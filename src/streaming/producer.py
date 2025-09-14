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

from streaming.config import (kafka_config, Topics)
from streaming.models import (
    KafkaMessage, LawEvent, ContentEvent, ArticleEvent,
    BatchStatusEvent, EventType
)
from api.models import LawListItem, LawContent, LawArticle
from logging_config import get_logger

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
            future.add_callback(self._on_send_success, message=message, topic=topic)
            future.add_errback(self._on_send_error, message=message, topic=topic)

            # 결과 대기 (타임아웃 줄임)
            record_metadata = future.get(timeout=5)  # 10초 → 5초로 단축

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

            # Producer에서 전송하는 데이터 구조 로깅 (디버깅용)
            logger.info("Producer 전송 데이터", 
                       law_id=law.law_id,
                       data_keys=list(law_data.keys()),
                       data_sample=law_data)

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

    async def send_batch_status_event(self, job_id: str, job_type: str,
                                      event_type: EventType,
                                      processed_count: Optional[int] = None,
                                      error_count: Optional[int] = None,
                                      correlation_id: Optional[str] = None) -> bool:
        """배치 상태 이벤트 전송"""
        try:
            if event_type == EventType.BATCH_STARTED:
                event = BatchStatusEvent.create_batch_started(job_id, job_type)
            elif event_type == EventType.BATCH_COMPLETED:
                event = BatchStatusEvent.create_batch_completed(
                    job_id, job_type, processed_count or 0, error_count or 0
                )
            elif event_type == EventType.BATCH_FAILED:
                # 실패한 경우 처리된 수와 오류 수를 모두 기록
                event = BatchStatusEvent(
                    event_type=EventType.BATCH_FAILED,
                    job_id=job_id,
                    job_type=job_type,
                    processed_count=processed_count or 0,
                    error_count=error_count or 1,
                    correlation_id=correlation_id
                )
            else:
                # 기타 상태 (커스텀 처리)
                event = BatchStatusEvent(
                    event_type=event_type,
                    job_id=job_id,
                    job_type=job_type,
                    processed_count=processed_count,
                    error_count=error_count,
                    correlation_id=correlation_id
                )

            # 상관관계 ID 설정
            if correlation_id:
                event.correlation_id = correlation_id

            # 전송
            success = await self.send_message(Topics.BATCH_STATUS, event)

            if success:
                logger.info("배치 상태 이벤트 전송 성공",
                            job_id=job_id,
                            job_type=job_type,
                            event_type=event_type.value,
                            processed_count=processed_count,
                            error_count=error_count)
            else:
                logger.error("배치 상태 이벤트 전송 실패",
                             job_id=job_id,
                             job_type=job_type,
                             event_type=event_type.value)

            return success

        except Exception as e:
            logger.error("배치 상태 이벤트 전송 중 오류",
                         job_id=job_id,
                         job_type=job_type,
                         event_type=event_type.value,
                         error=str(e))
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Producer 헬스 체크"""
        try:
            if not self.producer:
                return {
                    'status': 'not_started',
                    'producer_active': False,
                    'message': 'Producer가 시작되지 않았습니다'
                }

            # Producer 메트릭 확인
            metrics = self.producer.metrics()

            # 연결 상태 확인 (브로커 연결 수)
            connection_count = metrics.get('producer-metrics', {}).get('connection-count', 0)

            # 전송 통계
            record_send_rate = metrics.get('producer-metrics', {}).get('record-send-rate', 0)

            # 오류 통계
            record_error_rate = metrics.get('producer-metrics', {}).get('record-error-rate', 0)

            # 상태 결정
            status = 'healthy'
            issues = []

            if connection_count == 0:
                status = 'unhealthy'
                issues.append('브로커 연결 없음')

            if record_error_rate > 0.1:  # 10% 이상 오류율
                status = 'degraded'
                issues.append(f'높은 오류율: {record_error_rate:.2%}')

            return {
                'status': status,
                'producer_active': True,
                'broker_connections': connection_count,
                'record_send_rate': record_send_rate,
                'record_error_rate': record_error_rate,
                'messages_sent': self._stats['messages_sent'],
                'messages_failed': self._stats['messages_failed'],
                'issues': issues,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error("Producer 헬스 체크 실패", error=str(e))
            return {
                'status': 'error',
                'producer_active': self.producer is not None,
                'error_message': str(e),
                'timestamp': datetime.now().isoformat()
            }

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

        # 배치 시작 이벤트 전송
        await producer.send_batch_status_event(
            job_id, "PRODUCER_CLI", EventType.BATCH_STARTED,
            correlation_id=args.correlation_id
        )

        try:
            # 데이터 수집 및 전송
            stats = await producer.collect_and_send_laws(
                last_sync_date=last_sync_date,
                correlation_id=args.correlation_id
            )

            # 배치 완료 이벤트 전송
            if stats.get('failed_laws', 0) == 0:
                await producer.send_batch_status_event(
                    job_id, "PRODUCER_CLI", EventType.BATCH_COMPLETED,
                    processed_count=stats.get('sent_laws', 0),
                    error_count=0,
                    correlation_id=args.correlation_id
                )
            else:
                await producer.send_batch_status_event(
                    job_id, "PRODUCER_CLI", EventType.BATCH_FAILED,
                    processed_count=stats.get('sent_laws', 0),
                    error_count=stats.get('failed_laws', 0),
                    correlation_id=args.correlation_id
                )

            # 결과 출력
            print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

        except Exception as e:
            # 배치 실패 이벤트 전송
            await producer.send_batch_status_event(
                job_id, "PRODUCER_CLI", EventType.BATCH_FAILED,
                error_count=1,
                correlation_id=args.correlation_id
            )

            logger.error("Producer CLI 실행 실패", error=str(e))
            raise


if __name__ == "__main__":
    asyncio.run(main())
