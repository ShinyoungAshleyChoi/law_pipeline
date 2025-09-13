"""
Airflow DAG 유틸리티 함수
"""
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional
import json
import uuid
from airflow.models import Variable
from airflow.exceptions import AirflowException

from logging_config import get_logger

logger = get_logger(__name__)

class DAGConfigManager:
    """DAG 설정 관리자"""
    
    @staticmethod
    def get_pipeline_config() -> Dict[str, Any]:
        """파이프라인 설정 조회"""
        try:
            config_json = Variable.get("legal_pipeline_config", default_var="{}")
            config = json.loads(config_json)
            
            # 기본 설정 병합
            default_config = {
                'max_retry_count': 3,
                'retry_delay_minutes': 5,
                'execution_timeout_hours': 2,
                'sla_hours': 3,
                'notification_enabled': True,
                'data_validation_enabled': True,
                'batch_size': 50,
                'api_timeout_seconds': 30,
                'max_concurrent_tasks': 5
            }
            
            return {**default_config, **config}
            
        except Exception as e:
            logger.error("파이프라인 설정 조회 실패", error=str(e))
            return {
                'max_retry_count': 3,
                'retry_delay_minutes': 5,
                'execution_timeout_hours': 2,
                'sla_hours': 3,
                'notification_enabled': True,
                'data_validation_enabled': True,
                'batch_size': 50,
                'api_timeout_seconds': 30,
                'max_concurrent_tasks': 5
            }
    
    @staticmethod
    def get_schedule_config() -> Dict[str, Any]:
        """스케줄 설정 조회"""
        try:
            schedule_json = Variable.get("legal_pipeline_schedule", default_var="{}")
            schedule = json.loads(schedule_json)
            
            default_schedule = {
                'incremental_cron': '0 2 * * *',  # 매일 새벽 2시
                'full_sync_cron': '0 1 * * 0',   # 매주 일요일 새벽 1시
                'health_check_cron': '*/30 * * * *',  # 30분마다
                'cleanup_cron': '0 3 * * *'      # 매일 새벽 3시
            }
            
            return {**default_schedule, **schedule}
            
        except Exception as e:
            logger.error("스케줄 설정 조회 실패", error=str(e))
            return {
                'incremental_cron': '0 2 * * *',
                'full_sync_cron': '0 1 * * 0',
                'health_check_cron': '*/30 * * * *',
                'cleanup_cron': '0 3 * * *'
            }

class TaskStateManager:
    """태스크 상태 관리자"""
    
    @staticmethod
    def create_job_context(execution_date: datetime, dag_id: str) -> Dict[str, Any]:
        """작업 컨텍스트 생성"""
        job_id = f"{dag_id}_{execution_date.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        return {
            'job_id': job_id,
            'execution_date': execution_date.isoformat(),
            'dag_id': dag_id,
            'created_at': datetime.now().isoformat()
        }
    
    @staticmethod
    def validate_task_dependencies(context: Dict[str, Any], required_tasks: List[str]) -> bool:
        """태스크 의존성 검증"""
        task_instance = context.get('task_instance')
        if not task_instance:
            return False
        
        for task_id in required_tasks:
            try:
                result = task_instance.xcom_pull(task_ids=task_id)
                if result is None:
                    logger.error("필수 태스크 결과 누락", task_id=task_id)
                    return False
            except Exception as e:
                logger.error("태스크 의존성 검증 실패", task_id=task_id, error=str(e))
                return False
        
        return True
    
    @staticmethod
    def get_task_result(context: Dict[str, Any], task_id: str, key: Optional[str] = None) -> Any:
        """태스크 결과 조회"""
        try:
            task_instance = context.get('task_instance')
            if not task_instance:
                raise AirflowException("TaskInstance를 찾을 수 없습니다")
            
            if key:
                return task_instance.xcom_pull(task_ids=task_id, key=key)
            else:
                return task_instance.xcom_pull(task_ids=task_id)
                
        except Exception as e:
            logger.error("태스크 결과 조회 실패", task_id=task_id, key=key, error=str(e))
            return None

class ErrorHandler:
    """오류 처리 유틸리티"""
    
    @staticmethod
    def should_retry(exception: Exception, attempt_count: int, max_retries: int) -> bool:
        """재시도 여부 결정"""
        if attempt_count >= max_retries:
            return False
        
        # 특정 오류 타입에 대한 재시도 정책
        retry_exceptions = [
            'ConnectionError',
            'TimeoutError',
            'APIError',
            'TemporaryFailure'
        ]
        
        exception_name = exception.__class__.__name__
        return exception_name in retry_exceptions
    
    @staticmethod
    def calculate_retry_delay(attempt_count: int, base_delay: int = 300) -> int:
        """지수 백오프 재시도 지연 계산"""
        return min(base_delay * (2 ** attempt_count), 1800)  # 최대 30분
    
    @staticmethod
    def format_error_message(exception: Exception, context: Dict[str, Any]) -> str:
        """오류 메시지 포맷팅"""
        task_id = context.get('task_instance', {}).task_id if context.get('task_instance') else 'unknown'
        execution_date = context.get('execution_date', 'unknown')
        
        return f"""
오류 발생:
- 태스크: {task_id}
- 실행 시간: {execution_date}
- 오류 타입: {exception.__class__.__name__}
- 오류 메시지: {str(exception)}
        """.strip()

