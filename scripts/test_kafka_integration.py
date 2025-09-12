#!/usr/bin/env python3
"""Kafka 통합 테스트 스크립트"""

import sys
import os
import asyncio
import json
from datetime import datetime, date, timedelta

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.kafka.producer import LegalDataProducer
from src.kafka.consumer import LegalDataConsumer
from src.kafka.models import LawEvent, EventType
from src.kafka.config import Topics
from src.api.models import LawListItem
from src.database.repository import LegalDataRepository
from src.logging_config import get_logger

logger = get_logger(__name__)

async def test_producer_basic():
    """Producer 기본 테스트"""
    print("🔍 Producer 기본 테스트...")
    
    producer = LegalDataProducer()
    
    async with producer.session():
        # 헬스체크
        health = await producer.health_check()
        print(f"Producer 상태: {health['status']}")
        
        # 테스트 법령 데이터
        test_law = LawListItem(
            law_id=99999,
            law_master_no=99999,
            law_name="테스트 법령",
            enforcement_date=date.today(),
            promulgation_date=date.today() - timedelta(days=30),
            law_type="법률"
        )
        
        # 메시지 전송
        success = await producer.send_law_event(test_law, "test-correlation")
        print(f"메시지 전송 결과: {'성공' if success else '실패'}")
        
        return success

async def test_consumer_basic():
    """Consumer 기본 테스트"""
    print("🔍 Consumer 기본 테스트...")
    
    consumer = LegalDataConsumer(group_id="test-consumer")
    
    async with consumer.session([Topics.LAW_EVENTS]):
        print("Consumer 연결 성공")
        
        # 최대 3개 메시지만 처리
        await consumer.consume_messages(max_messages=3)
        
        stats = consumer.get_stats()
        print(f"처리된 메시지: {stats['messages_processed']}개")
        
        return True

async def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("🔍 데이터베이스 연결 테스트...")
    
    repository = LegalDataRepository()
    
    try:
        stats = repository.get_database_stats()
        print(f"총 법령 수: {stats.total_laws}")
        print(f"총 조항 수: {stats.total_articles}")
        
        return True
    except Exception as e:
        print(f"데이터베이스 연결 실패: {str(e)}")
        return False

async def run_integration_test():
    """통합 테스트 실행"""
    print("🧪 Kafka 통합 테스트 시작")
    print("=" * 50)
    
    tests = [
        ("데이터베이스 연결", test_database_connection),
        ("Producer 기본 테스트", test_producer_basic),
        ("Consumer 기본 테스트", test_consumer_basic),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n▶️ {test_name}...")
        try:
            result = await test_func()
            results[test_name] = "✅ 성공" if result else "❌ 실패"
        except Exception as e:
            results[test_name] = f"❌ 오류: {str(e)}"
    
    print("\n" + "=" * 50)
    print("🧪 테스트 결과 요약")
    print("=" * 50)
    
    for test_name, result in results.items():
        print(f"{result} {test_name}")
    
    success_count = sum(1 for r in results.values() if "✅" in r)
    total_count = len(results)
    
    print(f"\n📊 총 {total_count}개 테스트 중 {success_count}개 성공")
    
    if success_count == total_count:
        print("🎉 모든 테스트가 성공적으로 완료되었습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 설정을 확인해주세요.")

async def main():
    """메인 함수"""
    try:
        await run_integration_test()
    except KeyboardInterrupt:
        print("\n사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"테스트 실행 중 오류: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
