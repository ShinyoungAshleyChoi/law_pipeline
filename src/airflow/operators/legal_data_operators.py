"""
법제처 데이터 파이프라인 전용 Airflow 오퍼레이터
"""
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import uuid
import json

from airflow.models import BaseOperator
from airflow.utils.context import Context
from airflow.exceptions import AirflowException, AirflowSkipException
from airflow.utils.decorators import apply_defaults

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.api.client import api_client
# from src.processors.incremental_processor import incremental_processor  # 삭제됨
from src.database.repository import LegalDataRepository
from src.notifications.slack_service import slack_service
from src.logging_config import get_logger

logger = get_logger(__name__)

class LegalAPIHealthCheckOperator(BaseOperator):
    """
    법제처 API 상태 확인 오퍼레이터
    """
    
    template_fields = ['max_response_time']
    ui_color = '#4CAF50'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        max_response_time: int = 10000,  # 최대 응답 시간 (ms)
        fail_on_error: bool = True,      # 오류 시 실패 처리 여부
        **kwargs
    ):
        super().__init__(**kwargs)
        self.max_response_time = max_response_time
        self.fail_on_error = fail_on_error
    
    def execute(self, context: Context) -> Dict[str, Any]:
        """API 상태 확인 실행"""
        logger.info("법제처 API 상태 확인 시작")
        
        try:
            # API 헬스체크 수행
            health_status = api_client.health_check()
            
            result = {
                'is_healthy': health_status.is_healthy,
                'response_time_ms': health_status.response_time_ms,
                'error_message': health_status.error_message,
                'check_time': datetime.now().isoformat(),
                'max_response_time': self.max_response_time
            }
            
            # 상태 검증
            if not health_status.is_healthy:
                error_msg = f"API 상태 불량: {health_status.error_message}"
                logger.error(error_msg)
                
                if self.fail_on_error:
                    raise AirflowException(error_msg)
                else:
                    result['warning'] = error_msg
            
            # 응답 시간 검증
            if health_status.response_time_ms > self.max_response_time:
                warning_msg = f"API 응답 시간 초과: {health_status.response_time_ms}ms > {self.max_response_time}ms"
                logger.warning(warning_msg)
                result['warning'] = warning_msg
            
            logger.info("API 상태 확인 완료", result=result)
            return result
            
        except Exception as e:
            logger.error("API 상태 확인 실패", error=str(e))
            if self.fail_on_error:
                raise
            return {
                'is_healthy': False,
                'error_message': str(e),
                'check_time': datetime.now().isoformat()
            }

