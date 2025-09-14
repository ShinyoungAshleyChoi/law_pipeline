"""
Kafka 기반 법제처 API 데이터 파이프라인 Airflow DAG
MOCK 데이터를 사용한 완전한 Producer/Consumer 워크플로우
"""
from datetime import datetime, timedelta, date
from typing import Dict, Any, List
import asyncio
import uuid

from airflow import DAG
from airflow.operators.python import PythonOperator

from api.kafka_client import kafka_integrated_client
from streaming.producer import producer
from streaming.consumer import consumer
from streaming.models import EventType
from database.repository import LegalDataRepository
from mock.data_generator import MockDataGenerator
from notifications.slack_service import slack_service
from logging_config import get_logger

logger = get_logger(__name__)

# DAG 기본 설정
DEFAULT_ARGS = {
    'owner': 'legal-data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,
    'max_retry_delay': timedelta(minutes=15),
    'execution_timeout': timedelta(hours=2),
    'sla': timedelta(hours=3),
}

# Kafka 기반 DAG 정의
dag = DAG(
    'kafka_legal_data_pipeline_mock',
    default_args=DEFAULT_ARGS,
    description='Kafka 기반 법제처 API 데이터 파이프라인 - MOCK 데이터 활용 완전 워크플로우',
    schedule='0 2 * * *',  # 매일 새벽 2시 실행
    catchup=False,
    max_active_runs=1,
    tags=['legal', 'kafka', 'pipeline', 'mock', 'complete-workflow'],
    is_paused_upon_creation=False,
    doc_md="""
    # Kafka 기반 법제처 API 데이터 파이프라인 (MOCK 데이터)
    
    ## 개요
    MOCK 데이터를 활용한 완전한 Producer/Consumer 워크플로우입니다.
    
    ## 주요 특징
    - **MOCK 데이터**: 기존 MockDataGenerator 활용으로 실제 API 호출 없이 테스트 가능
    - **완전한 워크플로우**: Producer → Consumer → 알림까지 전체 과정
    - **Kafka 스트리밍**: 실제 Kafka Producer/Consumer 사용
    - **높은 신뢰성**: Kafka 메시지 영속성으로 데이터 손실 방지
    - **확장성**: Producer/Consumer 분리로 수평 확장 가능
    - **모니터링**: 실시간 처리 상태 추적 및 상세 통계
    
    ## 데이터 플로우
    1. **Health Check**: Kafka 클러스터 상태 확인
    2. **Producer**: MOCK 법령 데이터 → Kafka Topics
    3. **Consumer**: Kafka Topics → MySQL Database 저장
    4. **Notification**: 처리 결과 알림 발송
    """,

    params={
        'force_full_sync': False,
        'target_date': None,
        'batch_size': 30,  # MOCK 데이터용으로 설정
        'notification_enabled': True,
        'kafka_enabled': True,
        'mock_laws_count': 25,  # 생성할 MOCK 법령 수
        'consumer_timeout_seconds': 300,  # Consumer 타임아웃
        'producer_failure_simulation': False  # Producer 실패 시뮬레이션
    }
)

# ==================== 헬퍼 함수 ====================

