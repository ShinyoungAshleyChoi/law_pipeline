"""슬랙 알림 서비스 모듈"""
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import structlog

from ..config import config
from ..logging_config import get_logger

logger = get_logger(__name__)

class NotificationLevel(Enum):
    """알림 레벨"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ErrorType(Enum):
    """오류 유형 분류"""
    API_CONNECTION_ERROR = "API_CONNECTION_ERROR"
    API_RESPONSE_ERROR = "API_RESPONSE_ERROR"
    DATA_VALIDATION_ERROR = "DATA_VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"

@dataclass
class SlackMessage:
    """슬랙 메시지 데이터"""
    text: str
    channel: Optional[str] = None
    level: NotificationLevel = NotificationLevel.INFO
    error_type: Optional[ErrorType] = None
    blocks: Optional[List[Dict]] = None
    attachments: Optional[List[Dict]] = None
    thread_ts: Optional[str] = None

@dataclass
class BatchResult:
    """배치 작업 결과"""
    job_name: str
    success: bool
    processed_laws: int
    processed_articles: int
    error_count: int
    error_message: Optional[str] = None
    duration: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class SlackNotificationService:
    """슬랙 알림 서비스"""
    
    def __init__(self):
        self.slack_config = config.slack
        self.client: Optional[WebClient] = None
        self.templates: Dict[str, str] = {}
        self._initialize()
    
    def _initialize(self) -> None:
        """슬랙 클라이언트 및 템플릿 초기화"""
        if not self.slack_config.enable_notifications:
            logger.info("슬랙 알림이 비활성화되어 있습니다")
            return
        
        # 슬랙 클라이언트 초기화
        if self.slack_config.bot_token:
            try:
                self.client = WebClient(token=self.slack_config.bot_token)
                # 연결 테스트
                response = self.client.auth_test()
                logger.info("슬랙 봇 연결 성공", 
                           bot_user=response.get("user"),
                           team=response.get("team"))
            except SlackApiError as e:
                logger.error("슬랙 봇 초기화 실패", error=str(e))
                self.client = None
        
        # 메시지 템플릿 로드
        self._load_templates()
    
    def _load_templates(self) -> None:
        """메시지 템플릿 로드"""
        try:
            import yaml
            config_path = config.config_dir / "notification.yaml"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    notification_config = yaml.safe_load(f)
                    self.templates = notification_config.get("slack", {}).get("templates", {})
                    logger.info("슬랙 메시지 템플릿 로드 완료", 
                               template_count=len(self.templates))
        except Exception as e:
            logger.warning("메시지 템플릿 로드 실패, 기본 템플릿 사용", error=str(e))
            self._load_default_templates()
    
    def _load_default_templates(self) -> None:
        """기본 메시지 템플릿 설정"""
        self.templates = {
            "error_alert": "🚨 *데이터 파이프라인 오류 발생*\n\n*시간:* {timestamp}\n*작업:* {job_name}\n*오류 유형:* {error_type}\n*오류:* {error_message}",
            "batch_success": "✅ *배치 작업 완료*\n\n*시간:* {timestamp}\n*작업:* {job_name}\n*처리된 법령:* {processed_laws}개",
            "batch_failure": "❌ *배치 작업 실패*\n\n*시간:* {timestamp}\n*작업:* {job_name}\n*오류 유형:* {error_type}\n*오류:* {error_message}",
            "critical_alert": "🔥 *긴급 알림*\n\n*시간:* {timestamp}\n*메시지:* {message}\n\n@channel 즉시 확인 필요!",
            "api_health_warning": "⚠️ *API 상태 경고*\n\n*시간:* {timestamp}\n*API:* {api_name}\n*상태:* {status}",
            # 오류 유형별 템플릿
            "api_connection_error": "🔌 *API 연결 오류*\n\n*시간:* {timestamp}\n*API:* {api_name}\n*오류:* {error_message}",
            "api_response_error": "📡 *API 응답 오류*\n\n*시간:* {timestamp}\n*API:* {api_name}\n*상태 코드:* {status_code}\n*오류:* {error_message}",
            "data_validation_error": "📋 *데이터 검증 오류*\n\n*시간:* {timestamp}\n*데이터 유형:* {data_type}\n*검증 실패:* {validation_error}",
            "database_error": "🗄️ *데이터베이스 오류*\n\n*시간:* {timestamp}\n*작업:* {operation}\n*오류:* {error_message}",
            "processing_error": "⚙️ *데이터 처리 오류*\n\n*시간:* {timestamp}\n*처리 단계:* {processing_stage}\n*오류:* {error_message}",
            "system_error": "💻 *시스템 오류*\n\n*시간:* {timestamp}\n*시스템:* {system_component}\n*오류:* {error_message}\n\n@channel 즉시 확인 필요!"
        }
    
    def send_error_alert(self, error: Exception, context: Dict[str, Any]) -> bool:
        """오류 알림 발송"""
        error_type = self._classify_error(error, context)
        
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "job_name": context.get("job_name", "Unknown"),
            "error_type": error_type.value,
            "error_message": str(error),
            "error_details": context.get("error_details", "")
        }
        
        # 오류 유형별 템플릿 선택
        template_key = self._get_template_key_for_error_type(error_type)
        template_data.update(context)  # 추가 컨텍스트 정보 포함
        
        message_text = self.templates.get(template_key, 
                                        self.templates.get("error_alert", "오류 발생: {error_message}")).format(**template_data)
        
        # 시스템 오류는 긴급 알림으로 처리
        level = NotificationLevel.CRITICAL if error_type == ErrorType.SYSTEM_ERROR else NotificationLevel.ERROR
        
        message = SlackMessage(
            text=message_text,
            level=level,
            error_type=error_type,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def send_batch_completion_notice(self, result: BatchResult) -> bool:
        """배치 작업 완료 알림 발송"""
        template_key = "batch_success" if result.success else "batch_failure"
        
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "job_name": result.job_name,
            "processed_laws": result.processed_laws,
            "processed_articles": result.processed_articles,
            "error_count": result.error_count,
            "error_message": result.error_message or "",
            "error_type": "BATCH_FAILURE" if not result.success else "",
            "duration": result.duration or "알 수 없음"
        }
        
        message_text = self.templates.get(template_key, "배치 작업 완료").format(**template_data)
        
        level = NotificationLevel.INFO if result.success else NotificationLevel.ERROR
        message = SlackMessage(
            text=message_text,
            level=level,
            error_type=ErrorType.PROCESSING_ERROR if not result.success else None,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def send_critical_alert(self, message: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """긴급 알림 발송"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": message
        }
        
        if context:
            template_data.update(context)
        
        message_text = self.templates.get("critical_alert", "🔥 긴급: {message}").format(**template_data)
        
        slack_message = SlackMessage(
            text=message_text,
            level=NotificationLevel.CRITICAL,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(slack_message)
    
    def send_api_health_warning(self, api_name: str, status: str, 
                               response_time: int, error_message: str = "") -> bool:
        """API 상태 경고 알림 발송"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "api_name": api_name,
            "status": status,
            "response_time": response_time,
            "error_message": error_message
        }
        
        message_text = self.templates.get("api_health_warning", 
                                        "⚠️ API 상태 경고: {api_name} - {status}").format(**template_data)
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.WARNING,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def _send_message(self, message: SlackMessage) -> bool:
        """슬랙 메시지 발송"""
        if not self.slack_config.enable_notifications:
            logger.debug("슬랙 알림이 비활성화되어 있어 메시지를 발송하지 않습니다")
            return True
        
        # Bot Token을 사용한 발송 시도
        if self.client and message.channel:
            success = self._send_via_bot_token(message)
            if success:
                return True
        
        # Webhook URL을 사용한 발송 시도
        if self.slack_config.webhook_url:
            return self._send_via_webhook(message)
        
        logger.error("슬랙 메시지 발송 실패: Bot Token과 Webhook URL이 모두 설정되지 않음")
        return False
    
    def _send_via_bot_token(self, message: SlackMessage) -> bool:
        """Bot Token을 사용한 메시지 발송"""
        for attempt in range(self.slack_config.retry_attempts):
            try:
                response = self.client.chat_postMessage(
                    channel=message.channel,
                    text=message.text,
                    blocks=message.blocks,
                    attachments=message.attachments,
                    thread_ts=message.thread_ts
                )
                
                if response["ok"]:
                    logger.info("슬랙 메시지 발송 성공 (Bot Token)", 
                               channel=message.channel,
                               ts=response.get("ts"))
                    return True
                else:
                    logger.error("슬랙 메시지 발송 실패 (Bot Token)", 
                                error=response.get("error"))
                    
            except SlackApiError as e:
                logger.error("슬랙 API 오류", 
                            error=str(e), 
                            attempt=attempt + 1)
                
                if attempt < self.slack_config.retry_attempts - 1:
                    time.sleep(self.slack_config.retry_delay)
            
            except Exception as e:
                logger.error("슬랙 메시지 발송 중 예상치 못한 오류", 
                            error=str(e), 
                            attempt=attempt + 1)
                
                if attempt < self.slack_config.retry_attempts - 1:
                    time.sleep(self.slack_config.retry_delay)
        
        return False
    
    def _send_via_webhook(self, message: SlackMessage) -> bool:
        """Webhook URL을 사용한 메시지 발송"""
        payload = {
            "text": message.text
        }
        
        if message.blocks:
            payload["blocks"] = message.blocks
        if message.attachments:
            payload["attachments"] = message.attachments
        
        for attempt in range(self.slack_config.retry_attempts):
            try:
                response = requests.post(
                    self.slack_config.webhook_url,
                    json=payload,
                    timeout=self.slack_config.timeout
                )
                
                if response.status_code == 200:
                    logger.info("슬랙 메시지 발송 성공 (Webhook)")
                    return True
                else:
                    logger.error("슬랙 Webhook 발송 실패", 
                                status_code=response.status_code,
                                response=response.text)
                    
            except requests.RequestException as e:
                logger.error("슬랙 Webhook 요청 오류", 
                            error=str(e), 
                            attempt=attempt + 1)
                
                if attempt < self.slack_config.retry_attempts - 1:
                    time.sleep(self.slack_config.retry_delay)
            
            except Exception as e:
                logger.error("슬랙 Webhook 발송 중 예상치 못한 오류", 
                            error=str(e), 
                            attempt=attempt + 1)
                
                if attempt < self.slack_config.retry_attempts - 1:
                    time.sleep(self.slack_config.retry_delay)
        
        return False
    
    def test_connection(self) -> bool:
        """슬랙 연결 테스트"""
        test_message = SlackMessage(
            text="🧪 법제처 데이터 파이프라인 알림 테스트",
            level=NotificationLevel.INFO,
            channel=self.slack_config.channel_id
        )
        
        success = self._send_message(test_message)
        if success:
            logger.info("슬랙 연결 테스트 성공")
        else:
            logger.error("슬랙 연결 테스트 실패")
        
        return success
    
    def _classify_error(self, error: Exception, context: Dict[str, Any]) -> ErrorType:
        """오류 유형 분류"""
        error_message = str(error).lower()
        error_class = error.__class__.__name__.lower()
        
        # API 관련 오류
        if "connection" in error_message or "timeout" in error_message or "network" in error_message:
            return ErrorType.API_CONNECTION_ERROR
        elif "http" in error_class or "response" in error_message or context.get("status_code"):
            return ErrorType.API_RESPONSE_ERROR
        
        # 데이터베이스 관련 오류
        elif "mysql" in error_message or "database" in error_message or "sql" in error_message:
            return ErrorType.DATABASE_ERROR
        
        # 데이터 검증 오류
        elif "validation" in error_message or "invalid" in error_message or "format" in error_message:
            return ErrorType.DATA_VALIDATION_ERROR
        
        # 시스템 오류
        elif "memory" in error_message or "disk" in error_message or "system" in error_message:
            return ErrorType.SYSTEM_ERROR
        
        # 처리 오류
        elif "processing" in error_message or "parse" in error_message:
            return ErrorType.PROCESSING_ERROR
        
        # 기본값
        return ErrorType.UNKNOWN_ERROR
    
    def _get_template_key_for_error_type(self, error_type: ErrorType) -> str:
        """오류 유형별 템플릿 키 반환"""
        template_mapping = {
            ErrorType.API_CONNECTION_ERROR: "api_connection_error",
            ErrorType.API_RESPONSE_ERROR: "api_response_error",
            ErrorType.DATA_VALIDATION_ERROR: "data_validation_error",
            ErrorType.DATABASE_ERROR: "database_error",
            ErrorType.PROCESSING_ERROR: "processing_error",
            ErrorType.SYSTEM_ERROR: "system_error",
            ErrorType.UNKNOWN_ERROR: "error_alert"
        }
        return template_mapping.get(error_type, "error_alert")
    
    def send_api_connection_error(self, api_name: str, error_message: str, context: Dict[str, Any] = None) -> bool:
        """API 연결 오류 알림"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "api_name": api_name,
            "error_message": error_message
        }
        
        if context:
            template_data.update(context)
        
        message_text = self.templates.get("api_connection_error").format(**template_data)
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.ERROR,
            error_type=ErrorType.API_CONNECTION_ERROR,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def send_database_error(self, operation: str, error_message: str, context: Dict[str, Any] = None) -> bool:
        """데이터베이스 오류 알림"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operation": operation,
            "error_message": error_message
        }
        
        if context:
            template_data.update(context)
        
        message_text = self.templates.get("database_error").format(**template_data)
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.ERROR,
            error_type=ErrorType.DATABASE_ERROR,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def send_data_validation_error(self, data_type: str, validation_error: str, context: Dict[str, Any] = None) -> bool:
        """데이터 검증 오류 알림"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_type": data_type,
            "validation_error": validation_error
        }
        
        if context:
            template_data.update(context)
        
        message_text = self.templates.get("data_validation_error").format(**template_data)
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.WARNING,
            error_type=ErrorType.DATA_VALIDATION_ERROR,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def send_system_error(self, system_component: str, error_message: str, context: Dict[str, Any] = None) -> bool:
        """시스템 오류 알림 (긴급)"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "system_component": system_component,
            "error_message": error_message
        }
        
        if context:
            template_data.update(context)
        
        message_text = self.templates.get("system_error").format(**template_data)
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.ERROR,
            error_type=ErrorType.SYSTEM_ERROR,
            channel=self.slack_config.channel_id
        )
        

# 전역 슬랙 알림 서비스 인스턴스
slack_service = SlackNotificationService()