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

from config import config
from logging_config import get_logger

logger = get_logger(__name__)

class NotificationLevel(Enum):
    """알림 레벨"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

@dataclass
class SlackMessage:
    """슬랙 메시지 데이터"""
    text: str
    channel: Optional[str] = None
    level: NotificationLevel = NotificationLevel.INFO
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
            logger.info("슬랙 알림이 config/notification.yaml에서 비활성화되어 있습니다")
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
        """메시지 템플릿 로드 (notification.yaml에서만)"""
        try:
            import yaml
            config_path = config.config_dir / "notification.yaml"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    notification_config = yaml.safe_load(f)
                    templates = notification_config.get("slack", {}).get("templates", {})
                    if templates:
                        self.templates = templates
                        logger.info("슬랙 메시지 템플릿 로드 완료", 
                                   template_count=len(self.templates))
                    else:
                        logger.error("notification.yaml에서 slack 템플릿을 찾을 수 없습니다")
                        self.templates = {}
            else:
                logger.error("notification.yaml 파일이 존재하지 않습니다")
                self.templates = {}
                
        except Exception as e:
            logger.error("메시지 템플릿 로드 중 오류 발생", error=str(e))
            self.templates = {}
    

    def send_error_alert(self, error: Exception, context: Dict[str, Any]) -> bool:
        """오류 알림 발송"""
        template_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "job_name": context.get("job_name", "Unknown"),
            "error_message": str(error),
            "error_details": context.get("error_details", str(error))
        }
        
        # 추가 컨텍스트 정보 포함
        template_data.update(context)
        
        # notification.yaml의 템플릿 사용, 없으면 빈 문자열
        message_text = self.templates.get("error_alert", "").format(**template_data) if self.templates.get("error_alert") else f"오류 발생: {template_data.get('error_message', 'Unknown error')}"
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.ERROR,
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
            "duration": result.duration or "알 수 없음"
        }
        
        # notification.yaml의 템플릿 사용, 없으면 기본 메시지
        message_text = self.templates.get(template_key, "").format(**template_data) if self.templates.get(template_key) else f"배치 작업 {'완료' if result.success else '실패'}: {result.job_name}"
        
        level = NotificationLevel.INFO if result.success else NotificationLevel.ERROR
        message = SlackMessage(
            text=message_text,
            level=level,
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
        
        # notification.yaml의 템플릿 사용, 없으면 기본 메시지
        message_text = self.templates.get("critical_alert", "").format(**template_data) if self.templates.get("critical_alert") else f"🔥 긴급: {message}"
        
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
        
        # notification.yaml의 템플릿 사용, 없으면 기본 메시지
        message_text = self.templates.get("api_health_warning", "").format(**template_data) if self.templates.get("api_health_warning") else f"⚠️ API 상태 경고: {api_name} - {status}"
        
        message = SlackMessage(
            text=message_text,
            level=NotificationLevel.WARNING,
            channel=self.slack_config.channel_id
        )
        
        return self._send_message(message)
    
    def _send_message(self, message: SlackMessage) -> bool:
        """슬랙 메시지 발송"""
        if not self.slack_config.enable_notifications:
            logger.debug("슬랙 알림이 config/notification.yaml에서 비활성화되어 있어 메시지를 발송하지 않습니다")
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

# 전역 슬랙 알림 서비스 인스턴스
slack_service = SlackNotificationService()
