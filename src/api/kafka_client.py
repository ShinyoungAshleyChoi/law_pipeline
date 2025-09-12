"""Kafka 통합 법제처 API 클라이언트"""
from typing import Optional, Dict, Any, List
from datetime import date, datetime
import uuid

from .client import api_client, LegalAPIClient
from ..kafka.producer import LegalDataProducer
from ..kafka.models import EventType
from ..logging_config import get_logger

logger = get_logger(__name__)

class KafkaIntegratedAPIClient:
    """Kafka와 통합된 법제처 API 클라이언트"""
    
    def __init__(self):
        self.api_client = api_client
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
                
                # 성공 알림
                await self.kafka_producer.send_notification_event(
                    title="법제처 데이터 수집 완료",
                    message=f"처리된 법령: {stats.get('sent_laws', 0)}개",
                    severity="info"
                )
            else:
                # 부분 실패
                await self.kafka_producer.send_batch_status_event(
                    job_id, "KAFKA_INTEGRATED", EventType.BATCH_FAILED,
                    processed_count=stats.get('sent_laws', 0),
                    error_count=stats.get('failed_laws', 0)
                )
                
                # 오류 알림
                await self.kafka_producer.send_notification_event(
                    title="법제처 데이터 수집 부분 실패",
                    message=f"성공: {stats.get('sent_laws', 0)}개, 실패: {stats.get('failed_laws', 0)}개",
                    severity="warning"
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
            
            # 오류 알림
            await self.kafka_producer.send_notification_event(
                title="법제처 데이터 수집 실패",
                message=f"오류: {str(e)}",
                severity="error"
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
    
    # 기존 API Client 메서드들을 프록시
    def collect_law_list(self, last_sync_date: Optional[date] = None):
        """법령 목록 조회 (기존 API 메서드)"""
        return self.api_client.collect_law_list(last_sync_date)
    
    def collect_law_content(self, law_id: str):
        """법령 본문 조회 (기존 API 메서드)"""
        return self.api_client.collect_law_content(law_id)
    
    def collect_law_articles(self, law_master_no: str):
        """법령 조항 조회 (기존 API 메서드)"""
        return self.api_client.collect_law_articles(law_master_no)
    
    def collect_incremental_updates(self, last_sync_date: date):
        """증분 업데이트 조회 (기존 API 메서드)"""
        return self.api_client.collect_incremental_updates(last_sync_date)

# 전역 통합 클라이언트 인스턴스
kafka_integrated_client = KafkaIntegratedAPIClient()

async def main():
    """CLI 실행용 메인 함수"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Kafka 통합 법제처 API 클라이언트')
    parser.add_argument('--action', choices=['collect', 'health'], default='collect',
                       help='실행할 작업')
    parser.add_argument('--last-sync-date', type=str,
                       help='마지막 동기화 날짜 (YYYY-MM-DD)')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='배치 크기')
    
    args = parser.parse_args()
    
    async with kafka_integrated_client:
        if args.action == 'health':
            # 헬스체크
            health = await kafka_integrated_client.health_check()
            print(json.dumps(health, indent=2, ensure_ascii=False, default=str))
            
        elif args.action == 'collect':
            # 데이터 수집
            last_sync_date = None
            if args.last_sync_date:
                last_sync_date = datetime.strptime(args.last_sync_date, '%Y-%m-%d').date()
            
            stats = await kafka_integrated_client.collect_and_publish_laws(
                last_sync_date=last_sync_date,
                batch_size=args.batch_size
            )
            
            print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
