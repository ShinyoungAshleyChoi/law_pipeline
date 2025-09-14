"""Kafka 통합 법제처 API 클라이언트"""
from typing import Optional, Dict, Any
from datetime import date, datetime
import uuid

from streaming.producer import LegalDataProducer
from streaming.models import EventType
from logging_config import get_logger

logger = get_logger(__name__)


class KafkaIntegratedAPIClient:
    """Kafka와 통합된 법제처 API 클라이언트"""

    def __init__(self):
        self.kafka_producer = LegalDataProducer()
        self._session_active = False

    async def start_session(self):
        """세션 시작 (Kafka Producer 시작)"""
        if not self._session_active:
            await self.kafka_producer.start()
            self._session_active = True
            logger.info("Kafka 통합 API 클라이언트 세션 시작")

    async def end_session(self):
        """세션 종료 (Kafka Producer 종료)"""
        if self._session_active:
            await self.kafka_producer.stop()
            self._session_active = False
            logger.info("Kafka 통합 API 클라이언트 세션 종료")

    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        await self.start_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.end_session()

    async def collect_and_publish_laws(self,
                                       last_sync_date: Optional[date] = None,
                                       batch_size: int = 50) -> Dict[str, Any]:
        """법령 데이터 수집 및 Kafka 발송"""
        if not self._session_active:
            raise RuntimeError("세션이 시작되지 않았습니다. start_session()을 먼저 호출하세요.")

        correlation_id = str(uuid.uuid4())
        job_id = f"kafka_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info("Kafka 통합 법령 수집 시작",
                    correlation_id=correlation_id,
                    last_sync_date=last_sync_date,
                    batch_size=batch_size)

        # 배치 시작 이벤트
        await self.kafka_producer.send_batch_status_event(
            job_id, "KAFKA_INTEGRATED", EventType.BATCH_STARTED
        )

        try:
            # Producer를 통한 데이터 수집 및 전송
            stats = await self.kafka_producer.collect_and_send_laws(
                last_sync_date=last_sync_date,
                correlation_id=correlation_id
            )

            # 성공적으로 완료된 경우
            if stats.get('failed_laws', 0) == 0:
                await self.kafka_producer.send_batch_status_event(
                    job_id, "KAFKA_INTEGRATED", EventType.BATCH_COMPLETED,
                    processed_count=stats.get('sent_laws', 0),
                    error_count=0
                )
            else:
                # 부분 실패
                await self.kafka_producer.send_batch_status_event(
                    job_id, "KAFKA_INTEGRATED", EventType.BATCH_FAILED,
                    processed_count=stats.get('sent_laws', 0),
                    error_count=stats.get('failed_laws', 0)
                )

            # 추가 통계 정보
            stats['correlation_id'] = correlation_id
            stats['job_id'] = job_id
            stats['kafka_integration'] = True

            return stats

        except Exception as e:
            # 배치 실패 이벤트
            await self.kafka_producer.send_batch_status_event(
                job_id, "KAFKA_INTEGRATED", EventType.BATCH_FAILED,
                error_count=1
            )

            logger.error("Kafka 통합 법령 수집 실패",
                         error=str(e),
                         correlation_id=correlation_id)
            raise

    async def health_check(self) -> Dict[str, Any]:
        """통합 헬스체크"""
        logger.info("통합 헬스체크 시작")

        # API 클라이언트 헬스체크
        api_health = self.api_client.health_check()

        # Kafka Producer 헬스체크
        kafka_health = {'status': 'not_started'}
        if self._session_active:
            kafka_health = await self.kafka_producer.health_check()

        # 전체 상태 결정
        overall_status = 'healthy'
        if not api_health.is_healthy or kafka_health.get('status') != 'healthy':
            overall_status = 'unhealthy'

        return {
            'overall_status': overall_status,
            'session_active': self._session_active,
            'api_client': {
                'status': 'healthy' if api_health.is_healthy else 'unhealthy',
                'response_time_ms': api_health.response_time_ms,
                'error_message': api_health.error_message
            },
            'kafka_producer': kafka_health,
            'timestamp': datetime.now().isoformat()
        }


# 전역 통합 클라이언트 인스턴스
kafka_integrated_client = KafkaIntegratedAPIClient()