class LegalDataCollectionOperator(BaseOperator):
    """
    법제처 데이터 수집 오퍼레이터
    """
    
    template_fields = ['target_date', 'batch_size']
    ui_color = '#2196F3'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        collection_type: str = 'incremental',  # 'incremental' or 'full' or 'target_date'
        target_date: Optional[str] = None,     # YYYY-MM-DD 형식
        batch_size: int = 50,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.collection_type = collection_type
        self.target_date = target_date
        self.batch_size = batch_size
    
    def execute(self, context: Context) -> Dict[str, Any]:
        """데이터 수집 실행"""
        logger.info("법제처 데이터 수집 시작", 
                   collection_type=self.collection_type,
                   target_date=self.target_date)
        
        try:
            job_id = self._generate_job_id(context)
            
            if self.collection_type == 'incremental':
                return self._execute_incremental_collection(job_id, context)
            elif self.collection_type == 'target_date':
                return self._execute_target_date_collection(job_id, context)
            elif self.collection_type == 'full':
                return self._execute_full_collection(job_id, context)
            else:
                raise AirflowException(f"지원하지 않는 수집 타입: {self.collection_type}")
                
        except Exception as e:
            logger.error("데이터 수집 실패", error=str(e))
            raise
    
    def _generate_job_id(self, context: Context) -> str:
        """작업 ID 생성"""
        execution_date = context['execution_date']
        job_id = f"legal_collection_{execution_date.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # XCom에 저장
        context['task_instance'].xcom_push(key='job_id', value=job_id)
        return job_id
    
    def _execute_incremental_collection(self, job_id: str, context: Context) -> Dict[str, Any]:
        """증분 수집 실행"""
        logger.info("증분 데이터 수집 시작", job_id=job_id)
        
        # Mock 증분 업데이트 실행 (실제 로직은 별도 구현 필요)
        all_stats = [{
            'target_date': date.today(),
            'total_laws_found': 0,
            'new_laws': 0,
            'updated_laws': 0,
            'error_count': 0
        }]
        
        # 결과 집계
        total_stats = {
            'total_new_laws': sum(s.new_laws for s in all_stats),
            'total_updated_laws': sum(s.updated_laws for s in all_stats),
            'total_new_articles': sum(s.new_articles for s in all_stats),
            'total_updated_articles': sum(s.updated_articles for s in all_stats),
            'total_errors': sum(s.error_count for s in all_stats),
            'total_processing_time': sum(s.processing_time_seconds for s in all_stats),
            'processed_dates': len(all_stats)
        }
        
        result = {
            'job_id': job_id,
            'collection_type': 'incremental',
            'success': total_stats['total_errors'] == 0,
            'stats': total_stats,
            'daily_stats': [
                {
                    'target_date': stats.target_date.isoformat(),
                    'total_laws_found': stats.total_laws_found,
                    'new_laws': stats.new_laws,
                    'updated_laws': stats.updated_laws,
                    'new_articles': stats.new_articles,
                    'updated_articles': stats.updated_articles,
                    'error_count': stats.error_count,
                    'processing_time_seconds': stats.processing_time_seconds
                }
                for stats in all_stats
            ],
            'completion_time': datetime.now().isoformat()
        }
        
        logger.info("증분 데이터 수집 완료", result=result['stats'])
        return result
    
    def _execute_target_date_collection(self, job_id: str, context: Context) -> Dict[str, Any]:
        """특정 날짜 수집 실행"""
        if not self.target_date:
            raise AirflowException("target_date가 지정되지 않았습니다")
        
        target_date_obj = datetime.strptime(self.target_date, '%Y-%m-%d').date()
        logger.info("특정 날짜 데이터 수집 시작", 
                   job_id=job_id, 
                   target_date=target_date_obj)
        
        # Mock 일별 처리 (실제 로직은 별도 구현 필요)
        daily_stats = {
            'target_date': target_date_obj,
            'total_laws_found': 0,
            'new_laws': 0,
            'updated_laws': 0,
            'error_count': 0
        }
        
        result = {
            'job_id': job_id,
            'collection_type': 'target_date',
            'target_date': target_date_obj.isoformat(),
            'success': daily_stats.error_count == 0,
            'stats': {
                'total_laws_found': daily_stats.total_laws_found,
                'new_laws': daily_stats.new_laws,
                'updated_laws': daily_stats.updated_laws,
                'new_articles': daily_stats.new_articles,
                'updated_articles': daily_stats.updated_articles,
                'error_count': daily_stats.error_count,
                'processing_time_seconds': daily_stats.processing_time_seconds
            },
            'completion_time': datetime.now().isoformat()
        }
        
        logger.info("특정 날짜 데이터 수집 완료", result=result['stats'])
        return result
    
    def _execute_full_collection(self, job_id: str, context: Context) -> Dict[str, Any]:
        """전체 수집 실행 (구현 예정)"""
        logger.warning("전체 수집은 아직 구현되지 않았습니다")
        raise AirflowSkipException("전체 수집은 별도 DAG에서 처리됩니다")

