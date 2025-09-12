"""통합 알림 서비스 모듈"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .slack_service import SlackNotificationService, ErrorType, NotificationLevel, BatchResult
from ..logging_config import get_logger

logger = get_logger(__name__)

class NotificationService:
    """통합 알림 서비스 - 요구사항 6.1~6.5 구현"""
    
    def __init__(self):
        self.slack_service = SlackNotificationService()
    
    def send_error_alert(self, error: Exception, context: Dict[str, Any]) -> bool:
        """
        오류 알림 발송 - 요구사항 6.1, 6.2
        API 호출 실패, 데이터 적재 실패 시 관리자에게 알림 발송
        """
        try:
            success = self.slack_service.send_error_alert(error, context)
            if success:
                logger.info("오류 알림 발송 성공", 
                           error_type=str(error.__class__.__name__),
                           job_name=context.get("job_name"))
            else:
                logger.error("오류 알림 발송 실패", 
                            error_type=str(error.__class__.__name__),
                            job_name=context.get("job_name"))
            return success
        except Exception as e:
            logger.error("알림 발송 중 예상치 못한 오류", error=str(e))
            return False
    
    def send_batch_failure_alert(self, job_name: str, error_message: str, 
                                error_details: Optional[str] = None) -> bool:
        """
        배치 작업 실패 알림 - 요구사항 6.3
        배치 작업 실패 시 실패 원인과 함께 알림 발송
        """
        result = BatchResult(
            job_name=job_name,
            success=False,
            processed_laws=0,
            processed_articles=0,
            error_count=1,
            error_message=error_message
        )
        
        try:
            success = self.slack_service.send_batch_completion_notice(result)
            if success:
                logger.info("배치 실패 알림 발송 성공", job_name=job_name)
            else:
                logger.error("배치 실패 알림 발송 실패", job_name=job_name)
            return success
        except Exception as e:
            logger.error("배치 실패 알림 발송 중 오류", error=str(e))
            return False
    
    def send_critical_alert(self, message: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        긴급 알림 발송 - 요구사항 6.4
        연속적인 실패 발생 시 긴급 알림 발송
        """
        try:
            success = self.slack_service.send_critical_alert(message, context)
            if success:
                logger.info("긴급 알림 발송 성공", message=message)
            else:
                logger.error("긴급 알림 발송 실패", message=message)
            return success
        except Exception as e:
            logger.error("긴급 알림 발송 중 오류", error=str(e))
            return False
    
    def send_api_connection_error(self, api_name: str, error_message: str, 
                                 retry_count: int = 0) -> bool:
        """API 연결 오류 알림"""
        context = {"retry_count": retry_count} if retry_count > 0 else {}
        return self.slack_service.send_api_connection_error(api_name, error_message, context)
    
    def send_database_error(self, operation: str, error_message: str, 
                           table_name: Optional[str] = None) -> bool:
        """데이터베이스 오류 알림"""
        context = {"table_name": table_name} if table_name else {}
        return self.slack_service.send_database_error(operation, error_message, context)
    
    def send_data_validation_error(self, data_type: str, validation_error: str, 
                                  affected_records: int = 0) -> bool:
        """데이터 검증 오류 알림"""
        context = {"affected_records": affected_records} if affected_records > 0 else {}
        return self.slack_service.send_data_validation_error(data_type, validation_error, context)
    
    def send_system_error(self, system_component: str, error_message: str) -> bool:
        """시스템 오류 알림 (긴급)"""
        return self.slack_service.send_system_error(system_component, error_message)
    
    def send_batch_success_notice(self, job_name: str, processed_laws: int, 
                                 processed_articles: int, duration: str) -> bool:
        """배치 작업 성공 알림"""
        result = BatchResult(
            job_name=job_name,
            success=True,
            processed_laws=processed_laws,
            processed_articles=processed_articles,
            error_count=0,
            duration=duration
        )
        
        try:
            success = self.slack_service.send_batch_completion_notice(result)
            if success:
                logger.info("배치 성공 알림 발송 성공", job_name=job_name)
            return success
        except Exception as e:
            logger.error("배치 성공 알림 발송 중 오류", error=str(e))
            return False
    
    def test_notification_system(self) -> bool:
        """알림 시스템 연결 테스트"""
        try:
            return self.slack_service.test_connection()
        except Exception as e:
            logger.error("알림 시스템 테스트 중 오류", error=str(e))
            return False

# 전역 알림 서비스 인스턴스
notification_service = NotificationService()