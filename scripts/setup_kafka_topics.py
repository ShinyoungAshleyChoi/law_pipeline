#!/usr/bin/env python3
"""Kafka 토픽 생성 및 설정 스크립트"""

import sys
import time
import json
import logging
from typing import Dict, List
from kafka.admin import KafkaAdminClient, ConfigResource, ConfigResourceType, NewTopic
from kafka import KafkaProducer
from kafka.errors import TopicAlreadyExistsError, KafkaError

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KafkaTopicSetup:
    """Kafka 토픽 설정 클래스"""
    
    def __init__(self, bootstrap_servers: List[str] = None):
        self.bootstrap_servers = bootstrap_servers or [
            'localhost:9092',
            'localhost:9093', 
            'localhost:9094'
        ]
        
        try:
            self.admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                request_timeout_ms=10000,
                connections_max_idle_ms=60000
            )
            logger.info("Kafka Admin Client 초기화 완료")
        except Exception as e:
            logger.error(f"Kafka Admin Client 초기화 실패: {e}")
            sys.exit(1)
    
    def wait_for_kafka(self, max_retries: int = 30, retry_delay: int = 2):
        """Kafka 클러스터가 준비될 때까지 대기"""
        logger.info("Kafka 클러스터 연결 대기 중...")
        
        for attempt in range(max_retries):
            try:
                # 클러스터 메타데이터 조회로 연결 확인
                metadata = self.admin_client.describe_cluster()
                logger.info(f"Kafka 클러스터 연결 성공 (시도 {attempt + 1}/{max_retries})")
                return True
                
            except Exception as e:
                logger.warning(f"Kafka 연결 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    logger.error("Kafka 클러스터 연결 실패")
                    return False
        
        return False
    
    def get_topic_configs(self) -> Dict[str, Dict[str, any]]:
        """토픽 설정 정의"""
        return {
            # 법령 이벤트 토픽 (주요 데이터 스트림)
            'legal-law-events': {
                'num_partitions': 6,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'delete',
                    'retention.ms': '604800000',  # 7일
                    'segment.ms': '86400000',     # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                    'max.message.bytes': '10485760',  # 10MB
                }
            },
            
            # 법령 본문 이벤트 토픽
            'legal-content-events': {
                'num_partitions': 4,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'delete',
                    'retention.ms': '604800000',  # 7일
                    'segment.ms': '86400000',     # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                    'max.message.bytes': '20971520',  # 20MB (본문이 클 수 있음)
                }
            },
            
            # 법령 조항 이벤트 토픽
            'legal-article-events': {
                'num_partitions': 8,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'delete',
                    'retention.ms': '604800000',  # 7일
                    'segment.ms': '86400000',     # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                    'max.message.bytes': '10485760',  # 10MB
                }
            },
            
            # 배치 작업 상태 토픽
            'legal-batch-status': {
                'num_partitions': 1,  # 순서 보장 필요
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'compact',
                    'retention.ms': '2592000000',  # 30일
                    'segment.ms': '86400000',      # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                }
            },
            
            # CDC (Change Data Capture) 토픽들
            'legal-cdc-laws': {
                'num_partitions': 3,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'compact',
                    'retention.ms': '1209600000',  # 14일
                    'segment.ms': '86400000',      # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                    'min.compaction.lag.ms': '60000',  # 1분
                }
            },
            
            'legal-cdc-content': {
                'num_partitions': 3,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'compact',
                    'retention.ms': '1209600000',  # 14일
                    'segment.ms': '86400000',      # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                    'min.compaction.lag.ms': '60000',  # 1분
                }
            },
            
            'legal-cdc-articles': {
                'num_partitions': 4,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'compact',
                    'retention.ms': '1209600000',  # 14일
                    'segment.ms': '86400000',      # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                    'min.compaction.lag.ms': '60000',  # 1분
                }
            },
            
            # 알림 토픽
            'legal-notifications': {
                'num_partitions': 2,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'delete',
                    'retention.ms': '259200000',   # 3일
                    'segment.ms': '43200000',      # 12시간
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                }
            },
            
            # 메트릭스 토픽
            'legal-metrics': {
                'num_partitions': 3,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'delete',
                    'retention.ms': '604800000',   # 7일
                    'segment.ms': '86400000',      # 1일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                }
            },
            
            # 데드 레터 큐
            'legal-dlq': {
                'num_partitions': 3,
                'replication_factor': 3,
                'config': {
                    'cleanup.policy': 'delete',
                    'retention.ms': '2592000000',  # 30일 (장기 보관)
                    'segment.ms': '604800000',     # 7일
                    'min.insync.replicas': '2',
                    'compression.type': 'lz4',
                }
            }
        }
    
    def create_topics(self):
        """토픽 생성"""
        topic_configs = self.get_topic_configs()
        topics_to_create = []
        
        for topic_name, config in topic_configs.items():
            new_topic = NewTopic(
                name=topic_name,
                num_partitions=config['num_partitions'],
                replication_factor=config['replication_factor'],
                topic_configs=config['config']
            )
            topics_to_create.append(new_topic)
        
        try:
            # 토픽 생성 요청
            response = self.admin_client.create_topics(topics_to_create, validate_only=False)
            
            # 응답 처리 - kafka-python 버전에 따른 다양한 응답 형태 처리
            logger.info(f"토픽 생성 응답 타입: {type(response)}")
            
            if hasattr(response, 'items'):
                # 딕셔너리 형태의 응답 (이전 버전)
                for topic_name, future in response.items():
                    try:
                        future.result()  # 결과 대기
                        logger.info(f"토픽 '{topic_name}' 생성 성공")
                    except TopicAlreadyExistsError:
                        logger.warning(f"토픽 '{topic_name}' 이미 존재함")
                    except Exception as e:
                        logger.error(f"토픽 '{topic_name}' 생성 실패: {e}")
            else:
                # 다른 형태의 응답 처리 (최신 버전)
                logger.info(f"토픽 생성 요청 전송됨: {[topic.name for topic in topics_to_create]}")
                
                # 각 토픽별로 개별 생성 시도
                success_count = 0
                for topic in topics_to_create:
                    try:
                        single_response = self.admin_client.create_topics([topic], validate_only=False)
                        logger.info(f"토픽 '{topic.name}' 생성 성공")
                        success_count += 1
                    except TopicAlreadyExistsError:
                        logger.warning(f"토픽 '{topic.name}' 이미 존재함")
                        success_count += 1
                    except Exception as e:
                        logger.error(f"토픽 '{topic.name}' 생성 실패: {e}")
                
                # 잠시 대기 후 토픽 목록으로 확인
                time.sleep(2)
                existing_topics = self.admin_client.list_topics()
                for topic in topics_to_create:
                    if topic.name in existing_topics:
                        logger.info(f"토픽 '{topic.name}' 존재 확인됨")
                    else:
                        logger.warning(f"토픽 '{topic.name}' 생성 상태 불명확")
                    
        except Exception as e:
            logger.error(f"토픽 생성 요청 실패: {e}")
            logger.error(f"오류 상세: {str(e)}")
            
            # 개별 토픽 생성으로 재시도
            logger.info("개별 토픽 생성으로 재시도...")
            success_count = 0
            for topic in topics_to_create:
                try:
                    single_topic = NewTopic(
                        name=topic.name,
                        num_partitions=topic.num_partitions,
                        replication_factor=topic.replication_factor,
                        topic_configs=topic.topic_configs
                    )
                    self.admin_client.create_topics([single_topic], validate_only=False)
                    logger.info(f"토픽 '{topic.name}' 개별 생성 성공")
                    success_count += 1
                except TopicAlreadyExistsError:
                    logger.warning(f"토픽 '{topic.name}' 이미 존재함")
                    success_count += 1
                except Exception as single_error:
                    logger.error(f"토픽 '{topic.name}' 개별 생성 실패: {single_error}")
            
            if success_count == 0:
                return False
        
        return True
    
    def list_topics(self):
        """토픽 목록 조회"""
        try:
            metadata = self.admin_client.list_topics()
            logger.info("현재 토픽 목록:")
            for topic in sorted(metadata):
                if topic.startswith('legal-'):
                    logger.info(f"  - {topic}")
            return list(metadata)
        except Exception as e:
            logger.error(f"토픽 목록 조회 실패: {e}")
            return []
    
    def describe_topics(self, topic_names: List[str] = None):
        """토픽 상세 정보 조회"""
        if topic_names is None:
            # legal- 로 시작하는 토픽들만 조회
            all_topics = self.admin_client.list_topics()
            topic_names = [t for t in all_topics if t.startswith('legal-')]

        if not topic_names:
            logger.info("legal- 로 시작하는 토픽이 없습니다.")
            return

        logger.info(f"조회할 토픽 목록: {topic_names}")

        # 토픽 상세 정보 조회
        topic_metadata = self.admin_client.describe_topics(topic_names)

        # 응답 형태 확인 및 처리
        logger.info(f"describe_topics 응답 타입: {type(topic_metadata)}")

        if topic_names:
            for topic_name in topic_names:
                try:
                    single_metadata = self.admin_client.describe_topics([topic_name])
                    logger.info(f"토픽 '{topic_name}' 개별 조회 성공")
                    # 간단한 정보 출력
                    logger.info(f"  - 토픽명: {topic_name}")
                except Exception as single_error:
                    logger.error(f"토픽 '{topic_name}' 개별 조회 실패: {single_error}")

    
    def _print_topic_details(self, topic_name: str, metadata):
        """토픽 상세 정보 출력 헬퍼 함수"""
        try:
            logger.info(f"\n토픽: {topic_name}")
            
            if hasattr(metadata, 'partitions') and metadata.partitions:
                logger.info(f"  파티션 수: {len(metadata.partitions)}")
                logger.info(f"  복제 팩터: {len(metadata.partitions[0].replicas) if metadata.partitions else 0}")
                
                for partition in metadata.partitions:
                    logger.info(f"    파티션 {partition.partition}: 리더={partition.leader}, "
                              f"복제본={partition.replicas}, ISR={partition.isr}")
            else:
                logger.info(f"  메타데이터: {metadata}")
                
        except Exception as e:
            logger.error(f"토픽 '{topic_name}' 상세 정보 출력 실패: {e}")
            logger.info(f"  원본 메타데이터: {metadata}")
    
    def test_connection(self):
        """Kafka 연결 테스트"""
        # 더 기본적인 연결 테스트 시도
        try:
            logger.info("기본 연결 테스트 시도...")

            # 단순히 토픽 목록 조회로 연결 확인
            topics = self.admin_client.list_topics()
            logger.info(f"토픽 목록 조회 성공: {len(topics)}개 토픽 발견")

            # 클러스터 메타데이터 조회
            try:
                cluster_metadata = self.admin_client.describe_cluster()
                logger.info(f"cluster_metadata: {cluster_metadata}")
                logger.info("클러스터 메타데이터 조회 성공")
                return True
            except Exception as cluster_error:
                logger.error(f"클러스터 메타데이터 조회 실패: {cluster_error}")

            # 최소한 토픽 목록은 조회 가능한 경우
            if len(topics) >= 0:
                logger.info("기본적인 Kafka 연결은 가능한 상태")
                return True

        except Exception as basic_error:
            logger.error(f"기본 연결 테스트 실패: {basic_error}")

        return False

    def setup_all(self):
        """전체 설정 실행"""
        logger.info("Kafka 토픽 설정 시작")
        
        # 1. Kafka 연결 대기
        if not self.wait_for_kafka():
            logger.error("Kafka 클러스터 연결 실패")
            return False
        
        # 2. 토픽 생성
        if not self.create_topics():
            logger.error("토픽 생성 실패")
            return False
        
        # 3. 토픽 목록 확인
        self.list_topics()
        
        # 4. 토픽 상세 정보 확인
        self.describe_topics()
        
        # 5. 연결 테스트
        if not self.test_connection():
            logger.error("연결 테스트 실패")
            return False
        
        logger.info("Kafka 토픽 설정 완료")
        return True

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kafka 토픽 설정 스크립트')
    parser.add_argument('--servers', nargs='+', 
                       default=['localhost:9092', 'localhost:9093', 'localhost:9094'],
                       help='Kafka 부트스트랩 서버 목록')
    parser.add_argument('--action', choices=['setup', 'list', 'describe', 'test'], 
                       default='setup',
                       help='실행할 작업')
    parser.add_argument('--topics', nargs='*',
                       help='특정 토픽 목록 (describe 작업용)')
    
    args = parser.parse_args()
    
    setup = KafkaTopicSetup(args.servers)
    
    if args.action == 'setup':
        success = setup.setup_all()
        sys.exit(0 if success else 1)
    elif args.action == 'list':
        setup.list_topics()
    elif args.action == 'describe':
        setup.describe_topics(args.topics)
    elif args.action == 'test':
        success = setup.test_connection()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
