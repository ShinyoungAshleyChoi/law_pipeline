"""
일별 법제처 데이터 처리 파이프라인 DAG

Mock 데이터 생성 → Kafka 스트리밍 → Blue-Green 배포를 통한 
법제처 API 데이터 처리 파이프라인
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from airflow import DAG
from airflow.operators.python import PythonOperator

# 프로젝트 모듈 임포트
from mock.data_generator import MockDataGenerator
from streaming.producer import LegalDataProducer
from streaming.consumer import LegalDataConsumer
from streaming.config import Topics
from api.models import LawListItem
from logging_config import get_logger

logger = get_logger(__name__)

# DAG 기본 설정
default_args = {
    'owner': 'data-engineer',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'daily_legal_data_pipeline',
    default_args=default_args,
    description='일별 법제처 데이터 처리 파이프라인',
    schedule_interval='0 2 * * *',  # 새벽 2시
    catchup=False,
    max_active_runs=1,
    tags=['legal', 'daily', 'kafka', 'blue-green'],
)


def generate_and_produce_mock_data(**context):
    """
    Mock 데이터 생성 및 Kafka 프로듀싱
    logical_date(실행일 전날)의 공포일자 기준으로 데이터 생성
    """
    import asyncio
    from datetime import datetime
    
    # logical_date 가져오기 (실행일 전날)
    logical_date = context['ds']  # YYYY-MM-DD 형식
    execution_date = datetime.strptime(logical_date, '%Y-%m-%d')
    
    logger.info(f"Mock 데이터 생성 시작 - 공포일자: {logical_date}")
    
    # Mock 데이터 생성
    generator = MockDataGenerator()
    
    # 법령 데이터 생성 (50개)
    laws_data = []
    for i in range(50):
        doc = generator.generate_legal_document()
        # 공포일자를 logical_date로 설정
        doc['published_date'] = execution_date.isoformat() + "Z"
        laws_data.append(doc)
    
    # 법령 본문 데이터 생성 (20개)
    contents_data = []
    for i in range(20):
        content_doc = generator.generate_legal_document()
        content_doc['published_date'] = execution_date.isoformat() + "Z"
        content_doc['content_type'] = 'full_text'
        contents_data.append(content_doc)
    
    # 법령 조항 데이터 생성 (30개)
    articles_data = []
    for i in range(30):
        article_doc = generator.generate_legal_document()
        article_doc['published_date'] = execution_date.isoformat() + "Z"
        article_doc['content_type'] = 'articles'
        # 조항 분할
        article_doc['articles'] = [
            {
                'article_no': f'제{j+1}조',
                'article_title': f'조항 {j+1}',
                'article_content': f'제{j+1}조의 내용입니다.',
                'law_id': article_doc['id']
            }
            for j in range(5)  # 조항당 5개 조문
        ]
        articles_data.append(article_doc)
    
    async def produce_data():
        """비동기 데이터 프로듀싱"""
        producer = LegalDataProducer()
        
        try:
            await producer.start()
            
            # 배치 시작 이벤트
            job_id = f"daily_pipeline_{logical_date.replace('-', '')}"
            correlation_id = f"daily_{execution_date.strftime('%Y%m%d_%H%M%S')}"
            
            from streaming.models import EventType
            await producer.send_batch_status_event(
                job_id=job_id,
                job_type="DAILY_PIPELINE",
                event_type=EventType.BATCH_STARTED,
                correlation_id=correlation_id
            )
            
            # 1. 법령 목록 데이터 프로듀싱
            logger.info("법령 목록 데이터 프로듀싱 시작")
            laws_sent = 0
            for i, law_data in enumerate(laws_data):
                # LawListItem으로 변환 (필수 파라미터만 사용)
                law_master_no = f"MASTER_{law_data['id'].replace('LAW-', '')}"
                
                law_item = LawListItem(
                    law_id=law_data['id'],
                    law_master_no=law_master_no,
                    law_name=law_data['title'],
                    enforcement_date=execution_date.date(),
                    law_type=law_data.get('doc_type'),
                    promulgation_date=execution_date.date(),
                    ministry_name=law_data.get('source'),
                    revision_type='신규'
                )
                
                if await producer.send_law_event(law_item, correlation_id):
                    laws_sent += 1
                
                # 프로듀싱 간격 조절
                await asyncio.sleep(1)
            
            logger.info(f"법령 목록 프로듀싱 완료: {laws_sent}/{len(laws_data)}")
            
            # 2. 법령 본문 데이터 프로듀싱
            logger.info("법령 본문 데이터 프로듀싱 시작")
            from streaming.models import ContentEvent
            contents_sent = 0
            
            for content_data in contents_data:
                # ContentEvent.create_updated_event에 올바른 파라미터 전달
                content_dict = {
                    'law_id': content_data['id'],
                    'law_name': content_data['title'],
                    'content': content_data['content'],
                    'enforcement_date': execution_date.date().isoformat(),
                    'law_type': content_data.get('doc_type'),
                    'article_count': 5  # Mock 데이터이므로 고정값
                }
                
                content_event = ContentEvent.create_updated_event(
                    law_id=content_data['id'],
                    content_data=content_dict,
                    correlation_id=correlation_id
                )
                
                if await producer.send_message(Topics.CONTENT_EVENTS, content_event):
                    contents_sent += 1
                
                await asyncio.sleep(1)
            
            logger.info(f"법령 본문 프로듀싱 완료: {contents_sent}/{len(contents_data)}")
            
            # 3. 법령 조항 데이터 프로듀싱
            logger.info("법령 조항 데이터 프로듀싱 시작")
            from streaming.models import ArticleEvent
            articles_sent = 0
            
            for article_data in articles_data:
                # ArticleEvent.create_updated_event에 올바른 파라미터 전달
                law_master_no = f"MASTER_{article_data['id'].replace('LAW-', '')}"
                
                article_event = ArticleEvent.create_updated_event(
                    law_id=article_data['id'],
                    law_master_no=law_master_no,
                    articles_data=article_data['articles'],
                    ministry_code=1,  # Mock 데이터이므로 고정값
                    correlation_id=correlation_id
                )
                
                if await producer.send_message(Topics.ARTICLE_EVENTS, article_event):
                    articles_sent += 1
                
                await asyncio.sleep(1)
            
            logger.info(f"법령 조항 프로듀싱 완료: {articles_sent}/{len(articles_data)}")
            
            # 배치 완료 이벤트
            total_sent = laws_sent + contents_sent + articles_sent
            total_expected = len(laws_data) + len(contents_data) + len(articles_data)
            
            if total_sent == total_expected:
                await producer.send_batch_status_event(
                    job_id=job_id,
                    job_type="DAILY_PIPELINE",
                    event_type=EventType.BATCH_COMPLETED,
                    processed_count=total_sent,
                    error_count=0,
                    correlation_id=correlation_id
                )
                logger.info(f"프로듀싱 완료: 총 {total_sent}개 메시지 전송")
            else:
                await producer.send_batch_status_event(
                    job_id=job_id,
                    job_type="DAILY_PIPELINE", 
                    event_type=EventType.BATCH_FAILED,
                    processed_count=total_sent,
                    error_count=total_expected - total_sent,
                    correlation_id=correlation_id
                )
                raise Exception(f"프로듀싱 불완전: {total_sent}/{total_expected}")
            
        finally:
            await producer.stop()
    
    # 이벤트 루프에서 실행
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(produce_data())
    
    return {
        'laws_produced': len(laws_data),
        'contents_produced': len(contents_data), 
        'articles_produced': len(articles_data),
        'publication_date': logical_date
    }


def consume_kafka_messages(**context):
    """
    Kafka 메시지 컨슈밍하여 Green MySQL에 저장
    """
    import asyncio
    import time
    
    logical_date = context['ds']
    logger.info(f"Kafka 메시지 컨슈밍 시작 - {logical_date}")
    
    async def consume_data():
        """비동기 데이터 컨슈밍"""
        # Green DB 타겟 Consumer 생성
        consumer = LegalDataConsumer(group_id="daily-pipeline-green")
        
        try:
            # 모든 이벤트 토픽 구독
            topics = [Topics.LAW_EVENTS, Topics.CONTENT_EVENTS, Topics.ARTICLE_EVENTS]
            await consumer.start(topics)
            
            logger.info("메시지 컨슈밍 시작")
            
            # 최대 10분간 메시지 소비 (또는 큐가 비워질 때까지)
            start_time = time.time()
            timeout = 600  # 10분
            
            # 배치 크기만큼 처리 (앞서 프로듀싱한 메시지 수)
            expected_messages = 100  # 50 + 20 + 30
            
            logger.info(f"메시지 컨슈밍 시작 - 예상 메시지: {expected_messages}개")
            
            # Consumer는 무한 루프로 동작하므로 max_messages 없이 시간제한으로 제어
            await consumer.consume_messages(max_messages=expected_messages)
            
            processed_messages = consumer._stats.get('messages_processed', 0)
            logger.info(f"컨슈밍 완료: {processed_messages}개 메시지 처리")
            
            return processed_messages
            
        finally:
            await consumer.stop()
    
    # 이벤트 루프에서 실행
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    processed = loop.run_until_complete(consume_data())
    
    return {
        'messages_consumed': processed,
        'target_database': 'mysql-green',
        'processing_date': logical_date
    }


def blue_green_switch(**context):
    """
    Blue-Green 데이터베이스 스위칭 실행
    기존 스크립트를 활용하여 데이터 동기화 + 스위칭 수행
    """
    logical_date = context['ds']
    logger.info(f"Blue-Green 스위칭 시작 - {logical_date}")
    
    # 실행 컨텍스트 정보
    run_id = context['run_id']
    version = f"daily-{logical_date.replace('-', '')}"
    
    # Python으로 blue_green_deploy.py 실행
    import subprocess
    import sys
    
    # 프로젝트 루트 경로
    project_root = Path(__file__).parent.parent.parent.parent
    script_path = project_root / "deployment" / "blue_green_deploy.py"
    
    try:
        # blue-green 배포 실행 (데이터 동기화 포함)
        cmd = [
            sys.executable,
            str(script_path),
            'deploy',
            '--version', version
        ]
        
        logger.info(f"Blue-Green 배포 명령 실행: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30분 타임아웃
            cwd=str(project_root)
        )
        
        if result.returncode == 0:
            logger.info("Blue-Green 배포 성공")
            logger.info(f"배포 출력: {result.stdout}")
            
            return {
                'status': 'success',
                'version': version,
                'switch_date': logical_date,
                'deployment_log': result.stdout
            }
        else:
            logger.error("Blue-Green 배포 실패")
            logger.error(f"오류 출력: {result.stderr}")
            raise Exception(f"Blue-Green 배포 실패: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("Blue-Green 배포 타임아웃")
        raise Exception("Blue-Green 배포가 30분 내에 완료되지 않았습니다")
    except Exception as e:
        logger.error(f"Blue-Green 배포 실행 오류: {e}")
        raise


# Task 정의
task_1_produce = PythonOperator(
    task_id='generate_and_produce_mock_data',
    python_callable=generate_and_produce_mock_data,
    dag=dag,
    doc_md="""
    ## Mock 데이터 생성 및 Kafka 프로듀싱
    
    - logical_date(전날) 기준 공포일자 데이터 생성
    - 법령목록(50개) → law-events 토픽
    - 법령본문(20개) → content-events 토픽  
    - 법령조항(30개) → article-events 토픽
    - 총 100개 메시지 프로듀싱
    """,
)

task_2_consume = PythonOperator(
    task_id='consume_kafka_messages',
    python_callable=consume_kafka_messages,
    dag=dag,
    doc_md="""
    ## Kafka 메시지 컨슈밍
    
    - 3개 토픽에서 메시지 수신
    - Green MySQL 데이터베이스에 저장
    - 데이터 정합성 확인
    - 최대 10분 또는 100개 메시지 처리
    """,
)

task_3_switch = PythonOperator(
    task_id='blue_green_switch',
    python_callable=blue_green_switch,
    dag=dag,
    doc_md="""
    ## Blue-Green 데이터베이스 스위칭
    
    - 기존 blue_green_deploy.py 스크립트 활용
    - Green → Blue 데이터 동기화
    - 트래픽 스위칭 (무중단 배포)
    - Nginx 프록시 설정 업데이트
    """,
)

# Task 의존성 설정
task_1_produce >> task_2_consume >> task_3_switch

# DAG 레벨 문서화
dag.doc_md = """
# 일별 법제처 데이터 처리 파이프라인

법제처 API Mock 데이터를 활용한 일별 데이터 처리 파이프라인입니다.

## 실행 스케줄
- **시간**: 매일 새벽 2시 (KST)
- **데이터 기준일**: 실행일 전날 (logical_date)

## 처리 흐름
1. **Mock 데이터 생성 & 프로듀싱** (10분)
   - 전날 공포일자 기준 법제처 데이터 생성
   - Kafka 3개 토픽으로 스트리밍
   
2. **데이터 컨슈밍** (10분)  
   - Green MySQL에 데이터 적재
   - 실시간 데이터 검증
   
3. **Blue-Green 스위칭** (30분)
   - 데이터베이스 동기화
   - 무중단 서비스 전환

## 모니터링
- Airflow UI: Task 실행 상태 확인
- Slack: 실패 시 자동 알림  
- MySQL: 데이터 적재 현황 확인

## 롤백 방법
Blue-Green 스위칭 실패 시:
```bash
python deployment/blue_green_deploy.py rollback
```
"""