class DataQualityChecker:
    """데이터 품질 검사기"""
    
    @staticmethod
    def validate_law_data_quality(laws_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """법령 데이터 품질 검증"""
        if not laws_data:
            return {
                'is_valid': False,
                'error_message': '법령 데이터가 없습니다',
                'quality_score': 0.0
            }
        
        total_laws = len(laws_data)
        valid_laws = 0
        issues = []
        
        for law in laws_data:
            is_valid = True
            
            # 필수 필드 검증
            required_fields = ['law_id', 'law_master_no', 'law_name', 'enforcement_date']
            for field in required_fields:
                if not law.get(field):
                    issues.append(f"법령 {law.get('law_id', 'unknown')}: {field} 필드 누락")
                    is_valid = False
            
            # 날짜 형식 검증
            if law.get('enforcement_date'):
                try:
                    datetime.fromisoformat(law['enforcement_date'].replace('Z', '+00:00'))
                except ValueError:
                    issues.append(f"법령 {law.get('law_id', 'unknown')}: 잘못된 시행일 형식")
                    is_valid = False
            
            # 법령명 길이 검증
            if law.get('law_name') and len(law['law_name']) > 500:
                issues.append(f"법령 {law.get('law_id', 'unknown')}: 법령명이 너무 깁니다")
                is_valid = False
            
            if is_valid:
                valid_laws += 1
        
        quality_score = valid_laws / total_laws if total_laws > 0 else 0.0
        
        return {
            'is_valid': quality_score >= 0.95,  # 95% 이상 유효해야 통과
            'quality_score': quality_score,
            'total_laws': total_laws,
            'valid_laws': valid_laws,
            'issues': issues[:10],  # 최대 10개 이슈만 반환
            'total_issues': len(issues)
        }
    
    @staticmethod
    def check_data_freshness(last_update: datetime, max_age_hours: int = 25) -> Dict[str, Any]:
        """데이터 신선도 검사"""
        now = datetime.now()
        age_hours = (now - last_update).total_seconds() / 3600
        
        return {
            'is_fresh': age_hours <= max_age_hours,
            'age_hours': age_hours,
            'last_update': last_update.isoformat(),
            'max_age_hours': max_age_hours,
            'status': 'fresh' if age_hours <= max_age_hours else 'stale'
        }

class PerformanceMonitor:
    """성능 모니터링 유틸리티"""
    
    @staticmethod
    def measure_task_performance(func):
        """태스크 성능 측정 데코레이터"""
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # 성능 메트릭 로깅
                logger.info("태스크 성능 측정",
                           function=func.__name__,
                           duration_seconds=duration,
                           start_time=start_time.isoformat(),
                           end_time=end_time.isoformat())
                
                # 결과에 성능 정보 추가
                if isinstance(result, dict):
                    result['performance'] = {
                        'duration_seconds': duration,
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat()
                    }
                
                return result
                
            except Exception as e:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.error("태스크 실행 실패",
                           function=func.__name__,
                           duration_seconds=duration,
                           error=str(e))
                raise
        
        return wrapper
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """시스템 메트릭 수집"""
        import psutil
        
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error("시스템 메트릭 수집 실패", error=str(e))
            return {
                'cpu_percent': 0,
                'memory_percent': 0,
                'disk_percent': 0,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

class NotificationFormatter:
    """알림 메시지 포맷터"""
    
    @staticmethod
    def format_success_message(job_id: str, stats: Dict[str, Any]) -> str:
        """성공 메시지 포맷팅"""
        return f"""
✅ 법제처 데이터 파이프라인 성공

🆔 작업 ID: {job_id}
📊 처리 결과:
• 신규 법령: {stats.get('new_laws', 0)}개
• 업데이트 법령: {stats.get('updated_laws', 0)}개
• 신규 조항: {stats.get('new_articles', 0)}개
• 업데이트 조항: {stats.get('updated_articles', 0)}개
• 처리 시간: {stats.get('processing_time', 0):.1f}초

🕐 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
    
    @staticmethod
    def format_error_message(job_id: str, error: str, context: Dict[str, Any]) -> str:
        """오류 메시지 포맷팅"""
        task_id = context.get('task_instance', {}).task_id if context.get('task_instance') else 'unknown'
        
        return f"""
🚨 법제처 데이터 파이프라인 오류

🆔 작업 ID: {job_id}
📍 실패 태스크: {task_id}
❌ 오류 내용: {error}

🕐 발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔧 관리자 확인이 필요합니다.
        """.strip()
    
    @staticmethod
    def format_warning_message(job_id: str, warnings: List[str]) -> str:
        """경고 메시지 포맷팅"""
        warning_text = '\n'.join([f"• {w}" for w in warnings[:5]])
        
        return f"""
⚠️ 법제처 데이터 파이프라인 경고

🆔 작업 ID: {job_id}
📋 경고 사항:
{warning_text}

🕐 발생 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()