"""
Kafka 기반 법제처 API 데이터 파이프라인 Airflow DAG
무중단 서비스를 위한 Kafka 통합 버전
"""
from datetime import datetime, timedelta, date
from typing import Dict, Any
import uuid
import json
import asyncio

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
from airflow.exceptions import AirflowException, AirflowSkipException
from airflow.utils.email import send_email

# 프로젝트 모듈 임포트
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../..'))

from src.api.kafka_client import kafka_integrated_client
from src.database.repository import LegalDataRepository
from src.notifications.slack_service import slack_service
from src.logging_config import get_logger
from src.kafka.models import EventType

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
    'kafka_legal_data_pipeline',
    default_args=DEFAULT_ARGS,
    description='Kafka 기반 법제처 API 데이터 파이프라인 - 무중단 서비스',
    schedule_interval='0 2 * * *',  # 매일 새벽 2시 실행
    catchup=False,
    max_active_runs=1,
    tags=['legal', 'kafka', 'pipeline', 'zero-downtime'],
    doc_md="""
    # Kafka 기반 법제처 API 데이터 파이프라인
    
    ## 개요
    무중단 서비스를 위해 Kafka를 활용한 법제처 데이터 파이프라인입니다.
    
    ## 주요 특징
    - **무중단 서비스**: API 서비스 중단 없이 데이터 업데이트
    - **높은 신뢰성**: Kafka 메시지 영속성으로 데이터 손실 방지
    - **확장성**: Producer/Consumer 분리로 수평 확장 가능
    - **모니터링**: 실시간 처리 상태 추적
    
    ## 데이터 플로우
    1. **Producer**: 법제처 API → Kafka Topics
    2. **Consumer**: Kafka Topics → MySQL Database
    3. **Monitoring**: 처리 상태 및 통계 추적
    """,
    params={
        'force_full_sync': False,
        'target_date': None,
        'batch_size': 100,
        'notification_enabled': True,
        'kafka_enabled': True
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

def kafka_produce_legal_data(**context) -> Dict[str, Any]:
    """Kafka Producer를 통한 법령 데이터 수집 및 전송"""
    logger.info("Kafka Producer 데이터 수집 시작")
    
    async def _produce_data(sync_date, batch_size):
        async with kafka_integrated_client:
            return await kafka_integrated_client.collect_and_publish_laws(
                last_sync_date=sync_date,
                batch_size=batch_size
            )
    
    try:
        # 파라미터 확인
        params = context.get('params', {})
        batch_size = params.get('batch_size', 100)
        
        # 마지막 동기화 날짜 조회
        repository = LegalDataRepository()
        sync_date = repository.get_last_sync_date("INCREMENTAL")
        if not sync_date:
            sync_date = date.today() - timedelta(days=7)
        
        # Kafka Producer 실행
        result = run_async_task(_produce_data, sync_date, batch_size)
        
        logger.info("Kafka Producer 데이터 수집 완료",
                   sent_laws=result.get('sent_laws', 0),
                   failed_laws=result.get('failed_laws', 0))
        
        return result
        
    except Exception as e:
        logger.error("Kafka Producer 데이터 수집 실패", error=str(e))
        
        # 오류 알림
        slack_service.send_error_alert(
            title="Kafka Producer 실행 실패",
            message=f"오류: {str(e)}",
            context={'dag_id': context['dag'].dag_id}
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
        
        # 결과 데이터 수집
        produce_result = context['task_instance'].xcom_pull(
            task_ids='kafka_produce_legal_data'
        )
        
        if not produce_result:
            logger.warning("Producer 결과를 찾을 수 없습니다")
            return
        
        # 통계 정보 생성
        sent_laws = produce_result.get('sent_laws', 0)
        failed_laws = produce_result.get('failed_laws', 0)
        duration = produce_result.get('duration_seconds', 0)
        
        # 성공/실패 결정
        is_success = failed_laws == 0
        
        # 메시지 생성
        status_icon = "✅" if is_success else "⚠️"
        status_text = "성공" if is_success else "부분 성공"
        
        message = f"""
{status_icon} Kafka 기반 법제처 데이터 파이프라인 완료

📊 **처리 결과:**
• 처리된 법령: {sent_laws}개
• 실패한 법령: {failed_laws}개
• 처리 시간: {duration:.1f}초
• 상태: {status_text}

🔄 **Kafka 통합:**
• Producer → Consumer 비동기 처리
• 무중단 서비스 보장
• 메시지 영속성 확보
        """.strip()
        
        # 슬랙 알림 발송
        if is_success:
            slack_service.send_info_message(
                title="Kafka 기반 법제처 파이프라인 완료",
                message=message
            )
        else:
            slack_service.send_error_alert(
                title="Kafka 기반 법제처 파이프라인 부분 실패",
                message=message,
                context=produce_result
            )
        
        logger.info("완료 알림 발송 완료")
        
    except Exception as e:
        logger.error("완료 알림 발송 실패", error=str(e))

# ==================== DAG 태스크 정의 ====================

# Kafka Producer 데이터 수집
kafka_produce_task = PythonOperator(
    task_id='kafka_produce_legal_data',
    python_callable=kafka_produce_legal_data,
    dag=dag,
    execution_timeout=timedelta(hours=1),
    doc_md="Kafka Producer를 통해 법제처 데이터를 수집하고 토픽으로 전송합니다."
)

# 완료 알림
completion_notification_task = PythonOperator(
    task_id='send_completion_notification',
    python_callable=send_completion_notification,
    dag=dag,
    doc_md="파이프라인 완료 알림을 발송합니다."
)

# ==================== 태스크 의존성 설정 ====================

kafka_produce_task >> completion_notification_task
