"""슬랙 알림 서비스 유틸리티 함수들"""
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

from notifications.slack_service import SlackNotificationService, BatchResult
from logging_config import get_logger

logger = get_logger(__name__)

# 전역 슬랙 서비스 인스턴스
_slack_service = SlackNotificationService()

def notify_error(error: Exception, job_name: str = "Unknown", 
                error_details: Optional[str] = None, **kwargs) -> bool:
    """
    간편한 오류 알림 함수
    
    Args:
        error: 발생한 예외
        job_name: 작업명
        error_details: 추가 오류 상세 정보
        **kwargs: 추가 컨텍스트 정보
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    context = {
        "job_name": job_name,
        "error_details": error_details or traceback.format_exc(),
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    
    return _slack_service.send_error_alert(error, context)

def notify_batch_failure(job_name: str, error_message: str, 
                        error_details: Optional[str] = None) -> bool:
    """
    배치 작업 실패 알림
    
    Args:
        job_name: 배치 작업명
        error_message: 오류 메시지
        error_details: 추가 오류 상세 정보
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    result = BatchResult(
        job_name=job_name,
        success=False,
        processed_laws=0,
        processed_articles=0,
        error_count=1,
        error_message=error_message
    )
    
    return _slack_service.send_batch_completion_notice(result)

def notify_batch_success(job_name: str, processed_laws: int, 
                        processed_articles: int, duration: str) -> bool:
    """
    배치 작업 성공 알림
    
    Args:
        job_name: 배치 작업명
        processed_laws: 처리된 법령 수
        processed_articles: 처리된 조항 수
        duration: 소요 시간
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    result = BatchResult(
        job_name=job_name,
        success=True,
        processed_laws=processed_laws,
        processed_articles=processed_articles,
        error_count=0,
        duration=duration
    )
    
    return _slack_service.send_batch_completion_notice(result)

def notify_critical(message: str, **kwargs) -> bool:
    """
    긴급 알림
    
    Args:
        message: 긴급 메시지
        **kwargs: 추가 컨텍스트 정보
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    context = {
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }
    
    return _slack_service.send_critical_alert(message, context)

def notify_api_error(api_name: str, error_message: str, retry_count: int = 0) -> bool:
    """
    API 오류 알림 (error_alert 템플릿 사용)
    
    Args:
        api_name: API 이름
        error_message: 오류 메시지
        retry_count: 재시도 횟수
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    context = {
        "job_name": f"API-{api_name}",
        "retry_count": retry_count,
        "api_name": api_name
    }
    error = Exception(f"API 오류 - {api_name}: {error_message}")
    return _slack_service.send_error_alert(error, context)

def notify_database_error(operation: str, error_message: str, 
                         table_name: Optional[str] = None) -> bool:
    """
    데이터베이스 오류 알림 (error_alert 템플릿 사용)
    
    Args:
        operation: 수행 중이던 작업
        error_message: 오류 메시지
        table_name: 테이블명 (선택사항)
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    context = {
        "job_name": f"DB-{operation}",
        "operation": operation,
        "table_name": table_name
    }
    error = Exception(f"데이터베이스 오류 - {operation}: {error_message}")
    return _slack_service.send_error_alert(error, context)

def notify_validation_error(data_type: str, validation_error: str, 
                           affected_records: int = 0) -> bool:
    """
    데이터 검증 오류 알림 (api_health_warning 템플릿 사용 - 경고 수준)
    
    Args:
        data_type: 데이터 유형
        validation_error: 검증 오류 내용
        affected_records: 영향받은 레코드 수
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    return _slack_service.send_api_health_warning(
        api_name=f"Data-{data_type}",
        status="Validation Failed",
        response_time=0,
        error_message=f"{validation_error} (영향받은 레코드: {affected_records}개)" if affected_records > 0 else validation_error
    )

def notify_system_error(system_component: str, error_message: str) -> bool:
    """
    시스템 오류 알림 (critical_alert 템플릿 사용)
    
    Args:
        system_component: 시스템 컴포넌트명
        error_message: 오류 메시지
    
    Returns:
        bool: 알림 발송 성공 여부
    """
    message = f"시스템 컴포넌트 '{system_component}'에서 오류 발생: {error_message}"
    context = {"system_component": system_component}
    return _slack_service.send_critical_alert(message, context)

# 데코레이터 함수들
def with_error_notification(job_name: str = "Unknown"):
    """
    함수 실행 중 오류 발생 시 자동으로 알림을 보내는 데코레이터
    
    Args:
        job_name: 작업명
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                notify_error(e, job_name=job_name)
                raise
        return wrapper
    return decorator

def with_batch_notification(job_name: str):
    """
    배치 작업 결과를 자동으로 알림으로 보내는 데코레이터
    
    Args:
        job_name: 배치 작업명
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                end_time = datetime.now()
                duration = str(end_time - start_time)
                
                # 결과가 딕셔너리이고 필요한 키들이 있는 경우
                if isinstance(result, dict) and all(key in result for key in ['processed_laws', 'processed_articles']):
                    notify_batch_success(
                        job_name=job_name,
                        processed_laws=result['processed_laws'],
                        processed_articles=result['processed_articles'],
                        duration=duration
                    )
                
                return result
            except Exception as e:
                notify_batch_failure(
                    job_name=job_name,
                    error_message=str(e)
                )
                raise
        return wrapper
    return decorator