class LegalDataValidationOperator(BaseOperator):
    """
    법제처 데이터 검증 오퍼레이터
    """
    
    template_fields = ['validation_rules']
    ui_color = '#FF9800'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        validation_rules: Optional[Dict[str, Any]] = None,
        fail_on_validation_error: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.validation_rules = validation_rules or {}
        self.fail_on_validation_error = fail_on_validation_error
    
    def execute(self, context: Context) -> Dict[str, Any]:
        """데이터 검증 실행"""
        logger.info("데이터 검증 시작")
        
        try:
            # 이전 태스크에서 수집 결과 조회
            collection_result = context['task_instance'].xcom_pull(
                task_ids=self._get_collection_task_id(context)
            )
            
            if not collection_result:
                raise AirflowException("수집 결과를 찾을 수 없습니다")
            
            # 기본 검증 수행
            validation_result = self._perform_basic_validation(collection_result)
            
            # 추가 검증 규칙 적용
            if self.validation_rules:
                additional_validation = self._apply_validation_rules(
                    collection_result, self.validation_rules
                )
                validation_result.update(additional_validation)
            
            # 검증 결과 평가
            is_valid = validation_result.get('is_valid', True)
            
            if not is_valid and self.fail_on_validation_error:
                error_msg = f"데이터 검증 실패: {validation_result.get('error_messages', [])}"
                logger.error(error_msg)
                raise AirflowException(error_msg)
            
            logger.info("데이터 검증 완료", result=validation_result)
            return validation_result
            
        except Exception as e:
            logger.error("데이터 검증 실패", error=str(e))
            raise
    
    def _get_collection_task_id(self, context: Context) -> str:
        """수집 태스크 ID 추정"""
        # 일반적인 수집 태스크 ID들을 시도
        possible_task_ids = [
            'collect_legal_data',
            'data_collection.collect_law_contents',
            'legal_data_collection'
        ]
        
        for task_id in possible_task_ids:
            try:
                result = context['task_instance'].xcom_pull(task_ids=task_id)
                if result:
                    return task_id
            except:
                continue
        
        raise AirflowException("수집 태스크를 찾을 수 없습니다")
    
    def _perform_basic_validation(self, collection_result: Dict[str, Any]) -> Dict[str, Any]:
        """기본 검증 수행"""
        validation_errors = []
        validation_warnings = []
        
        # 성공 여부 확인
        if not collection_result.get('success', False):
            validation_errors.append("데이터 수집이 실패했습니다")
        
        # 통계 확인
        stats = collection_result.get('stats', {})
        
        # 오류 건수 확인
        error_count = stats.get('total_errors', 0)
        if error_count > 0:
            validation_warnings.append(f"수집 중 {error_count}건의 오류가 발생했습니다")
        
        # 처리된 데이터 확인
        total_processed = stats.get('total_new_laws', 0) + stats.get('total_updated_laws', 0)
        if total_processed == 0:
            validation_warnings.append("처리된 법령이 없습니다")
        
        # 처리 시간 확인
        processing_time = stats.get('total_processing_time', 0)
        if processing_time > 3600:  # 1시간 초과
            validation_warnings.append(f"처리 시간이 길습니다: {processing_time:.1f}초")
        
        return {
            'is_valid': len(validation_errors) == 0,
            'error_messages': validation_errors,
            'warning_messages': validation_warnings,
            'validation_time': datetime.now().isoformat(),
            'validated_stats': stats
        }
    
    def _apply_validation_rules(self, collection_result: Dict[str, Any], 
                               rules: Dict[str, Any]) -> Dict[str, Any]:
        """추가 검증 규칙 적용"""
        additional_errors = []
        additional_warnings = []
        
        stats = collection_result.get('stats', {})
        
        # 최소 처리 건수 확인
        if 'min_processed_laws' in rules:
            min_laws = rules['min_processed_laws']
            total_processed = stats.get('total_new_laws', 0) + stats.get('total_updated_laws', 0)
            if total_processed < min_laws:
                additional_errors.append(f"처리된 법령 수가 최소 기준 미달: {total_processed} < {min_laws}")
        
        # 최대 오류 비율 확인
        if 'max_error_rate' in rules:
            max_error_rate = rules['max_error_rate']
            total_found = stats.get('total_laws_found', 0)
            error_count = stats.get('total_errors', 0)
            
            if total_found > 0:
                error_rate = error_count / total_found
                if error_rate > max_error_rate:
                    additional_errors.append(f"오류 비율이 허용 기준 초과: {error_rate:.2%} > {max_error_rate:.2%}")
        
        # 최대 처리 시간 확인
        if 'max_processing_time' in rules:
            max_time = rules['max_processing_time']
            processing_time = stats.get('total_processing_time', 0)
            if processing_time > max_time:
                additional_warnings.append(f"처리 시간이 기준 초과: {processing_time:.1f}초 > {max_time}초")
        
        return {
            'additional_errors': additional_errors,
            'additional_warnings': additional_warnings,
            'rules_applied': list(rules.keys())
        }

