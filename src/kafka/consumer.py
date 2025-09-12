"""Kafka Consumer - Kafka 메시지를 받아 데이터베이스에 저장"""
import asyncio
import json
import time
import signal
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from contextlib import asynccontextmanager

from kafka import KafkaConsumer
from kafka.errors import KafkaError, CommitFailedError
import structlog

from .config import kafka_config, Topics
from .models import (
    KafkaMessage, LawEvent, ContentEvent, ArticleEvent,
    BatchStatusEvent, NotificationEvent, EventType, MessageStatus
)
from ..database.repository import LegalDataRepository
from ..database.models import (
    LawList, LawContent, LawArticle, JobType, JobStatus
)
from ..notifications.slack_service import slack_service
from ..logging_config import get_logger

logger = get_logger(__name__)

class LegalDataConsumer:
    """법제처 데이터 Kafka Consumer"""
    
    def __init__(self, group_id: str = "legal-data-writers"):
        self.consumer: Optional[KafkaConsumer] = None
        self.config = kafka_config
        self.group_id = group_id
        self.repository = LegalDataRepository()
        self.running = False
        self._stats = {
            'messages_processed': 0,
            'messages_failed': 0,
            'messages_committed': 0,
            'laws_stored': 0,
            'contents_stored': 0,
            'articles_stored': 0,
            'start_time': None,
            'last_processed_time': None
        }
        self._callbacks: Dict[str, List[Callable]] = {}
        self._processed_message_ids = set()  # 중복 처리 방지
    
    async def start(self, topics: List[str] = None) -> None:
        """Consumer 시작"""
        if topics is None:
            topics = Topics.event_topics()
        
        logger.info("Kafka Consumer 시작 중...", topics=topics, group_id=self.group_id)
        
        try:
            # Consumer 설정
            consumer_config = {
                'bootstrap_servers': self.config.bootstrap_servers,
                'client_id': f"{self.config.client_id}-consumer",
                'group_id': self.group_id,
                'value_deserializer': lambda m: json.loads(m.decode('utf-8')),
                'key_deserializer': lambda m: m.decode('utf-8') if m else None,
                **self.config.consumer_config
            }
            
            self.consumer = KafkaConsumer(*topics, **consumer_config)
            self.running = True
            self._stats['start_time'] = time.time()
            
            logger.info("Kafka Consumer 시작 완료",
                       bootstrap_servers=self.config.bootstrap_servers,
                       topics=topics)
            
        except Exception as e:
            logger.error("Kafka Consumer 시작 실패", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Consumer 중지"""
        if self.consumer and self.running:
            logger.info("Kafka Consumer 중지 중...")
            
            self.running = False
            
            # 마지막 커밋
            try:
                self.consumer.commit()
                logger.info("최종 커밋 완료")
            except Exception as e:
                logger.warning("최종 커밋 실패", error=str(e))
            
            self.consumer.close()
            self.consumer = None
            
            # 통계 출력
            self._log_stats()
            logger.info("Kafka Consumer 중지 완료")
    
    @asynccontextmanager
    async def session(self, topics: List[str] = None):
        """Consumer 세션 컨텍스트 매니저"""
        await self.start(topics)
        try:
            yield self
        finally:
            await self.stop()
    
    async def consume_messages(self, max_messages: Optional[int] = None) -> None:
        """메시지 소비"""
        if not self.consumer or not self.running:
            raise RuntimeError("Consumer가 시작되지 않았습니다")
        
        logger.info("메시지 소비 시작", max_messages=max_messages)
        
        processed_count = 0
        
        try:
            for message in self.consumer:
                if not self.running:
                    break
                
                if max_messages and processed_count >= max_messages:
                    logger.info("최대 메시지 수 도달", processed=processed_count)
                    break
                
                try:
                    await self._process_message(message)
                    processed_count += 1
                    
                    # 주기적으로 커밋
                    if processed_count % 10 == 0:
                        self.consumer.commit()
                        self._stats['messages_committed'] += 10
                        logger.debug("주기적 커밋", processed=processed_count)
                    
                except Exception as e:
                    logger.error("메시지 처리 실패",
                               topic=message.topic,
                               partition=message.partition,
                               offset=message.offset,
                               error=str(e))
                    
                    await self._handle_message_error(message, e)
                    self._stats['messages_failed'] += 1
                    continue
            
            # 최종 커밋
            if processed_count > 0:
                self.consumer.commit()
                logger.info("메시지 소비 완료", processed=processed_count)
                
        except KeyboardInterrupt:
            logger.info("사용자 중단 요청")
            await self.stop()
        except Exception as e:
            logger.error("메시지 소비 중 오류", error=str(e))
            raise
    
    async def _process_message(self, message) -> None:
        """개별 메시지 처리"""
        try:
            # 메시지 파싱
            kafka_message = KafkaMessage.from_dict(message.value)
            
            # 중복 처리 방지
            if kafka_message.event_id in self._processed_message_ids:
                logger.debug("중복 메시지 스킵", event_id=kafka_message.event_id)
                return
            
            self._processed_message_ids.add(kafka_message.event_id)
            
            logger.debug("메시지 처리 시작",
                        topic=message.topic,
                        event_id=kafka_message.event_id,
                        event_type=kafka_message.event_type.value)
            
            # 토픽별 처리
            if message.topic == Topics.LAW_EVENTS:
                await self._process_law_event(kafka_message)
            elif message.topic == Topics.CONTENT_EVENTS:
                await self._process_content_event(kafka_message)
            elif message.topic == Topics.ARTICLE_EVENTS:
                await self._process_article_event(kafka_message)
            elif message.topic == Topics.BATCH_STATUS:
                await self._process_batch_status_event(kafka_message)
            elif message.topic == Topics.NOTIFICATIONS:
                await self._process_notification_event(kafka_message)
            else:
                logger.warning("알 수 없는 토픽", topic=message.topic)
                return
            
            self._stats['messages_processed'] += 1
            self._stats['last_processed_time'] = time.time()
            
            logger.debug("메시지 처리 완료",
                        event_id=kafka_message.event_id)
                        
        except Exception as e:
            logger.error("메시지 처리 실패", error=str(e))
            raise
    
    async def _process_law_event(self, kafka_message: KafkaMessage) -> None:
        """법령 이벤트 처리"""
        try:
            law_data = kafka_message.data
            
            # 법령 데이터 변환
            law_list = LawList(
                law_id=law_data.get('law_id'),
                law_serial_no=law_data.get('law_master_no'),  # 매핑
                law_name_korean=law_data.get('law_name'),
                enforcement_date=int(law_data.get('enforcement_date', '').replace('-', '')) if law_data.get('enforcement_date') else None,
                promulgation_date=int(law_data.get('promulgation_date', '').replace('-', '')) if law_data.get('promulgation_date') else None,
                law_type_name=law_data.get('law_type'),
                ministry_name=law_data.get('ministry_name'),
                revision_type=law_data.get('revision_type'),
                created_at=datetime.now()
            )
            
            # 데이터베이스 저장
            with self.repository.transaction():
                success = self.repository.save_law_list(law_list)
                
                if success:
                    self._stats['laws_stored'] += 1
                    logger.debug("법령 저장 완료", law_id=law_data.get('law_id'))
                else:
                    raise Exception("법령 저장 실패")
                    
        except Exception as e:
            logger.error("법령 이벤트 처리 실패", error=str(e))
            raise
    
    async def _process_content_event(self, kafka_message: KafkaMessage) -> None:
        """법령 본문 이벤트 처리"""
        try:
            content_data = kafka_message.data
            
            # 법령 본문 데이터 변환
            law_content = LawContent(
                law_id=content_data.get('law_id'),
                law_name_korean=content_data.get('law_name'),
                article_content=content_data.get('content'),
                enforcement_date=int(content_data.get('enforcement_date', '').replace('-', '')) if content_data.get('enforcement_date') else None,
                law_type=content_data.get('law_type'),
                created_at=datetime.now()
            )
            
            # 데이터베이스 저장
            with self.repository.transaction():
                success = self.repository.save_law_content(law_content)
                
                if success:
                    self._stats['contents_stored'] += 1
                    logger.debug("법령 본문 저장 완료", law_id=content_data.get('law_id'))
                else:
                    raise Exception("법령 본문 저장 실패")
                    
        except Exception as e:
            logger.error("법령 본문 이벤트 처리 실패", error=str(e))
            raise
    
    async def _process_article_event(self, kafka_message: KafkaMessage) -> None:
        """법령 조항 이벤트 처리"""
        try:
            articles_data = kafka_message.data.get('articles', [])
            
            # 데이터베이스 저장
            with self.repository.transaction():
                stored_count = 0
                
                for article_data in articles_data:
                    law_article = LawArticle(
                        law_key=article_data.get('law_id'),
                        law_id=article_data.get('law_id'),
                        law_name_korean=article_data.get('law_name'),
                        article_no=article_data.get('article_no'),
                        article_title=article_data.get('article_title'),
                        article_content=article_data.get('article_content'),
                        paragraph_no=article_data.get('paragraph_no'),
                        paragraph_content=article_data.get('paragraph_content'),
                        item_no=article_data.get('item_no'),
                        item_content=article_data.get('item_content'),
                        created_at=datetime.now()
                    )
                    
                    if self.repository.save_law_article(law_article):
                        stored_count += 1
                    else:
                        logger.warning("조항 저장 실패", 
                                     law_id=article_data.get('law_id'),
                                     article_no=article_data.get('article_no'))
                
                self._stats['articles_stored'] += stored_count
                logger.debug("법령 조항 저장 완료", 
                           law_id=kafka_message.data.get('law_id'),
                           stored_count=stored_count)
                    
        except Exception as e:
            logger.error("법령 조항 이벤트 처리 실패", error=str(e))
            raise
    
    async def _process_batch_status_event(self, kafka_message: KafkaMessage) -> None:
        """배치 상태 이벤트 처리"""
        try:
            batch_data = kafka_message.data
            job_id = batch_data.get('job_id')
            job_type = batch_data.get('job_type')
            event_type = kafka_message.event_type
            
            logger.info("배치 상태 이벤트 처리", 
                       job_id=job_id,
                       job_type=job_type,
                       event_type=event_type.value)
                    
        except Exception as e:
            logger.error("배치 상태 이벤트 처리 실패", error=str(e))
            raise
    
    async def _process_notification_event(self, kafka_message: KafkaMessage) -> None:
        """알림 이벤트 처리"""
        try:
            notification_data = kafka_message.data
            title = notification_data.get('title')
            message = notification_data.get('message')
            severity = notification_data.get('severity', 'info')
            channels = notification_data.get('channels', ['slack'])
            
            # Slack 알림 전송
            if 'slack' in channels:
                if severity == 'error':
                    slack_service.send_error_alert(
                        title=title,
                        message=message,
                        context={'kafka_event_id': kafka_message.event_id}
                    )
                else:
                    slack_service.send_info_message(
                        title=title,
                        message=message
                    )
            
            logger.debug("알림 이벤트 처리 완료", 
                        title=title,
                        severity=severity)
                    
        except Exception as e:
            logger.error("알림 이벤트 처리 실패", error=str(e))
            # 알림 실패는 전체 처리를 중단시키지 않음
            pass
    
    async def _handle_message_error(self, message, error: Exception) -> None:
        """메시지 처리 오류 핸들링"""
        try:
            # 오류 메시지를 DLQ로 전송
            dlq_message = {
                'original_topic': message.topic,
                'original_partition': message.partition,
                'original_offset': message.offset,
                'original_key': message.key,
                'original_value': message.value,
                'error_message': str(error),
                'error_timestamp': datetime.now().isoformat(),
                'consumer_group': self.group_id
            }
            
            # 실제로는 별도 Producer를 통해 DLQ로 전송해야 함
            logger.error("메시지를 DLQ로 전송", 
                        topic=message.topic,
                        error=str(error))
                    
        except Exception as e:
            logger.error("오류 핸들링 실패", error=str(e))
    
    def _log_stats(self) -> None:
        """통계 로깅"""
        if self._stats['start_time']:
            duration = time.time() - self._stats['start_time']
            
            logger.info("Consumer 통계",
                       messages_processed=self._stats['messages_processed'],
                       messages_failed=self._stats['messages_failed'],
                       laws_stored=self._stats['laws_stored'],
                       contents_stored=self._stats['contents_stored'],
                       articles_stored=self._stats['articles_stored'],
                       duration_seconds=round(duration, 2))

# 전역 Consumer 인스턴스
consumer = LegalDataConsumer()

async def main():
    """메인 함수 - CLI 실행용"""
    import argparse
    
    parser = argparse.ArgumentParser(description='법제처 데이터 Consumer')
    parser.add_argument('--group-id', type=str, default='legal-data-writers',
                       help='Consumer 그룹 ID')
    parser.add_argument('--topics', nargs='*', default=None,
                       help='구독할 토픽 목록')
    parser.add_argument('--max-messages', type=int, default=None,
                       help='최대 처리 메시지 수')
    
    args = parser.parse_args()
    
    # Consumer 인스턴스 생성
    consumer_instance = LegalDataConsumer(group_id=args.group_id)
    
    # 시그널 핸들러 등록 (Graceful Shutdown)
    def signal_handler(signum, frame):
        logger.info("종료 시그널 수신", signal=signum)
        consumer_instance.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 메시지 소비 시작
    async with consumer_instance.session(args.topics):
        logger.info("Consumer 시작", 
                   group_id=args.group_id,
                   topics=args.topics or Topics.event_topics(),
                   max_messages=args.max_messages)
        
        await consumer_instance.consume_messages(max_messages=args.max_messages)
        
        logger.info("Consumer 종료")

if __name__ == "__main__":
    asyncio.run(main())
