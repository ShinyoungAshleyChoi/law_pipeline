"""Kafka Producer - 법제처 API 데이터를 Kafka로 전송"""
import asyncio
import json
import time
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, date
from contextlib import asynccontextmanager

from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError
import structlog

from src.kafka.config import kafka_config, Topics
from src.kafka.models import (
    KafkaMessage, LawEvent, ContentEvent, ArticleEvent, 
    BatchStatusEvent, NotificationEvent, EventType
)
from src.api.client import api_client
from src.api.models import LawListItem, LawContent, LawArticle
from src.logging_config import get_logger

logger = get_logger(__name__)

class LegalDataProducer:
    """법제처 데이터 Kafka Producer"""
    
    def __init__(self):
        self.producer: Optional[KafkaProducer] = None
        self.config = kafka_config
        self._stats = {
            'messages_sent': 0,
            'messages_failed': 0,
            'bytes_sent': 0,
            'start_time': None
        }
        self._callbacks: Dict[str, List[Callable]] = {}
        
    async def start(self) -> None:
        """Producer 시작"""
        logger.info("Kafka Producer 시작 중...")
        
        try:
            # Producer 설정
            producer_config = {
                'bootstrap_servers': self.config.bootstrap_servers,
                'client_id': f"{self.config.client_id}-producer",
                'value_serializer': lambda v: json.dumps(v, ensure_ascii=False, default=str).encode('utf-8'),
                'key_serializer': lambda k: str(k).encode('utf-8') if k else None,
                **self.config.producer_config
            }
            
            self.producer = KafkaProducer(**producer_config)
            self._stats['start_time'] = time.time()
            
            logger.info("Kafka Producer 시작 완료", 
                       bootstrap_servers=self.config.bootstrap_servers)
            
        except Exception as e:
            logger.error("Kafka Producer 시작 실패", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Producer 중지"""
        if self.producer:
            logger.info("Kafka Producer 중지 중...")
            
            # 대기 중인 메시지 전송 완료 대기
            self.producer.flush(timeout=30)
            self.producer.close(timeout=30)
            
            self.producer = None
            
            # 통계 출력
            self._log_stats()
            logger.info("Kafka Producer 중지 완료")
    
    @asynccontextmanager
    async def session(self):
        """Producer 세션 컨텍스트 매니저"""
        await self.start()
        try:
            yield self
        finally:
            await self.stop()
    
    async def send_message(self, topic: str, message: KafkaMessage, 
                          partition_key: Optional[str] = None) -> bool:
        """메시지 전송"""
        if not self.producer:
            raise RuntimeError("Producer가 시작되지 않았습니다")
        
        try:
            # 파티션 키 결정
            key = partition_key or message.get_partition_key()
            
            # 메시지 직렬화
            value = message.to_dict()
            
            # 비동기 전송
            future = self.producer.send(topic, value=value, key=key)
            
            # 콜백 등록
            future.add_callback(self._on_send_success, message, topic)
            future.add_errback(self._on_send_error, message, topic)
            
            # 결과 대기 (타임아웃 있음)
            record_metadata = future.get(timeout=10)
            
            self._stats['messages_sent'] += 1
            self._stats['bytes_sent'] += len(json.dumps(value))
            
            logger.debug("메시지 전송 성공", 
                        topic=topic, 
                        partition=record_metadata.partition,
                        offset=record_metadata.offset,
                        event_id=message.event_id)
            
            return True
            
        except KafkaTimeoutError:
            logger.error("메시지 전송 타임아웃", 
                        topic=topic, 
                        event_id=message.event_id)
            self._stats['messages_failed'] += 1
            return False
            
        except KafkaError as e:
            logger.error("Kafka 전송 오류", 
                        topic=topic, 
                        event_id=message.event_id,
                        error=str(e))
            self._stats['messages_failed'] += 1
            return False
            
        except Exception as e:
            logger.error("메시지 전송 실패", 
                        topic=topic, 
                        event_id=message.event_id,
                        error=str(e))
            self._stats['messages_failed'] += 1
            return False
    
    def _on_send_success(self, record_metadata, message: KafkaMessage, topic: str):
        """전송 성공 콜백"""
        logger.debug("메시지 전송 성공 콜백", 
                    topic=topic,
                    partition=record_metadata.partition,
                    offset=record_metadata.offset,
                    event_id=message.event_id)
        
        # 등록된 콜백 실행
        for callback in self._callbacks.get('success', []):
            try:
                callback(message, record_metadata)
            except Exception as e:
                logger.warning("성공 콜백 실행 실패", error=str(e))
    
    def _on_send_error(self, exception, message: KafkaMessage, topic: str):
        """전송 실패 콜백"""
        logger.error("메시지 전송 실패 콜백", 
                    topic=topic,
                    event_id=message.event_id,
                    error=str(exception))
        
        # 등록된 콜백 실행
        for callback in self._callbacks.get('error', []):
            try:
                callback(message, exception)
            except Exception as e:
                logger.warning("오류 콜백 실행 실패", error=str(e))
    
    def register_callback(self, event_type: str, callback: Callable) -> None:
        """콜백 등록"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    async def send_law_event(self, law: LawListItem, correlation_id: Optional[str] = None) -> bool:
        """법령 이벤트 전송"""
        try:
            # 법령 데이터 직렬화
            law_data = {
                'law_id': law.law_id,
                'law_master_no': law.law_master_no,
                'law_name': law.law_name,
                'enforcement_date': law.enforcement_date.isoformat() if law.enforcement_date else None,
                'promulgation_date': law.promulgation_date.isoformat() if law.promulgation_date else None,
                'law_type': law.law_type,
                'ministry_name': law.ministry_name,
                'revision_type': law.revision_type
            }
            
            # 이벤트 생성
            event = LawEvent.create_updated_event(
                law_id=str(law.law_id),
                law_master_no=str(law.law_master_no),
                law_name=law.law_name,
                enforcement_date=law.enforcement_date,
                law_data=law_data,
                correlation_id=correlation_id
            )
            
            # 전송
            return await self.send_message(Topics.LAW_EVENTS, event)
            
        except Exception as e:
            logger.error("법령 이벤트 전송 실패", 
                        law_id=law.law_id,
                        error=str(e))
            return False
    
    async def collect_and_send_laws(self, last_sync_date: Optional[date] = None,
                                   correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """법령 수집 및 전송"""
        logger.info("법령 데이터 수집 및 전송 시작", last_sync_date=last_sync_date)
        
        stats = {
            'total_laws': 0,
            'sent_laws': 0,
            'failed_laws': 0,
            'start_time': datetime.now(),
            'errors': []
        }
        
        try:
            # 1. 법령 목록 수집
            laws = api_client.collect_law_list(last_sync_date)
            stats['total_laws'] = len(laws)
            
            logger.info("법령 목록 수집 완료", count=len(laws))
            
            # 2. 각 법령별로 처리
            for law in laws:
                try:
                    # 법령 정보 전송
                    if await self.send_law_event(law, correlation_id):
                        stats['sent_laws'] += 1
                    else:
                        stats['failed_laws'] += 1
                        continue
                    
                    # 진행률 로깅 (10개마다)
                    if stats['sent_laws'] % 10 == 0:
                        logger.info("법령 처리 진행률", 
                                   processed=stats['sent_laws'],
                                   total=stats['total_laws'],
                                   progress_pct=round((stats['sent_laws'] / stats['total_laws']) * 100, 1))
                
                except Exception as e:
                    logger.error("법령 처리 실패", 
                               law_id=law.law_id,
                               error=str(e))
                    stats['failed_laws'] += 1
                    stats['errors'].append(f"Law processing failed for law_id {law.law_id}: {str(e)}")
                    continue
            
            # 최종 통계
            stats['end_time'] = datetime.now()
            stats['duration_seconds'] = (stats['end_time'] - stats['start_time']).total_seconds()
            
            logger.info("법령 데이터 수집 및 전송 완료", 
                       sent_laws=stats['sent_laws'],
                       failed_laws=stats['failed_laws'],
                       duration_seconds=stats['duration_seconds'])
            
            return stats
            
        except Exception as e:
            logger.error("법령 데이터 수집 및 전송 실패", error=str(e))
            stats['errors'].append(f"Global error: {str(e)}")
            return stats
    
    def _log_stats(self) -> None:
        """통계 로깅"""
        if self._stats['start_time']:
            duration = time.time() - self._stats['start_time']
            
            logger.info("Producer 통계", 
                       messages_sent=self._stats['messages_sent'],
                       messages_failed=self._stats['messages_failed'],
                       bytes_sent=self._stats['bytes_sent'],
                       duration_seconds=round(duration, 2),
                       throughput_msg_per_sec=round(self._stats['messages_sent'] / duration, 2) if duration > 0 else 0)

# 전역 Producer 인스턴스
producer = LegalDataProducer()

async def main():
    """메인 함수 - CLI 실행용"""
    import argparse
    
    parser = argparse.ArgumentParser(description='법제처 데이터 Producer')
    parser.add_argument('--last-sync-date', type=str, 
                       help='마지막 동기화 날짜 (YYYY-MM-DD)')
    parser.add_argument('--correlation-id', type=str,
                       help='상관관계 ID')
    
    args = parser.parse_args()
    
    async with producer.session():
        # 데이터 수집 및 전송
        last_sync_date = None
        if args.last_sync_date:
            last_sync_date = datetime.strptime(args.last_sync_date, '%Y-%m-%d').date()
        
        # 배치 시작 알림
        job_id = f"producer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 데이터 수집 및 전송
        stats = await producer.collect_and_send_laws(
            last_sync_date=last_sync_date,
            correlation_id=args.correlation_id
        )
        
        # 결과 출력
        print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    asyncio.run(main())
