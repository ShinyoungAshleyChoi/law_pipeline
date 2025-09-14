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

from streaming.config import (kafka_config, Topics)
from streaming.models import (
    KafkaMessage, LawEvent, ContentEvent, ArticleEvent,
    BatchStatusEvent, NotificationEvent, EventType, MessageStatus
)
from database.repository import LegalDataRepository
from database.models import (
    LawList, LawContent, LawArticle, JobType, JobStatus
)
from notifications.slack_service import slack_service
from logging_config import get_logger

logger = get_logger(__name__)

class LegalDataConsumer:
    """법제처 데이터 Kafka Consumer"""
    
    def __init__(self, group_id: str = "legal-data-writers", target_db_host: str = "mysql-green"):
        self.consumer: Optional[KafkaConsumer] = None
        self.config = kafka_config
        self.group_id = group_id
        self.target_db_host = target_db_host  # 타겟 DB 호스트
        self.repository = LegalDataRepository(target_db_host=target_db_host)  # 타겟 DB 지정
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
                'consumer_timeout_ms': 10000,  # 10초 후 StopIteration 발생
                'session_timeout_ms': 30000,   # 30초 세션 타임아웃
                'heartbeat_interval_ms': 3000, # 3초 하트비트
                'max_poll_records': 10,        # 한 번에 최대 10개 메시지만
                'fetch_min_bytes': 1,          # 최소 1바이트만 있어도 반환
                'fetch_max_wait_ms': 1000,     # 최대 1초 대기
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
    
    async def consume_messages(self, max_messages: Optional[int] = None, timeout_seconds: int = 300) -> None:
        """메시지 소비 - 타임아웃과 빈 큐 감지 추가"""
        if not self.consumer or not self.running:
            raise RuntimeError("Consumer가 시작되지 않았습니다")
        
        logger.info("메시지 소비 시작", max_messages=max_messages, timeout_seconds=timeout_seconds)
        
        processed_count = 0
        empty_polls = 0
        max_empty_polls = 10  # 연속 빈 폴링 허용 횟수
        start_time = time.time()
        
        try:
            while self.running:
                # 최대 메시지 수 체크
                if max_messages and processed_count >= max_messages:
                    logger.info("최대 메시지 수 도달", processed=processed_count)
                    break
                
                # 타임아웃 체크
                if time.time() - start_time > timeout_seconds:
                    logger.info("타임아웃 도달", 
                               processed=processed_count, 
                               timeout_seconds=timeout_seconds)
                    break
                
                # poll 메서드로 메시지 가져오기 (타임아웃 설정)
                message_batch = self.consumer.poll(timeout_ms=5000)  # 5초 타임아웃
                
                if not message_batch:
                    empty_polls += 1
                    logger.info("빈 배치 폴링", empty_polls=empty_polls, max_empty_polls=max_empty_polls)
                    
                    if empty_polls >= max_empty_polls:
                        logger.info("연속 빈 폴링으로 컨슈밍 종료", 
                                   processed=processed_count,
                                   empty_polls=empty_polls)
                        break
                    
                    # 잠시 대기 후 재시도
                    await asyncio.sleep(1)
                    continue
                
                # 메시지가 있으면 빈 폴링 카운터 리셋
                empty_polls = 0
                
                # 배치 내 모든 메시지 처리
                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        if not self.running:
                            break
                        
                        if max_messages and processed_count >= max_messages:
                            logger.info("배치 처리 중 최대 메시지 수 도달", processed=processed_count)
                            break
                        
                        try:
                            await self._process_message(message)
                            processed_count += 1
                            
                            # 주기적으로 커밋
                            if processed_count % 10 == 0:
                                self.consumer.commit()
                                self._stats['messages_committed'] += 10
                                logger.info("주기적 커밋", processed=processed_count)
                            
                        except Exception as e:
                            logger.error("메시지 처리 실패",
                                       topic=message.topic,
                                       partition=message.partition,
                                       offset=message.offset,
                                       error=str(e))
                            
                            await self._handle_message_error(message, e)
                            self._stats['messages_failed'] += 1
                            continue
                    
                    if max_messages and processed_count >= max_messages:
                        break
                
                if max_messages and processed_count >= max_messages:
                    break
            
            # 최종 커밋
            if processed_count > 0:
                self.consumer.commit()
                logger.info("메시지 소비 완료", 
                           processed=processed_count,
                           duration=time.time() - start_time)
                
        except KeyboardInterrupt:
            logger.info("사용자 중단 요청")
            await self.stop()
        except Exception as e:
            logger.error("메시지 소비 중 오류", error=str(e))
            raise
    
    async def _process_message(self, message) -> None:
        """개별 메시지 처리"""
        try:
            logger.info("메시지 파싱 시작",
                        topic=message.topic,
                        partition=message.partition,
                        offset=message.offset,
                        key=message.key,
                        value_type=type(message.value).__name__)
            
            # 메시지 값이 올바른지 확인
            if message.value is None:
                logger.error("메시지 값이 None입니다", 
                           topic=message.topic, 
                           partition=message.partition, 
                           offset=message.offset)
                raise Exception("메시지 값이 None입니다")
            
            # 메시지 파싱
            try:
                kafka_message = KafkaMessage.from_dict(message.value)
                logger.info("메시지 파싱 성공", 
                           event_id=kafka_message.event_id,
                           event_type=kafka_message.event_type.value)
            except Exception as parse_error:
                logger.error("메시지 파싱 실패", 
                           topic=message.topic,
                           partition=message.partition,
                           offset=message.offset,
                           message_value=str(message.value)[:1000],  # 처음 1000자만
                           parse_error=str(parse_error))
                raise Exception(f"메시지 파싱 실패: {parse_error}")
            
            # 중복 처리 방지
            if kafka_message.event_id in self._processed_message_ids:
                logger.info("중복 메시지 스킵", event_id=kafka_message.event_id)
                return
            
            self._processed_message_ids.add(kafka_message.event_id)
            
            logger.info("메시지 처리 시작",
                        topic=message.topic,
                        event_id=kafka_message.event_id,
                        event_type=kafka_message.event_type.value,
                        data_available=kafka_message.data is not None)
            
            # 토픽별 처리
            if message.topic == Topics.LAW_EVENTS:
                logger.info("법령 이벤트 처리 시작")
                await self._process_law_event(kafka_message)
            elif message.topic == Topics.CONTENT_EVENTS:
                logger.info("콘텐츠 이벤트 처리 시작")
                await self._process_content_event(kafka_message)
            elif message.topic == Topics.ARTICLE_EVENTS:
                logger.info("조항 이벤트 처리 시작")
                await self._process_article_event(kafka_message)
            elif message.topic == Topics.BATCH_STATUS:
                logger.info("배치 상태 이벤트 처리 시작")
                await self._process_batch_status_event(kafka_message)
            elif message.topic == Topics.NOTIFICATIONS:
                logger.info("알림 이벤트 처리 시작")
                await self._process_notification_event(kafka_message)
            else:
                logger.warning("알 수 없는 토픽", topic=message.topic)
                return
            
            self._stats['messages_processed'] += 1
            self._stats['last_processed_time'] = time.time()
            
            logger.info("메시지 처리 완료",
                        event_id=kafka_message.event_id,
                        topic=message.topic)
                        
        except Exception as e:
            logger.error("메시지 처리 실패", 
                        topic=message.topic,
                        partition=message.partition,
                        offset=message.offset,
                        error=str(e),
                        error_type=type(e).__name__,
                        message_key=message.key,
                        message_value_preview=str(message.value)[:200] if message.value else 'None')
            raise
    
    async def _process_law_event(self, kafka_message: KafkaMessage) -> None:
        """법령 이벤트 처리"""
        try:
            logger.info("법령 이벤트 처리 시작", event_id=kafka_message.event_id)
            law_data = kafka_message.data
            
            # 원본 데이터 로깅
            logger.info("수신한 법령 데이터", 
                        event_id=kafka_message.event_id,
                        data_keys=list(law_data.keys()) if isinstance(law_data, dict) else type(law_data).__name__,
                        data_sample=str(law_data)[:500])  # 처음 500자만 로깅
            
            # 전체 raw 데이터 출력 (디버깅용)
            logger.info("RAW 법령 데이터 전체", 
                        event_id=kafka_message.event_id,
                        raw_data=law_data)
            
            # 법령 데이터 변환 - 실제 Mock API 응답 필드명 사용
            logger.info("법령 데이터 변환 시작")
            law_list = LawList(
                law_id=law_data.get('법령ID'),  # Mock 데이터의 실제 필드명
                law_name_korean=law_data.get('법령명'),
                enforcement_date=law_data.get('시행일자'),
                promulgation_date=law_data.get('공포일자'),
                law_type_name=law_data.get('법령구분'),
                ministry_name=law_data.get('소관부처')
            )
            
            logger.info("변환된 법령 데이터", 
                        law_id=law_list.law_id,
                        law_name=law_list.law_name_korean,
                        enforcement_date=law_list.enforcement_date,
                        law_type=law_list.law_type_name,
                        ministry=law_list.ministry_name)
            
            # 데이터베이스 저장
            logger.info("데이터베이스 저장 시작")
            with self.repository.transaction():
                logger.info("트랜잭션 내에서 저장 시도")
                success = self.repository.save_law_list(law_list)
                
                if success:
                    self._stats['laws_stored'] += 1
                    logger.info("법령 저장 성공", 
                               law_id=law_data.get('법령ID'),
                               event_id=kafka_message.event_id)
                else:
                    error_msg = f"법령 저장 실패 law_data={law_data}"
                    logger.error("법령 저장이 실패함", 
                               law_id=law_data.get('법령ID'),
                               event_id=kafka_message.event_id,
                               law_data_keys=list(law_data.keys()) if isinstance(law_data, dict) else 'not_dict')
                    raise Exception(error_msg)
                    
        except Exception as e:
            logger.error("법령 이벤트 처리 실패", 
                        event_id=kafka_message.event_id,
                        error=str(e),
                        error_type=type(e).__name__,
                        data_available=kafka_message.data is not None,
                        data_type=type(kafka_message.data).__name__ if kafka_message.data else 'None')
            raise
    
    async def _process_content_event(self, kafka_message: KafkaMessage) -> None:
        """법령 본문 이벤트 처리"""
        try:
            content_data = kafka_message.data
            
            # 법령 본문 데이터 변환 - 실제 Mock API 응답 필드명 사용  
            law_content = LawContent(
                law_id=content_data.get('법령ID'),  # Mock 데이터의 실제 필드명
                law_name_korean=content_data.get('법령명'),
                article_content=content_data.get('법령내용'),  # 'content'가 아니라 '법령내용'
                enforcement_date=content_data.get('시행일자'),
                promulgation_date=content_data.get('공포일자')
            )
            
            # 데이터베이스 저장
            with self.repository.transaction():
                success = self.repository.save_law_content(law_content)
                
                if success:
                    self._stats['contents_stored'] += 1
                    logger.info("법령 본문 저장 완료", law_id=content_data.get('law_id'))
                else:
                    raise Exception("법령 본문 저장 실패")
                    
        except Exception as e:
            logger.error("법령 본문 이벤트 처리 실패", error=str(e))
            raise
    
    async def _process_article_event(self, kafka_message: KafkaMessage) -> None:
        """법령 조항 이벤트 처리"""
        try:
            articles_data = kafka_message.data.get('articles', [])  # 실제 저장되는 필드명은 'articles'
            law_id = kafka_message.data.get('law_id')  # 영문 필드명으로 수정
            
            # 데이터베이스 저장
            with self.repository.transaction():
                stored_count = 0
                
                for article_data in articles_data:
                    law_article = LawArticle(
                        law_key=law_id,  # 법령ID를 law_key로 사용
                        law_id=law_id,
                        article_no=article_data.get('article_no', ''),  # 영문 필드명으로 수정
                        article_title=article_data.get('article_title', ''),  # 영문 필드명으로 수정
                        article_content=article_data.get('article_content', '')  # 영문 필드명으로 수정
                    )
                    
                    if self.repository.save_law_article(law_article):
                        stored_count += 1
                    else:
                        logger.warning("조항 저장 실패", 
                                     law_id=law_id,
                                     article_no=article_data.get('article_no'))
                
                self._stats['articles_stored'] += stored_count
                logger.info("법령 조항 저장 완료", 
                           law_id=law_id,
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
            
            logger.info("알림 이벤트 처리 완료", 
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
