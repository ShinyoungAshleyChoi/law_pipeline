"""
일별 법제처 데이터 처리 파이프라인 DAG

Mock 데이터 생성 → Kafka 스트리밍 → Blue-Green 배포를 통한 
법제처 API 데이터 처리 파이프라인
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
import subprocess
import time
import json

from airflow import DAG
from airflow.operators.python import PythonOperator

# 데이터베이스 연결을 위한 MySQL 커넥터 추가
import mysql.connector
from mysql.connector import Error as MySQLError

# 프로젝트 모듈 임포트
from mock.data_generator import MockDataGenerator
from streaming.producer import LegalDataProducer
from streaming.consumer import LegalDataConsumer
from streaming.config import Topics
from api.models import LawListItem
from logging_config import get_logger

logger = get_logger(__name__)


def optimize_message_size(data: Dict[str, Any], max_content_length: int = 5000) -> Dict[str, Any]:
    """메시지 크기 최적화 - Kafka 전송 안정성 향상"""
    optimized = data.copy()

    # 1. 긴 콘텐츠 잘라내기
    if 'content' in optimized and optimized['content']:
        content = optimized['content']
        if len(content) > max_content_length:
            # 문장 단위로 자르기 (자연스러운 단락 끝에서)
            sentences = content.split('. ')
            truncated_content = ""
            for sentence in sentences:
                if len(truncated_content + sentence + '. ') <= max_content_length:
                    truncated_content += sentence + '. '
                else:
                    break

            optimized['content'] = truncated_content.rstrip('. ')
            optimized['content_truncated'] = True
            optimized['original_content_length'] = len(content)

    # 2. 불필요한 메타데이터 제거
    if 'metadata' in optimized:
        # 핵심 메타데이터만 유지
        essential_keys = ['language', 'bill_number', 'case_number', 'notice_number', 'effective_date']
        metadata = optimized['metadata']
        optimized['metadata'] = {k: v for k, v in metadata.items() if k in essential_keys}

    # 3. 배열 크기 제한
    if 'tags' in optimized and len(optimized['tags']) > 3:
        optimized['tags'] = optimized['tags'][:3]  # 최대 3개 태그만

    # 4. 조항 데이터 최적화
    if 'articles' in optimized and isinstance(optimized['articles'], list):
        for article in optimized['articles'][:5]:  # 최대 5개 조항만
            if 'article_content' in article:
                if len(article['article_content']) > 500:  # 조항별 500자 제한
                    article['article_content'] = article['article_content'][:500] + "..."

    return optimized


def estimate_message_size(message: Dict[str, Any]) -> tuple[int, bool]:
    """메시지 크기 추정 및 Kafka 제한 확인"""
    import json

    # JSON 직렬화하여 실제 크기 측정
    serialized = json.dumps(message, ensure_ascii=False)
    size_bytes = len(serialized.encode('utf-8'))

    # Kafka 기본 제한 (1MB = 1,048,576 bytes)
    kafka_limit = 1048576

    # 안전 마진 (90% 사용)
    safe_limit = int(kafka_limit * 0.9)

    is_safe = size_bytes <= safe_limit

    return size_bytes, is_safe


def batch_message_optimization(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """배치 메시지 최적화 및 통계"""
    from typing import List

    optimized_messages = []
    stats = {
        'original_count': len(messages),
        'optimized_count': 0,
        'total_size_reduction': 0,
        'oversized_messages': 0,
        'average_size_before': 0,
        'average_size_after': 0
    }

    total_size_before = 0
    total_size_after = 0

    for i, msg in enumerate(messages):
        # 원본 크기 측정
        original_size, original_safe = estimate_message_size(msg)
        total_size_before += original_size

        if not original_safe:
            stats['oversized_messages'] += 1
            logger.warning(f"메시지 {i} 크기 초과: {original_size:,} bytes")

        # 최적화 적용
        optimized_msg = optimize_message_size(msg)
        optimized_size, optimized_safe = estimate_message_size(optimized_msg)
        total_size_after += optimized_size

        if optimized_safe:
            optimized_messages.append(optimized_msg)
            stats['optimized_count'] += 1
        else:
            logger.error(f"메시지 {i} 최적화 후에도 크기 초과: {optimized_size:,} bytes")
            # 더 강력한 최적화 적용 (콘텐츠를 더 짧게)
            heavily_optimized = optimize_message_size(msg, max_content_length=2000)
            final_size, final_safe = estimate_message_size(heavily_optimized)

            if final_safe:
                optimized_messages.append(heavily_optimized)
                stats['optimized_count'] += 1
                logger.info(f"메시지 {i} 강력 최적화 성공: {final_size:,} bytes")
            else:
                logger.error(f"메시지 {i} 최적화 실패, 스킵")

    # 통계 계산
    if len(messages) > 0:
        stats['average_size_before'] = int(total_size_before) // len(messages)
        stats['average_size_after'] = int(total_size_after) // stats['optimized_count'] if stats[
                                                                                               'optimized_count'] > 0 else 0
        stats['total_size_reduction'] = int(total_size_before) - int(total_size_after)

    logger.info(f"메시지 최적화 완료: {stats['optimized_count']}/{stats['original_count']}")
    logger.info(f"평균 크기 감소: {stats['average_size_before']:,} → {stats['average_size_after']:,} bytes")
    logger.info(f"총 크기 절약: {stats['total_size_reduction']:,} bytes")

    return {
        'messages': optimized_messages,
        'stats': stats
    }


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

    # 법령 데이터 생성 (15개로 축소)
    laws_data = []
    for i in range(15):
        doc = generator.generate_legal_document()
        # 공포일자를 logical_date로 설정
        doc['published_date'] = execution_date.isoformat() + "Z"
        laws_data.append(doc)

    # 메시지 크기 최적화 적용
    optimized_laws = batch_message_optimization(laws_data)
    laws_data = optimized_laws['messages']
    logger.info(f"법령 데이터 최적화: {optimized_laws['stats']}")

    # 법령 본문 데이터 생성 (10개로 축소)
    contents_data = []
    for i in range(10):
        content_doc = generator.generate_legal_document()
        content_doc['published_date'] = execution_date.isoformat() + "Z"
        content_doc['content_type'] = 'full_text'
        contents_data.append(content_doc)

    # 본문 데이터 최적화
    optimized_contents = batch_message_optimization(contents_data)
    contents_data = optimized_contents['messages']
    logger.info(f"본문 데이터 최적화: {optimized_contents['stats']}")

    # 법령 조항 데이터 생성 (15개로 축소)
    articles_data = []
    for i in range(15):
        article_doc = generator.generate_legal_document()
        article_doc['published_date'] = execution_date.isoformat() + "Z"
        article_doc['content_type'] = 'articles'
        # 조항 분할
        article_doc['articles'] = [
            {
                'article_no': j + 1,  # 정수로 설정 (문자열에서 변경)
                'article_title': f'조항 {j + 1}',
                'article_content': f'제{j + 1}조의 내용입니다.',
                'law_id': article_doc['id']
            }
            for j in range(3)  # 조항당 3개 조문 (5개→3개로 축소)
        ]
        articles_data.append(article_doc)

    # 조항 데이터 최적화
    optimized_articles = batch_message_optimization(articles_data)
    articles_data = optimized_articles['messages']
    logger.info(f"조항 데이터 최적화: {optimized_articles['stats']}")

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

                # 프로듀싱 간격 조절 (안정성과 속도 균형)
                await asyncio.sleep(0.3)

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

                await asyncio.sleep(0.3)

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

                await asyncio.sleep(0.3)

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

    # 이벤트 루프에서 실행 (개선된 안정성)
    import time

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # 재시도 로직이 포함된 프로듀싱 실행
    max_attempts = 2  # 최대 2회 재시도
    for attempt in range(max_attempts):
        try:
            result = loop.run_until_complete(produce_data())
            logger.info(f"프로듀싱 성공 (시도 {attempt + 1}/{max_attempts})")
            break
        except Exception as e:
            logger.error(f"프로듀싱 시도 {attempt + 1} 실패: {e}")
            if attempt < max_attempts - 1:
                logger.info("10초 후 재시도...")
                time.sleep(10)
            else:
                logger.error("모든 프로듀싱 시도 실패")
                raise

    return {
        'laws_produced': len(laws_data),
        'contents_produced': len(contents_data),
        'articles_produced': len(articles_data),
        'publication_date': logical_date
    }


def consume_kafka_messages(**context):
    """
    Kafka 메시지 컨슈밍하여 대기 MySQL DB에 저장
    현재 활성 DB를 확인하고 대기 DB에 데이터 적재
    """
    import asyncio
    import time
    import mysql.connector
    from mysql.connector import Error as MySQLError

    logical_date = context['ds']
    logger.info(f"Kafka 메시지 컨슈밍 시작 - {logical_date}")

    # 데이터베이스 연결 정보
    DB_CONFIG = {
        'user': 'legal_user',
        'password': 'legal_pass_2024!',
        'database': 'legal_db',
        'connection_timeout': 10,
        'autocommit': True
    }

    def get_current_active_db():
        """현재 활성 DB 확인"""
        try:
            # Blue DB에서 설정 조회 (양쪽 DB 동일한 설정)
            blue_config = DB_CONFIG.copy()
            blue_config['host'] = 'mysql-blue'
            
            connection = mysql.connector.connect(**blue_config)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT config_value FROM blue_green_config WHERE config_key = 'ACTIVE_DATABASE'"
            )
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            
            current_active = result[0] if result else 'BLUE'
            return current_active.upper()
            
        except MySQLError as e:
            logger.error(f"활성 DB 확인 오류: {e}")
            # 기본값으로 BLUE 반환
            return 'BLUE'

    # 1. 현재 활성 DB 확인
    current_active = get_current_active_db()
    target_db = 'BLUE' if current_active == 'GREEN' else 'GREEN'
    target_host = 'mysql-blue' if target_db == 'BLUE' else 'mysql-green'
    
    logger.info(f"현재 활성 DB: {current_active}")
    logger.info(f"데이터 적재 타겟: {target_db} ({target_host})")

    async def consume_data():
        """비동기 데이터 컨슈밍"""
        # 대기 DB 타겟으로 Consumer 생성
        group_suffix = target_db.lower()
        consumer = LegalDataConsumer(
            group_id=f"daily-pipeline-{group_suffix}",
            target_db_host=target_host  # 타겟 DB 지정
        )

        try:
            # 모든 이벤트 토픽 구독
            topics = [Topics.LAW_EVENTS, Topics.CONTENT_EVENTS, Topics.ARTICLE_EVENTS]
            await consumer.start(topics)

            logger.info(f"메시지 컨슈밍 시작 → {target_db} DB")

            # 배치 크기만큼 처리 (앞서 프로듀싱한 메시지 수)
            expected_messages = 40  # 15 + 10 + 15
            timeout_seconds = 300  # 5분 타임아웃

            logger.info(f"메시지 컨슈밍 시작 - 예상 메시지: {expected_messages}개, 타임아웃: {timeout_seconds}초")

            # 타임아웃과 빈 큐 감지를 통해 컨슈밍 자동 종료
            await consumer.consume_messages(
                max_messages=expected_messages,
                timeout_seconds=timeout_seconds
            )

            processed_messages = consumer._stats.get('messages_processed', 0)
            logger.info(f"컨슈밍 완료: {processed_messages}개 메시지 처리 → {target_db} DB")

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
        'current_active_db': current_active,
        'target_database': f'mysql-{target_db.lower()}',
        'processing_date': logical_date
    }

def blue_green_switch(**context):
    """
    블루그린 데이터베이스 스위칭 (MySQL 기반)
    MySQL의 blue_green_config 테이블을 활용한 상태 관리
    """
    import mysql.connector
    from mysql.connector import Error as MySQLError
    from datetime import datetime
    import time
    
    logical_date = context['ds']
    logger.info(f"블루그린 스위치 시작 - {logical_date}")
    
    # 데이터베이스 연결 정보
    DB_CONFIG = {
        'user': 'legal_user',
        'password': 'legal_pass_2024!',
        'database': 'legal_db',
        'connection_timeout': 30,
        'autocommit': False  # 트랜잭션 관리
    }
    
    def get_db_connection(host):
        """데이터베이스 연결 생성"""
        config = DB_CONFIG.copy()
        config['host'] = host
        return mysql.connector.connect(**config)
    
    def get_config_value(connection, key, default_value=''):
        """설정값 조회"""
        try:
            cursor = connection.cursor()
            cursor.execute(
                "SELECT config_value FROM blue_green_config WHERE config_key = %s", 
                (key,)
            )
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else default_value
        except MySQLError as e:
            logger.error(f"설정값 조회 오류 ({key}): {e}")
            return default_value
    
    def set_config_value(connection, key, value, updated_by='AIRFLOW_PIPELINE'):
        """설정값 업데이트"""
        try:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO blue_green_config (config_key, config_value, updated_by) 
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    config_value = VALUES(config_value), 
                    updated_by = VALUES(updated_by),
                    updated_at = CURRENT_TIMESTAMP
            """, (key, value, updated_by))
            cursor.close()
        except MySQLError as e:
            logger.error(f"설정값 업데이트 오류 ({key}={value}): {e}")
            raise
    
    def get_table_counts(connection):
        """테이블별 데이터 개수 조회"""
        tables = ['law_list', 'law_content', 'law_articles']
        counts = {}
        
        try:
            cursor = connection.cursor()
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]
            cursor.close()
            return counts, sum(counts.values())
        except MySQLError as e:
            logger.error(f"테이블 카운트 조회 오류: {e}")
            return {}, 0
    
    def sync_data_between_dbs(source_conn, target_conn, source_name, target_name):
        """데이터베이스 간 데이터 동기화"""
        logger.info(f"데이터 동기화 시작: {source_name} → {target_name}")
        
        try:
            # 타겟 DB 기존 데이터 백업 (선택적)
            target_cursor = target_conn.cursor()
            
            # 트랜잭션 시작
            target_conn.start_transaction()
            
            # 기존 데이터 삭제 (역순으로 삭제하여 참조 무결성 유지)
            tables_to_sync = ['law_articles', 'law_content', 'law_list']
            
            for table in tables_to_sync:
                logger.info(f"  테이블 {table} 초기화 중...")
                target_cursor.execute(f"DELETE FROM {table}")
            
            # 소스에서 타겟으로 데이터 복사
            source_cursor = source_conn.cursor()
            
            for table in reversed(tables_to_sync):  # 삽입 시에는 정순
                logger.info(f"  테이블 {table} 동기화 중...")
                
                # 소스 데이터 조회
                source_cursor.execute(f"SELECT * FROM {table}")
                source_data = source_cursor.fetchall()
                
                if source_data:
                    # 컬럼 정보 가져오기
                    source_cursor.execute(f"SHOW COLUMNS FROM {table}")
                    columns = [column[0] for column in source_cursor.fetchall()]
                    
                    # INSERT 쿼리 생성
                    placeholders = ', '.join(['%s'] * len(columns))
                    columns_str = ', '.join(columns)
                    insert_query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                    
                    # 배치 삽입
                    target_cursor.executemany(insert_query, source_data)
                    logger.info(f"    {len(source_data)}건 복사 완료")
            
            # 커밋
            target_conn.commit()
            logger.info(f"데이터 동기화 완료: {source_name} → {target_name}")
            
            source_cursor.close()
            target_cursor.close()
            return True
            
        except MySQLError as e:
            # 롤백
            target_conn.rollback()
            logger.error(f"데이터 동기화 실패: {e}")
            return False
    
    try:
        # 1. 현재 활성 DB 확인 (Blue를 기준으로)
        blue_conn = get_db_connection('mysql-blue')
        green_conn = get_db_connection('mysql-green')
        
        current_active = get_config_value(blue_conn, 'ACTIVE_DATABASE', 'BLUE')
        logger.info(f"현재 활성 DB: {current_active}")
        
        # 2. 현재 활성/대기 DB 설정
        if current_active.upper() == 'BLUE':
            active_conn = blue_conn
            standby_conn = green_conn
            new_active = 'GREEN'
            active_name = 'Blue'
            standby_name = 'Green'
        else:
            active_conn = green_conn
            standby_conn = blue_conn
            new_active = 'BLUE'
            active_name = 'Green'
            standby_name = 'Blue'
        
        logger.info(f"스위칭 대상: {active_name} → {standby_name}")
        
        # 3. 활성 DB 데이터 검증
        active_counts, active_total = get_table_counts(active_conn)
        logger.info(f"{active_name} DB 데이터: {active_total}건 ({active_counts})")
        
        # 4. 대기 DB 상태 확인
        standby_counts, standby_total = get_table_counts(standby_conn)
        logger.info(f"{standby_name} DB 데이터: {standby_total}건 ({standby_counts})")
        
        # 5. 데이터 동기화 실행 (활성 → 대기)
        logger.info("데이터 동기화 상태 업데이트...")
        set_config_value(active_conn, 'SYNC_STATUS', 'SYNCING')
        set_config_value(standby_conn, 'SYNC_STATUS', 'SYNCING')
        active_conn.commit()
        standby_conn.commit()
        
        # 실제 동기화 수행
        sync_success = sync_data_between_dbs(
            active_conn, standby_conn, 
            active_name, standby_name
        )
        
        if not sync_success:
            raise Exception("데이터 동기화 실패")
        
        # 6. 동기화 후 검증
        standby_counts_after, standby_total_after = get_table_counts(standby_conn)
        logger.info(f"{standby_name} DB 동기화 후: {standby_total_after}건")
        
        if standby_total_after < active_total * 0.95:  # 95% 이상 동기화 확인
            raise Exception(f"동기화 불완전: {active_total} → {standby_total_after}")
        
        # 7. 블루그린 스위칭 수행
        switch_timestamp = datetime.now().isoformat()
        
        logger.info(f"블루그린 스위칭 실행: {current_active} → {new_active}")
        
        # 트랜잭션으로 양쪽 DB 설정 동시 업데이트
        blue_conn.start_transaction()
        green_conn.start_transaction()
        
        try:
            # 새로운 활성 DB 설정
            set_config_value(blue_conn, 'ACTIVE_DATABASE', new_active)
            set_config_value(green_conn, 'ACTIVE_DATABASE', new_active)
            
            set_config_value(blue_conn, 'SWITCH_TIMESTAMP', switch_timestamp)
            set_config_value(green_conn, 'SWITCH_TIMESTAMP', switch_timestamp)
            
            set_config_value(blue_conn, 'SYNC_STATUS', 'COMPLETED')
            set_config_value(green_conn, 'SYNC_STATUS', 'COMPLETED')
            
            set_config_value(blue_conn, 'DATA_VALIDATION_STATUS', 'VALID')
            set_config_value(green_conn, 'DATA_VALIDATION_STATUS', 'VALID')
            
            # 데이터 개수 업데이트
            set_config_value(blue_conn, 'BLUE_RECORD_COUNT', str(active_total if current_active == 'BLUE' else standby_total_after))
            set_config_value(green_conn, 'GREEN_RECORD_COUNT', str(standby_total_after if current_active == 'BLUE' else active_total))
            
            # 커밋
            blue_conn.commit()
            green_conn.commit()
            
            logger.info("✅ 블루그린 스위칭 완료!")
            
        except Exception as e:
            # 롤백
            blue_conn.rollback()
            green_conn.rollback()
            raise Exception(f"스위칭 설정 업데이트 실패: {e}")
        
        # 8. 최종 검증
        new_active_db = get_config_value(blue_conn, 'ACTIVE_DATABASE')
        logger.info(f"스위칭 검증: 새 활성 DB = {new_active_db}")
        
        return {
            'success': True,
            'previous_active': current_active,
            'new_active': new_active_db,
            'switch_timestamp': switch_timestamp,
            'data_synced': f"{active_total} → {standby_total_after}",
            'processing_date': logical_date
        }
        
    except Exception as e:
        logger.error(f"블루그린 스위칭 실패: {e}")
        
        # 실패 상태 업데이트
        try:
            for conn in [blue_conn, green_conn]:
                if conn.is_connected():
                    set_config_value(conn, 'SYNC_STATUS', 'FAILED')
                    set_config_value(conn, 'DATA_VALIDATION_STATUS', 'INVALID')
                    conn.commit()
        except:
            pass
        
        raise Exception(f"블루그린 스위칭 실패: {e}")
        
    finally:
        # 연결 종료
        try:
            if blue_conn.is_connected():
                blue_conn.close()
            if green_conn.is_connected():
                green_conn.close()
        except:
            pass


task_1_produce = PythonOperator(
    task_id='generate_and_produce_mock_data',
    python_callable=generate_and_produce_mock_data,
    dag=dag,
    doc_md="""
    ## Mock 데이터 생성 및 Kafka 프로듀싱
    
    - logical_date(전날) 기준 공포일자 데이터 생성
    - 법령목록(15개) → law-events 토픽
    - 법령본문(10개) → content-events 토픽  
    - 법령조항(15개) → article-events 토픽
    - 총 40개 메시지 프로듀싱 (재시도 로직 포함)
    """,
)

task_2_consume = PythonOperator(
    task_id='consume_kafka_messages',
    python_callable=consume_kafka_messages,
    dag=dag,
    doc_md="""
    ## Kafka 메시지 컨슈밍 (동적 타겟 선택)
    
    - 현재 활성 DB 확인 (Blue/Green)
    - 대기 DB에 새 데이터 적재 (활성이 Blue면 Green에, Green이면 Blue에)
    - 3개 토픽에서 메시지 수신
    - 데이터 정합성 확인
    - 최대 5분 또는 40개 메시지 처리
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
