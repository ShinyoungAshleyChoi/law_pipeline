"""Kafka 메시지 모델"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any, Union
from enum import Enum
import uuid
import json

class EventType(Enum):
    """이벤트 타입"""
    LAW_CREATED = "LAW_CREATED"
    LAW_UPDATED = "LAW_UPDATED" 
    LAW_DELETED = "LAW_DELETED"
    
    CONTENT_CREATED = "CONTENT_CREATED"
    CONTENT_UPDATED = "CONTENT_UPDATED"
    CONTENT_DELETED = "CONTENT_DELETED"
    
    ARTICLE_CREATED = "ARTICLE_CREATED"
    ARTICLE_UPDATED = "ARTICLE_UPDATED"
    ARTICLE_DELETED = "ARTICLE_DELETED"
    
    BATCH_STARTED = "BATCH_STARTED"
    BATCH_COMPLETED = "BATCH_COMPLETED"
    BATCH_FAILED = "BATCH_FAILED"

class MessageStatus(Enum):
    """메시지 상태"""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"

@dataclass
class KafkaMessage:
    """기본 Kafka 메시지 구조"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.LAW_UPDATED
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "legal-data-pipeline"
    version: str = "1.0"
    
    # 메시지 메타데이터
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    message_status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    
    # 페이로드 (하위 클래스에서 구현)
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source,
            'version': self.version,
            'correlation_id': self.correlation_id,
            'causation_id': self.causation_id,
            'message_status': self.message_status.value,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'data': self.data
        }
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KafkaMessage':
        """딕셔너리에서 생성"""
        return cls(
            event_id=data.get('event_id', str(uuid.uuid4())),
            event_type=EventType(data.get('event_type', EventType.LAW_UPDATED.value)),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            source=data.get('source', 'legal-data-pipeline'),
            version=data.get('version', '1.0'),
            correlation_id=data.get('correlation_id'),
            causation_id=data.get('causation_id'),
            message_status=MessageStatus(data.get('message_status', MessageStatus.PENDING.value)),
            retry_count=data.get('retry_count', 0),
            max_retries=data.get('max_retries', 3),
            data=data.get('data')
        )
    
    @classmethod  
    def from_json(cls, json_str: str) -> 'KafkaMessage':
        """JSON 문자열에서 생성"""
        return cls.from_dict(json.loads(json_str))
    
    def get_partition_key(self) -> str:
        """파티션 키 생성 (하위 클래스에서 오버라이드)"""
        return self.event_id
    
    def is_retryable(self) -> bool:
        """재시도 가능 여부"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self) -> None:
        """재시도 횟수 증가"""
        self.retry_count += 1
        if self.retry_count >= self.max_retries:
            self.message_status = MessageStatus.FAILED
        else:
            self.message_status = MessageStatus.RETRY

@dataclass
class LawEvent(KafkaMessage):
    """법령 이벤트 메시지"""
    law_id: Optional[str] = None
    law_master_no: Optional[str] = None
    law_name: Optional[str] = None
    enforcement_date: Optional[date] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.data is None:
            self.data = {}
        
        # 법령 정보를 data에 저장
        if self.law_id:
            self.data['law_id'] = self.law_id
        if self.law_master_no:
            self.data['law_master_no'] = self.law_master_no
        if self.law_name:
            self.data['law_name'] = self.law_name
        if self.enforcement_date:
            self.data['enforcement_date'] = self.enforcement_date.isoformat()
    
    def get_partition_key(self) -> str:
        """법령ID를 파티션 키로 사용"""
        return self.law_id or self.event_id
    
    @classmethod
    def create_updated_event(cls, law_id: str, law_master_no: str, law_name: str, 
                           enforcement_date: date, law_data: Dict[str, Any],
                           correlation_id: Optional[str] = None) -> 'LawEvent':
        """법령 업데이트 이벤트 생성"""
        return cls(
            event_type=EventType.LAW_UPDATED,
            law_id=law_id,
            law_master_no=law_master_no, 
            law_name=law_name,
            enforcement_date=enforcement_date,
            correlation_id=correlation_id,
            data=law_data
        )

@dataclass
class ContentEvent(KafkaMessage):
    """법령 본문 이벤트 메시지"""
    law_id: Optional[str] = None
    content_size: Optional[int] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.data is None:
            self.data = {}
        
        if self.law_id:
            self.data['law_id'] = self.law_id
        if self.content_size:
            self.data['content_size'] = self.content_size
    
    def get_partition_key(self) -> str:
        """법령ID를 파티션 키로 사용"""
        return self.law_id or self.event_id
    
    @classmethod
    def create_updated_event(cls, law_id: str, content_data: Dict[str, Any],
                           correlation_id: Optional[str] = None) -> 'ContentEvent':
        """법령 본문 업데이트 이벤트 생성"""
        content_size = len(str(content_data.get('content', '')))
        
        return cls(
            event_type=EventType.CONTENT_UPDATED,
            law_id=law_id,
            content_size=content_size,
            correlation_id=correlation_id,
            data=content_data
        )

@dataclass
class ArticleEvent(KafkaMessage):
    """법령 조항 이벤트 메시지"""
    law_id: Optional[str] = None
    law_master_no: Optional[str] = None
    article_no: Optional[int] = None
    article_count: Optional[int] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.data is None:
            self.data = {}
        
        if self.law_id:
            self.data['law_id'] = self.law_id
        if self.law_master_no:
            self.data['law_master_no'] = self.law_master_no
        if self.article_no:
            self.data['article_no'] = self.article_no
        if self.article_count:
            self.data['article_count'] = self.article_count
    
    def get_partition_key(self) -> str:
        """법령마스터번호를 파티션 키로 사용"""
        return self.law_master_no or self.law_id or self.event_id
    
    @classmethod
    def create_updated_event(cls, law_id: str, law_master_no: str, 
                           articles_data: list, correlation_id: Optional[str] = None) -> 'ArticleEvent':
        """조항 업데이트 이벤트 생성"""
        return cls(
            event_type=EventType.ARTICLE_UPDATED,
            law_id=law_id,
            law_master_no=law_master_no,
            article_count=len(articles_data),
            correlation_id=correlation_id,
            data={'articles': articles_data}
        )

@dataclass
class BatchStatusEvent(KafkaMessage):
    """배치 작업 상태 이벤트"""
    job_id: Optional[str] = None
    job_type: Optional[str] = None
    processed_count: Optional[int] = None
    error_count: Optional[int] = None
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.data is None:
            self.data = {}
        
        if self.job_id:
            self.data['job_id'] = self.job_id
        if self.job_type:
            self.data['job_type'] = self.job_type
        if self.processed_count is not None:
            self.data['processed_count'] = self.processed_count
        if self.error_count is not None:
            self.data['error_count'] = self.error_count
    
    def get_partition_key(self) -> str:
        """작업ID를 파티션 키로 사용"""
        return self.job_id or self.event_id
    
    @classmethod
    def create_batch_started(cls, job_id: str, job_type: str) -> 'BatchStatusEvent':
        """배치 시작 이벤트 생성"""
        return cls(
            event_type=EventType.BATCH_STARTED,
            job_id=job_id,
            job_type=job_type,
            processed_count=0,
            error_count=0
        )
    
    @classmethod 
    def create_batch_completed(cls, job_id: str, job_type: str, 
                             processed_count: int, error_count: int) -> 'BatchStatusEvent':
        """배치 완료 이벤트 생성"""
        return cls(
            event_type=EventType.BATCH_COMPLETED,
            job_id=job_id,
            job_type=job_type,
            processed_count=processed_count,
            error_count=error_count
        )

@dataclass
class NotificationEvent(KafkaMessage):
    """알림 이벤트"""
    title: Optional[str] = None
    message: Optional[str] = None
    severity: str = "info"  # info, warning, error
    channels: list = field(default_factory=lambda: ["slack"])
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.data is None:
            self.data = {}
        
        self.data.update({
            'title': self.title,
            'message': self.message, 
            'severity': self.severity,
            'channels': self.channels
        })
    
    @classmethod
    def create_error_alert(cls, title: str, message: str, 
                          correlation_id: Optional[str] = None) -> 'NotificationEvent':
        """오류 알림 이벤트 생성"""
        return cls(
            title=title,
            message=message,
            severity="error",
            channels=["slack"],
            correlation_id=correlation_id
        )