def run_async_task(async_func, *args, **kwargs):
    """비동기 함수를 동기 환경에서 실행"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(async_func(*args, **kwargs))
    finally:
        loop.close()

# ==================== DAG 태스크 함수들 ====================

def check_kafka_health(**context) -> Dict[str, Any]:
    """Kafka 헬스 체크"""
    logger.info("Kafka 헬스 체크 시작")
    
    async def _check_kafka():
        """Kafka 클러스터 상태 확인"""
        async with kafka_integrated_client:
            health_result = await kafka_integrated_client.health_check()
            return health_result
    
    try:
        health_result = run_async_task(_check_kafka)
        
        if health_result.get('overall_status') == 'healthy':
            logger.info("Kafka 헬스 체크 성공", health=health_result)
        else:
            logger.error("Kafka 헬스 체크 실패", health=health_result)
            raise Exception(f"Kafka 클러스터가 비정상 상태입니다: {health_result}")
        
        return health_result
        
    except Exception as e:
        logger.error("Kafka 헬스 체크 오류", error=str(e))
        raise

def kafka_produce_mock_data(**context) -> Dict[str, Any]:
    """Kafka Producer를 통한 MOCK 데이터 전송"""
    logger.info("Kafka Producer MOCK 데이터 전송 시작")
    
    async def _produce_mock_data(mock_count: int, failure_simulation: bool):
        """MOCK 데이터를 생성하고 Kafka로 전송"""
        
        # MOCK 데이터 생성기 초기화
        mock_generator = MockDataGenerator()
        
        # MOCK 법령 데이터 생성
        mock_documents = mock_generator.generate_multiple_documents(mock_count)
        logger.info(f"MOCK 법령 데이터 {len(mock_documents)}개 생성 완료")
        
        # Producer 세션 시작
        async with producer.session():
            sent_count = 0
            failed_count = 0
            job_id = f"mock_producer_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 배치 시작 이벤트 전송
            await producer.send_batch_status_event(
                job_id, "MOCK_PRODUCER", EventType.BATCH_STARTED
            )
            
            try:
                for i, doc in enumerate(mock_documents):
                    try:
                        # 의도적 실패 시뮬레이션
                        if failure_simulation and i % 10 == 0:  # 10%
                            raise Exception(f"의도적 실패 시뮬레이션: {doc['id']}")
                        
                        # MOCK 데이터를 LawEvent 형식으로 변환
                        from streaming.models import LawEvent
                        from api.models import LawListItem
                        
                        # MockDataGenerator 출력을 LawListItem으로 변환
                        mock_law = LawListItem(
                            law_id=doc['id'],
                            law_master_no=doc['id'],  # MOCK에서는 동일하게 사용
                            law_name=doc['title'],
                            enforcement_date=datetime.fromisoformat(doc['published_date'].replace('Z', '+00:00')).date(),
                            promulgation_date=datetime.fromisoformat(doc['published_date'].replace('Z', '+00:00')).date(),
                            law_type=doc['doc_type'],
                            ministry_name=doc['source'],
                            revision_type=doc['status']
                        )
                        
                        # LawEvent 생성 및 전송
                        success = await producer.send_law_event(mock_law)
                        
                        if success:
                            sent_count += 1
                            logger.debug(f"MOCK 법령 전송 성공: {doc['id']}")
                        else:
                            failed_count += 1
                            logger.warning(f"MOCK 법령 전송 실패: {doc['id']}")
                        
                        # 처리 속도 시뮬레이션
                        await asyncio.sleep(0.1)
                        
                    except Exception as e:
                        failed_count += 1
                        logger.warning(f"MOCK 법령 처리 실패: {doc.get('id', 'Unknown')} - {str(e)}")
                
                # 배치 완료/실패 이벤트 전송
                if failed_count == 0:
                    await producer.send_batch_status_event(
                        job_id, "MOCK_PRODUCER", EventType.BATCH_COMPLETED,
                        processed_count=sent_count, error_count=0
                    )
                else:
                    await producer.send_batch_status_event(
                        job_id, "MOCK_PRODUCER", EventType.BATCH_FAILED,
                        processed_count=sent_count, error_count=failed_count
                    )
                
                return {
                    'sent_laws': sent_count,
                    'failed_laws': failed_count,
                    'total_laws': len(mock_documents),
                    'job_id': job_id
                }
                
            except Exception as e:
                # 전체 배치 실패
                await producer.send_batch_status_event(
                    job_id, "MOCK_PRODUCER", EventType.BATCH_FAILED,
                    processed_count=sent_count, error_count=failed_count + 1
                )
                raise
    
    try:
        # 파라미터 확인
        params = context.get('params', {})
        mock_count = params.get('mock_laws_count', 25)
        failure_simulation = params.get('producer_failure_simulation', False)
        
        # Producer 실행
        start_time = datetime.now()
        result = run_async_task(_produce_mock_data, mock_count, failure_simulation)
        end_time = datetime.now()
        
        result['duration_seconds'] = (end_time - start_time).total_seconds()
        result['is_mock_data'] = True
        
        logger.info("Kafka Producer MOCK 데이터 전송 완료",
                   sent_laws=result.get('sent_laws', 0),
                   failed_laws=result.get('failed_laws', 0),
                   duration=result.get('duration_seconds', 0))
        
        # XCom에 결과 저장 (Consumer에서 사용)
        context['task_instance'].xcom_push(
            key='producer_result',
            value=result
        )
        
        return result
        
    except Exception as e:
        logger.error("Kafka Producer MOCK 데이터 전송 실패", error=str(e))
        
        # 오류 알림
        slack_service.send_error_alert(
            error=e,
            context={
                'job_name': 'Kafka Producer (MOCK)',
                'dag_id': context['dag'].dag_id,
                'task_id': context['task'].task_id,
                'logical_date': context['logical_date'].isoformat()
            }
        )
        
        raise

def kafka_consume_and_store(**context) -> Dict[str, Any]:
    """Kafka Consumer를 통한 데이터 수신 및 DB 저장"""
    logger.info("Kafka Consumer 데이터 수신 및 저장 시작")
    
    async def _consume_and_store_data(expected_count: int, timeout_seconds: int):
        """Kafka에서 데이터를 소비하고 DB에 저장"""
        from streaming.config import Topics
        
        # Consumer 그룹 ID 생성 (DAG 실행별로 고유)
        execution_date = context['logical_date'].strftime('%Y%m%d_%H%M%S')
        consumer_group_id = f"dag-consumer-{execution_date}"
        
        # Consumer 인스턴스 생성
        consumer_instance = consumer.__class__(group_id=consumer_group_id)
        
        consumed_count = 0
        stored_count = 0
        failed_count = 0
        
        try:
            # Consumer 세션 시작 (법령 이벤트만 구독)
            async with consumer_instance.session([Topics.LAW_EVENTS]):
                logger.info(f"Consumer 시작 - 예상 메시지: {expected_count}, 타임아웃: {timeout_seconds}초")
                
                start_time = datetime.now()
                
                # 메시지 소비 (타임아웃 처리)
                while consumed_count < expected_count:
                    current_time = datetime.now()
                    elapsed = (current_time - start_time).total_seconds()
                    
                    if elapsed > timeout_seconds:
                        logger.warning(f"Consumer 타임아웃 - 처리된 메시지: {consumed_count}/{expected_count}")
                        break
                    
                    # 단일 메시지 소비 (논블로킹)
                    try:
                        # Consumer poll을 직접 호출하여 단일 메시지 처리
                        message_batch = consumer_instance.consumer.poll(timeout_ms=1000)
                        
                        if not message_batch:
                            continue
                        
                        # 배치의 각 메시지 처리
                        for topic_partition, messages in message_batch.items():
                            for message in messages:
                                try:
                                    await consumer_instance._process_message(message)
                                    consumed_count += 1
                                    stored_count += 1
                                    
                                    logger.debug(f"메시지 처리 완료: {consumed_count}/{expected_count}")
                                    
                                    # 커밋
                                    consumer_instance.consumer.commit()
                                    
                                except Exception as e:
                                    consumed_count += 1
                                    failed_count += 1
                                    logger.warning(f"메시지 처리 실패: {str(e)}")
                    
                    except Exception as e:
                        logger.warning(f"메시지 polling 오류: {str(e)}")
                        await asyncio.sleep(1)
                
                return {
                    'consumed_messages': consumed_count,
                    'stored_laws': stored_count,
                    'failed_stores': failed_count,
                    'expected_count': expected_count,
                    'timeout_reached': consumed_count < expected_count
                }
                
        except Exception as e:
            logger.error("Consumer 실행 중 오류", error=str(e))
            return {
                'consumed_messages': consumed_count,
                'stored_laws': stored_count,
                'failed_stores': failed_count + 1,
                'expected_count': expected_count,
                'error': str(e)
            }
    
    try:
        # Producer 결과에서 예상 메시지 수 가져오기
        producer_result = context['task_instance'].xcom_pull(
            task_ids='kafka_produce_mock_data',
            key='producer_result'
        )
        
        if not producer_result:
            raise ValueError("Producer 결과를 찾을 수 없습니다")
        
        expected_count = producer_result.get('sent_laws', 0)
        
        if expected_count == 0:
            logger.warning("처리할 메시지가 없습니다")
            return {
                'consumed_messages': 0,
                'stored_laws': 0,
                'failed_stores': 0
            }
        
        # 파라미터 확인
        params = context.get('params', {})
        timeout_seconds = params.get('consumer_timeout_seconds', 300)
        
        # Consumer 실행
        start_time = datetime.now()
        result = run_async_task(_consume_and_store_data, expected_count, timeout_seconds)
        end_time = datetime.now()
        
        result['duration_seconds'] = (end_time - start_time).total_seconds()
        result['expected_messages'] = expected_count
        
        logger.info("Kafka Consumer 데이터 수신 및 저장 완료",
                   consumed_messages=result.get('consumed_messages', 0),
                   stored_laws=result.get('stored_laws', 0),
                   failed_stores=result.get('failed_stores', 0),
                   duration=result.get('duration_seconds', 0))
        
        return result
        
    except Exception as e:
        logger.error("Kafka Consumer 데이터 수신 및 저장 실패", error=str(e))
        
        # 오류 알림
        slack_service.send_error_alert(
            error=e,
            context={
                'job_name': 'Kafka Consumer',
                'dag_id': context['dag'].dag_id,
                'task_id': context['task'].task_id,
                'logical_date': context['logical_date'].isoformat()
            }
        )
        
        raise

def send_completion_notification(**context) -> None:
    """완료 알림 발송"""
    logger.info("완료 알림 발송 시작")
    
    try:
        # 파라미터 확인
        params = context.get('params', {})
        if not params.get('notification_enabled', True):
            logger.info("알림이 비활성화되어 있습니다")
            return
        
        # Producer 및 Consumer 결과 수집
        producer_result = context['task_instance'].xcom_pull(
            task_ids='kafka_produce_mock_data'
        )
        consumer_result = context['task_instance'].xcom_pull(
            task_ids='kafka_consume_and_store'
        )
        
        if not producer_result or not consumer_result:
            logger.warning("Producer 또는 Consumer 결과를 찾을 수 없습니다")
            return
        
        # 통계 정보 생성
        produced_laws = producer_result.get('sent_laws', 0)
        producer_failures = producer_result.get('failed_laws', 0)
        consumed_messages = consumer_result.get('consumed_messages', 0)
        stored_laws = consumer_result.get('stored_laws', 0)
        consumer_failures = consumer_result.get('failed_stores', 0)
        timeout_reached = consumer_result.get('timeout_reached', False)
        
        producer_duration = producer_result.get('duration_seconds', 0)
        consumer_duration = consumer_result.get('duration_seconds', 0)
        total_duration = producer_duration + consumer_duration
        
        # 성공/실패 결정
        total_failures = producer_failures + consumer_failures
        is_success = total_failures == 0 and not timeout_reached
        
        # BatchResult 생성
        from notifications.slack_service import BatchResult
        
        # 상태 아이콘 및 메시지
        if is_success:
            status_icon = "✅"
            status_text = "성공"
        elif timeout_reached:
            status_icon = "⏰"
            status_text = "부분 성공 (타임아웃)"
        else:
            status_icon = "⚠️"
            status_text = "부분 성공"
        
        # 상세 메시지 생성
        detail_message = f"""
{status_icon} **Kafka 파이프라인 처리 결과**

