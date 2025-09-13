"""알림 시스템 모듈"""

from .slack_service import SlackNotificationService, NotificationLevel, BatchResult
from .utils import (
    notify_error,
    notify_batch_failure,
    notify_batch_success,
    notify_critical,
    notify_api_error,
    notify_database_error,
    notify_validation_error,
    notify_system_error,
    with_error_notification,
    with_batch_notification
)

# 전역 슬랙 알림 서비스 인스턴스
slack_service = SlackNotificationService()

__all__ = [
    'SlackNotificationService',
    'slack_service',
    'NotificationLevel',
    'BatchResult',
    'notify_error',
    'notify_batch_failure',
    'notify_batch_success',
    'notify_critical',
    'notify_api_error',
    'notify_database_error',
    'notify_validation_error',
    'notify_system_error',
    'with_error_notification',
    'with_batch_notification'
]