"""Kafka 설정"""
import os
from typing import Dict, Any, List
from dataclasses import dataclass

@dataclass
class KafkaConfig:
    """Kafka 설정 클래스"""
    bootstrap_servers: List[str]
    client_id: str = "legal-data-pipeline"
    
    # Producer 설정
    producer_config: Dict[str, Any] = None
    
    # Consumer 설정  
    consumer_config: Dict[str, Any] = None
    
    # 토픽 설정
    topic_config: Dict[str, Dict[str, Any]] = None
    
    def __post_init__(self):
        """기본 설정 초기화"""
        if self.producer_config is None:
            self.producer_config = {
                'acks': 'all',  # 모든 replica 확인
                'retries': 3,
                'batch_size': 16384,
                'linger_ms': 100,  # 100ms 대기 후 전송
                'buffer_memory': 33554432,  # 32MB
                'compression_type': 'lz4',
                'max_in_flight_requests_per_connection': 5,
                'enable_idempotence': True,  # 중복 방지
                'request_timeout_ms': 30000,
                'delivery_timeout_ms': 120000,
            }
        
        if self.consumer_config is None:
            self.consumer_config = {
                'group_id': 'legal-data-writers',
                'enable_auto_commit': False,  # 수동 커밋
                'auto_offset_reset': 'earliest',
                'max_poll_records': 100,
                'session_timeout_ms': 30000,
                'heartbeat_interval_ms': 3000,
                'max_poll_interval_ms': 300000,  # 5분
                'fetch_min_bytes': 1024,
                'fetch_max_wait_ms': 500,
                'isolation_level': 'read_committed',
            }
        
        if self.topic_config is None:
            self.topic_config = {
                'legal-law-events': {
                    'partitions': 6,
                    'replication_factor': 3,
                    'key_serializer': 'str',
                    'value_serializer': 'json'
                },
                'legal-content-events': {
                    'partitions': 4, 
                    'replication_factor': 3,
                    'key_serializer': 'str',
                    'value_serializer': 'json'
                },
                'legal-article-events': {
                    'partitions': 8,
                    'replication_factor': 3,
                    'key_serializer': 'str', 
                    'value_serializer': 'json'
                },
                'legal-batch-status': {
                    'partitions': 1,
                    'replication_factor': 3,
                    'key_serializer': 'str',
                    'value_serializer': 'json'
                },
                'legal-notifications': {
                    'partitions': 2,
                    'replication_factor': 3,
                    'key_serializer': 'str',
                    'value_serializer': 'json'
                },
                'legal-dlq': {
                    'partitions': 3,
                    'replication_factor': 3, 
                    'key_serializer': 'str',
                    'value_serializer': 'json'
                }
            }

def get_kafka_config() -> KafkaConfig:
    """환경 변수에서 Kafka 설정 로드"""
    
    # Bootstrap servers 설정
    bootstrap_servers_str = os.getenv(
        'KAFKA_BOOTSTRAP_SERVERS',
        'localhost:9092,localhost:9093,localhost:9094'
    )
    bootstrap_servers = [server.strip() for server in bootstrap_servers_str.split(',')]
    
    # Client ID 설정
    client_id = os.getenv('KAFKA_CLIENT_ID', 'legal-data-pipeline')
    
    return KafkaConfig(
        bootstrap_servers=bootstrap_servers,
        client_id=client_id
    )

# 전역 설정 인스턴스
kafka_config = get_kafka_config()

# 토픽명 상수
class Topics:
    LAW_EVENTS = 'legal-law-events'
    CONTENT_EVENTS = 'legal-content-events'  
    ARTICLE_EVENTS = 'legal-article-events'
    BATCH_STATUS = 'legal-batch-status'
    NOTIFICATIONS = 'legal-notifications'
    DLQ = 'legal-dlq'
    
    # CDC 토픽들
    CDC_LAWS = 'legal-cdc-laws'
    CDC_CONTENT = 'legal-cdc-content'
    CDC_ARTICLES = 'legal-cdc-articles'
    
    @classmethod
    def all_topics(cls) -> List[str]:
        """모든 토픽 목록 반환"""
        return [
            cls.LAW_EVENTS,
            cls.CONTENT_EVENTS,
            cls.ARTICLE_EVENTS,
            cls.BATCH_STATUS,
            cls.NOTIFICATIONS,
            cls.DLQ,
            cls.CDC_LAWS,
            cls.CDC_CONTENT,
            cls.CDC_ARTICLES
        ]
    
    @classmethod
    def event_topics(cls) -> List[str]:
        """이벤트 토픽들만 반환"""
        return [
            cls.LAW_EVENTS,
            cls.CONTENT_EVENTS,
            cls.ARTICLE_EVENTS
        ]