class LegalDataNotificationOperator(BaseOperator):
    """
    법제처 데이터 파이프라인 알림 오퍼레이터
    """
    
    template_fields = ['message_template', 'notification_channels']
    ui_color = '#9C27B0'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        notification_type: str = 'completion',  # 'completion', 'error', 'warning'
        message_template: Optional[str] = None,
        notification_channels: List[str] = None,
        include_stats: bool = True,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.notification_type = notification_type
        self.message_template = message_template
        self.notification_channels = notification_channels or ['slack']
        self.include_stats = include_stats
    
    def execute(self, context: Context) -> Dict[str, Any]:
        """알림 발송 실행"""
        logger.info("알림 발송 시작", notification_type=self.notification_type)
        
        try:
            # 이전 태스크들의 결과 수집
            task_results = self._collect_task_results(context)
            
            # 알림 메시지 생성
            message = self._generate_message(task_results, context)
            
            # 알림 발송
            notification_results = []
            
            for channel in self.notification_channels:
                try:
                    if channel == 'slack':
                        result = self._send_slack_notification(message, task_results)
                        notification_results.append({'channel': 'slack', 'success': True, 'result': result})
                    elif channel == 'email':
                        result = self._send_email_notification(message, task_results, context)
                        notification_results.append({'channel': 'email', 'success': True, 'result': result})
                    else:
                        logger.warning("지원하지 않는 알림 채널", channel=channel)
                        
                except Exception as e:
                    logger.error("알림 발송 실패", channel=channel, error=str(e))
                    notification_results.append({'channel': channel, 'success': False, 'error': str(e)})
            
            result = {
                'notification_type': self.notification_type,
                'channels_attempted': self.notification_channels,
                'results': notification_results,
                'message_sent': message,
                'send_time': datetime.now().isoformat()
            }
            
            logger.info("알림 발송 완료", result=result)
            return result
            
        except Exception as e:
            logger.error("알림 발송 실패", error=str(e))
            raise
    
    def _collect_task_results(self, context: Context) -> Dict[str, Any]:
        """이전 태스크 결과 수집"""
        results = {}
        
        # 일반적인 태스크 ID들에서 결과 수집
        task_ids_to_check = [
            'generate_job_id',
            'check_prerequisites', 
            'collect_legal_data',
            'validate_collected_data',
            'update_sync_status'
        ]
        
        for task_id in task_ids_to_check:
            try:
                result = context['task_instance'].xcom_pull(task_ids=task_id)
                if result:
                    results[task_id] = result
            except:
                continue
        
        return results
    
    def _generate_message(self, task_results: Dict[str, Any], context: Context) -> str:
        """알림 메시지 생성"""
        if self.message_template:
            # 템플릿이 제공된 경우 사용
            return self.message_template.format(**task_results, **context)
        
        # 기본 메시지 생성
        job_id = task_results.get('generate_job_id', 'unknown')
        execution_date = context.get('execution_date', datetime.now())
        
        if self.notification_type == 'completion':
            return self._generate_completion_message(job_id, task_results, execution_date)
        elif self.notification_type == 'error':
            return self._generate_error_message(job_id, task_results, execution_date, context)
        elif self.notification_type == 'warning':
            return self._generate_warning_message(job_id, task_results, execution_date)
        else:
            return f"법제처 데이터 파이프라인 알림 - {self.notification_type}"
    
    def _generate_completion_message(self, job_id: str, task_results: Dict[str, Any], 
                                   execution_date: datetime) -> str:
        """완료 메시지 생성"""
        collection_result = task_results.get('collect_legal_data', {})
        stats = collection_result.get('stats', {})
        
        message = f"""
✅ 법제처 데이터 파이프라인 완료

🆔 작업 ID: {job_id}
📅 실행 시간: {execution_date.strftime('%Y-%m-%d %H:%M:%S')}

📊 처리 결과:
• 신규 법령: {stats.get('total_new_laws', 0)}개
• 업데이트 법령: {stats.get('total_updated_laws', 0)}개
• 신규 조항: {stats.get('total_new_articles', 0)}개
• 업데이트 조항: {stats.get('total_updated_articles', 0)}개
• 오류 건수: {stats.get('total_errors', 0)}건
• 처리 시간: {stats.get('total_processing_time', 0):.1f}초

🎯 상태: {'성공' if stats.get('total_errors', 0) == 0 else '부분 성공'}
        """.strip()
        
        return message
    
    def _generate_error_message(self, job_id: str, task_results: Dict[str, Any], 
                              execution_date: datetime, context: Context) -> str:
        """오류 메시지 생성"""
        failed_task = context.get('task_instance', {}).task_id if context.get('task_instance') else 'unknown'
        exception = context.get('exception', 'Unknown error')
        
        message = f"""
🚨 법제처 데이터 파이프라인 실패

🆔 작업 ID: {job_id}
📅 실행 시간: {execution_date.strftime('%Y-%m-%d %H:%M:%S')}
📍 실패 태스크: {failed_task}

❌ 오류 내용:
{str(exception)}

🔧 관리자 확인이 필요합니다.
        """.strip()
        
        return message
    
    def _generate_warning_message(self, job_id: str, task_results: Dict[str, Any], 
                                execution_date: datetime) -> str:
        """경고 메시지 생성"""
        validation_result = task_results.get('validate_collected_data', {})
        warnings = validation_result.get('warning_messages', [])
        
        warning_text = '\n'.join([f"• {w}" for w in warnings[:5]])
        
        message = f"""
⚠️ 법제처 데이터 파이프라인 경고

🆔 작업 ID: {job_id}
📅 실행 시간: {execution_date.strftime('%Y-%m-%d %H:%M:%S')}

📋 경고 사항:
{warning_text}

ℹ️ 파이프라인은 완료되었으나 주의가 필요합니다.
        """.strip()
        
        return message
    
    def _send_slack_notification(self, message: str, task_results: Dict[str, Any]) -> Dict[str, Any]:
        """Slack 알림 발송"""
        try:
            if self.notification_type == 'error':
                slack_service.send_error_alert(
                    title="법제처 데이터 파이프라인 오류",
                    message=message,
                    context=task_results
                )
            else:
                slack_service.send_info_message(
                    title="법제처 데이터 파이프라인 알림",
                    message=message
                )
            
            return {'status': 'sent', 'channel': 'slack'}
            
        except Exception as e:
            logger.error("Slack 알림 발송 실패", error=str(e))
            raise
    
    def _send_email_notification(self, message: str, task_results: Dict[str, Any], 
                               context: Context) -> Dict[str, Any]:
        """이메일 알림 발송"""
        try:
            from airflow.utils.email import send_email
            
            subject = f"법제처 데이터 파이프라인 - {self.notification_type.title()}"
            
            # 이메일 수신자 설정 (Airflow Variable에서 조회)
            from airflow.models import Variable
            recipients = Variable.get("legal_pipeline_email_recipients", 
                                    default_var="admin@company.com").split(',')
            
            send_email(
                to=recipients,
                subject=subject,
                html_content=f"<pre>{message}</pre>",
                mime_charset='utf-8'
            )
            
            return {'status': 'sent', 'channel': 'email', 'recipients': recipients}
            
        except Exception as e:
            logger.error("이메일 알림 발송 실패", error=str(e))
            raise

