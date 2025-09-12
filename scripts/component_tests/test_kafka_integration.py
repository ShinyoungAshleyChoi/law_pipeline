#!/usr/bin/env python3
"""
Kafka 통합 테스트 스크립트
- Kafka 연결 상태 확인
- Producer/Consumer 동작 테스트
- 토픽 생성 및 메시지 송수신 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from kafka.producer import LegalDataProducer
from kafka.consumer import LegalDataConsumer
from kafka.config import KAFKA_CONFIG
import json
import time
import logging
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_kafka_connection():
    """Kafka 브로커 연결 테스트"""
    try:
        producer = LegalDataProducer()
        # 연결 테스트를 위한 더미 메타데이터 요청
        metadata = producer.producer.list_topics(timeout=5)
        logger.info("✅ Kafka 브로커 연결 성공")
        producer.close()
        return True
    except Exception as e:
        logger.error(f"❌ Kafka 브로커 연결 실패: {e}")
        return False

def test_topic_creation():
    """토픽 생성 테스트"""
    try:
        from kafka.admin import KafkaAdminClient, NewTopic
        from kafka import KafkaProducer
        
        admin_client = KafkaAdminClient(
            bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
            client_id='test_admin'
        )
        
        # 테스트 토픽 생성
        test_topic = NewTopic(
            name='test-legal-data',
            num_partitions=1,
            replication_factor=1
        )
        
        try:
            admin_client.create_topics([test_topic], validate_only=False)
            logger.info("✅ 테스트 토픽 생성 성공")
        except Exception as e:
            if "already exists" in str(e):
                logger.info("✅ 테스트 토픽이 이미 존재합니다")
            else:
                raise e
        
        admin_client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ 토픽 생성 실패: {e}")
        return False

def test_producer_consumer():
    """Producer/Consumer 동작 테스트"""
    try:
        # 테스트용 메시지 데이터
        test_message = {
            "id": "test-001",
            "title": "테스트 법률 문서",
            "content": "이것은 Kafka 테스트용 메시지입니다.",
            "timestamp": datetime.now().isoformat(),
            "type": "법률"
        }
        
        # Producer 테스트
        producer = LegalDataProducer()
        result = producer.send_legal_document('test-legal-data', test_message)
        logger.info("✅ 메시지 전송 성공")
        producer.close()
        
        # Consumer 테스트 (별도 스레드에서 실행)
        received_message = None
        consumer_error = None
        
        def consume_test_message():
            nonlocal received_message, consumer_error
            try:
                consumer = LegalDataConsumer(['test-legal-data'], 'test-group')
                consumer.consumer.subscribe(['test-legal-data'])
                
                # 5초간 메시지 대기
                start_time = time.time()
                while time.time() - start_time < 5:
                    messages = consumer.consumer.poll(timeout_ms=1000)
                    for tp, msgs in messages.items():
                        for msg in msgs:
                            received_message = json.loads(msg.value.decode('utf-8'))
                            consumer.close()
                            return
                
                consumer.close()
            except Exception as e:
                consumer_error = e
        
        consumer_thread = threading.Thread(target=consume_test_message)
        consumer_thread.start()
        consumer_thread.join(timeout=10)
        
        if consumer_error:
            raise consumer_error
        
        if received_message:
            logger.info(f"✅ 메시지 수신 성공: {received_message['title']}")
            return True
        else:
            logger.warning("⚠️ 메시지 수신 시간 초과")
            return False
            
    except Exception as e:
        logger.error(f"❌ Producer/Consumer 테스트 실패: {e}")
        return False

def test_message_serialization():
    """메시지 직렬화/역직렬화 테스트"""
    try:
        # 복잡한 데이터 구조 테스트
        complex_message = {
            "document": {
                "id": "complex-001",
                "metadata": {
                    "tags": ["법률", "판례", "테스트"],
                    "created_at": datetime.now().isoformat(),
                    "version": 1.0
                },
                "content": {
                    "title": "복잡한 구조의 법률 문서",
                    "sections": [
                        {"section_id": 1, "title": "제1조", "content": "테스트 내용 1"},
                        {"section_id": 2, "title": "제2조", "content": "테스트 내용 2"}
                    ]
                }
            }
        }
        
        # JSON 직렬화 테스트
        serialized = json.dumps(complex_message, ensure_ascii=False, indent=2)
        deserialized = json.loads(serialized)
        
        if deserialized == complex_message:
            logger.info("✅ 메시지 직렬화/역직렬화 성공")
            return True
        else:
            logger.error("❌ 직렬화된 데이터가 원본과 다릅니다")
            return False
            
    except Exception as e:
        logger.error(f"❌ 메시지 직렬화 테스트 실패: {e}")
        return False

def cleanup_test_resources():
    """테스트 리소스 정리"""
    try:
        from kafka.admin import KafkaAdminClient
        
        admin_client = KafkaAdminClient(
            bootstrap_servers=KAFKA_CONFIG['bootstrap_servers'],
            client_id='test_cleanup'
        )
        
        # 테스트 토픽 삭제
        try:
            admin_client.delete_topics(['test-legal-data'], request_timeout_ms=5000)
            logger.info("✅ 테스트 토픽 정리 완료")
        except Exception as e:
            logger.info(f"테스트 토픽 정리 중 오류 (무시됨): {e}")
        
        admin_client.close()
        return True
        
    except Exception as e:
        logger.warning(f"테스트 리소스 정리 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    logger.info("=== Kafka 통합 테스트 시작 ===")
    
    test_results = []
    
    # 기본 연결 테스트
    test_results.append(("Kafka 연결", test_kafka_connection()))
    
    # 토픽 생성 테스트
    test_results.append(("토픽 생성", test_topic_creation()))
    
    # 메시지 직렬화 테스트
    test_results.append(("메시지 직렬화", test_message_serialization()))
    
    # Producer/Consumer 테스트
    test_results.append(("Producer/Consumer", test_producer_consumer()))
    
    # 테스트 리소스 정리
    cleanup_test_resources()
    
    logger.info("\n=== 테스트 결과 요약 ===")
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("\n🎉 모든 Kafka 테스트가 통과했습니다!")
    else:
        logger.error("\n⚠️ 일부 테스트가 실패했습니다. Kafka 설정을 확인해주세요.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