📊 **Producer 통계**
• 생성된 MOCK 데이터: {producer_result.get('total_laws', 0)}개
• Kafka 전송 성공: {produced_laws}개
• Kafka 전송 실패: {producer_failures}개
• Producer 처리 시간: {producer_duration:.1f}초

📥 **Consumer 통계**  
• Kafka 메시지 수신: {consumed_messages}개
• 데이터베이스 저장: {stored_laws}개
• 저장 실패: {consumer_failures}개
• Consumer 처리 시간: {consumer_duration:.1f}초

🔍 **전체 통계**
• 총 처리 시간: {total_duration:.1f}초
• 전체 성공률: {((stored_laws / produced_laws) * 100):.1f}%
• 파이프라인 타입: MOCK 데이터 테스트
        """.strip()
        
        if timeout_reached:
            detail_message += f"\n⚠️ Consumer가 {params.get('consumer_timeout_seconds', 300)}초 타임아웃에 도달했습니다."
        
        batch_result = BatchResult(
            job_name="Kafka 기반 법제처 데이터 파이프라인 (MOCK)",
            success=is_success,
            processed_laws=stored_laws,
            processed_articles=0,
            error_count=total_failures,
            error_message=None if is_success else f"총 {total_failures}개 오류 발생" + (" (타임아웃 포함)" if timeout_reached else ""),
            duration=f"{total_duration:.1f}초",
            detail_message=detail_message
        )
        
        # 슬랙 알림 발송
        success = slack_service.send_batch_completion_notice(batch_result)
        
        if success:
            logger.info("완료 알림 발송 성공")
        else:
            logger.warning("완료 알림 발송 실패")
        
        logger.info("완료 알림 발송 완료")
        
    except Exception as e:
        logger.error("완료 알림 발송 실패", error=str(e))

# ==================== DAG 태스크 정의 ====================

# Kafka 헬스 체크
kafka_health_check_task = PythonOperator(
    task_id='check_kafka_health',
    python_callable=check_kafka_health,
    dag=dag,
    execution_timeout=timedelta(minutes=5),
    doc_md="Kafka 클러스터의 상태를 확인합니다."
)

# Kafka Producer - MOCK 데이터 전송
kafka_produce_task = PythonOperator(
    task_id='kafka_produce_mock_data',
    python_callable=kafka_produce_mock_data,
    dag=dag,
    execution_timeout=timedelta(minutes=30),
    doc_md="""
    MOCK 법령 데이터를 MockDataGenerator로 생성하고 Kafka 토픽으로 전송합니다.
    - MockDataGenerator를 사용하여 현실적인 법령 데이터 생성
    - Kafka Producer를 통해 law_events 토픽으로 전송
    - 의도적 실패 시뮬레이션 지원
    """
)

# Kafka Consumer - 데이터 수신 및 저장
kafka_consume_task = PythonOperator(
    task_id='kafka_consume_and_store',
    python_callable=kafka_consume_and_store,
    dag=dag,
    execution_timeout=timedelta(minutes=45),
    doc_md="""
    Kafka 토픽에서 법령 데이터를 수신하고 데이터베이스에 저장합니다.
    - law_events 토픽을 구독하여 메시지 소비
    - 수신된 데이터를 MySQL 데이터베이스에 저장  
    - 타임아웃 처리로 무한 대기 방지
    - DAG 실행별 고유 Consumer Group 사용
    """
)

# 완료 알림
completion_notification_task = PythonOperator(
    task_id='send_completion_notification',
    python_callable=send_completion_notification,
    dag=dag,
    doc_md="""
    전체 파이프라인 완료 알림을 발송합니다.
    - Producer와 Consumer 실행 통계 종합
    - 성공/실패 상태 및 상세 메트릭 포함
    - Slack을 통한 알림 발송
    """
)

# ==================== 태스크 의존성 설정 ====================

kafka_health_check_task >> kafka_produce_task >> kafka_consume_task >> completion_notification_task