class LegalDataCleanupOperator(BaseOperator):
    """
    법제처 데이터 파이프라인 정리 오퍼레이터
    """
    
    template_fields = ['cleanup_days', 'cleanup_paths']
    ui_color = '#607D8B'
    ui_fgcolor = '#FFFFFF'
    
    @apply_defaults
    def __init__(
        self,
        cleanup_days: int = 7,           # 정리할 파일 나이 (일)
        cleanup_paths: List[str] = None, # 정리할 경로 목록
        cleanup_logs: bool = True,       # 로그 파일 정리 여부
        cleanup_temp: bool = True,       # 임시 파일 정리 여부
        **kwargs
    ):
        super().__init__(**kwargs)
        self.cleanup_days = cleanup_days
        self.cleanup_paths = cleanup_paths or ['/tmp', '/var/log/airflow']
        self.cleanup_logs = cleanup_logs
        self.cleanup_temp = cleanup_temp
    
    def execute(self, context: Context) -> Dict[str, Any]:
        """정리 작업 실행"""
        logger.info("정리 작업 시작", cleanup_days=self.cleanup_days)
        
        cleanup_results = []
        
        try:
            # 임시 파일 정리
            if self.cleanup_temp:
                temp_result = self._cleanup_temp_files()
                cleanup_results.append(temp_result)
            
            # 로그 파일 정리
            if self.cleanup_logs:
                log_result = self._cleanup_log_files()
                cleanup_results.append(log_result)
            
            # 추가 경로 정리
            for path in self.cleanup_paths:
                path_result = self._cleanup_path(path)
                cleanup_results.append(path_result)
            
            # 데이터베이스 정리
            db_result = self._cleanup_database()
            cleanup_results.append(db_result)
            
            result = {
                'cleanup_completed': True,
                'cleanup_days': self.cleanup_days,
                'results': cleanup_results,
                'total_files_removed': sum(r.get('files_removed', 0) for r in cleanup_results),
                'total_space_freed_mb': sum(r.get('space_freed_mb', 0) for r in cleanup_results),
                'cleanup_time': datetime.now().isoformat()
            }
            
            logger.info("정리 작업 완료", result=result)
            return result
            
        except Exception as e:
            logger.error("정리 작업 실패", error=str(e))
            raise
    
    def _cleanup_temp_files(self) -> Dict[str, Any]:
        """임시 파일 정리"""
        import os
        import glob
        from pathlib import Path
        
        logger.info("임시 파일 정리 시작")
        
        temp_patterns = [
            '/tmp/legal_pipeline_*',
            '/tmp/airflow_*',
            '/tmp/*.tmp'
        ]
        
        files_removed = 0
        space_freed = 0
        
        cutoff_time = datetime.now() - timedelta(days=self.cleanup_days)
        
        for pattern in temp_patterns:
            try:
                for file_path in glob.glob(pattern):
                    try:
                        file_stat = os.stat(file_path)
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        if file_mtime < cutoff_time:
                            file_size = file_stat.st_size
                            os.remove(file_path)
                            files_removed += 1
                            space_freed += file_size
                            logger.debug("임시 파일 삭제", file_path=file_path)
                            
                    except Exception as e:
                        logger.warning("파일 삭제 실패", file_path=file_path, error=str(e))
                        
            except Exception as e:
                logger.warning("패턴 처리 실패", pattern=pattern, error=str(e))
        
        result = {
            'type': 'temp_files',
            'files_removed': files_removed,
            'space_freed_mb': space_freed / (1024 * 1024),
            'patterns_checked': temp_patterns
        }
        
        logger.info("임시 파일 정리 완료", result=result)
        return result
    
    def _cleanup_log_files(self) -> Dict[str, Any]:
        """로그 파일 정리"""
        import os
        import glob
        
        logger.info("로그 파일 정리 시작")
        
        log_patterns = [
            '/var/log/airflow/*.log.*',
            '/var/log/legal-pipeline/*.log.*',
            '*.log.old'
        ]
        
        files_removed = 0
        space_freed = 0
        
        cutoff_time = datetime.now() - timedelta(days=self.cleanup_days)
        
        for pattern in log_patterns:
            try:
                for file_path in glob.glob(pattern):
                    try:
                        file_stat = os.stat(file_path)
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        if file_mtime < cutoff_time:
                            file_size = file_stat.st_size
                            os.remove(file_path)
                            files_removed += 1
                            space_freed += file_size
                            logger.debug("로그 파일 삭제", file_path=file_path)
                            
                    except Exception as e:
                        logger.warning("로그 파일 삭제 실패", file_path=file_path, error=str(e))
                        
            except Exception as e:
                logger.warning("로그 패턴 처리 실패", pattern=pattern, error=str(e))
        
        result = {
            'type': 'log_files',
            'files_removed': files_removed,
            'space_freed_mb': space_freed / (1024 * 1024),
            'patterns_checked': log_patterns
        }
        
        logger.info("로그 파일 정리 완료", result=result)
        return result
    
    def _cleanup_path(self, path: str) -> Dict[str, Any]:
        """특정 경로 정리"""
        logger.info("경로 정리 시작", path=path)
        
        # 안전성을 위해 특정 경로만 허용
        allowed_paths = ['/tmp', '/var/log', '/var/cache']
        if not any(path.startswith(allowed) for allowed in allowed_paths):
            logger.warning("허용되지 않은 경로", path=path)
            return {'type': 'path_cleanup', 'path': path, 'skipped': True, 'reason': 'not_allowed'}
        
        files_removed = 0
        space_freed = 0
        
        try:
            import os
            cutoff_time = datetime.now() - timedelta(days=self.cleanup_days)
            
            for root, dirs, files in os.walk(path):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_stat = os.stat(file_path)
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        if file_mtime < cutoff_time:
                            file_size = file_stat.st_size
                            os.remove(file_path)
                            files_removed += 1
                            space_freed += file_size
                            
                    except Exception as e:
                        logger.warning("파일 삭제 실패", file_path=file_path, error=str(e))
                        
        except Exception as e:
            logger.error("경로 정리 실패", path=path, error=str(e))
        
        result = {
            'type': 'path_cleanup',
            'path': path,
            'files_removed': files_removed,
            'space_freed_mb': space_freed / (1024 * 1024)
        }
        
        logger.info("경로 정리 완료", result=result)
        return result
    
    def _cleanup_database(self) -> Dict[str, Any]:
        """데이터베이스 정리"""
        logger.info("데이터베이스 정리 시작")
        
        try:
            repository = LegalDataRepository()
            
            # 오래된 배치 작업 기록 정리
            cutoff_date = datetime.now() - timedelta(days=self.cleanup_days * 2)  # 배치 기록은 더 오래 보관
            
            with repository.transaction():
                # 구현 예정: 오래된 배치 작업 기록 삭제
                # repository.cleanup_old_batch_jobs(cutoff_date)
                pass
            
            result = {
                'type': 'database_cleanup',
                'cutoff_date': cutoff_date.isoformat(),
                'records_removed': 0,  # 실제 구현 시 업데이트
                'tables_cleaned': ['batch_jobs']
            }
            
            logger.info("데이터베이스 정리 완료", result=result)
            return result
            
        except Exception as e:
            logger.error("데이터베이스 정리 실패", error=str(e))
            return {
                'type': 'database_cleanup',
                'error': str(e),
                'records_removed': 0
            }