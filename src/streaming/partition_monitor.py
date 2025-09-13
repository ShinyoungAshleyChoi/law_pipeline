"""Kafka 파티션 모니터링 및 최적화"""
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from kafka.admin import KafkaAdminClient, ConfigResource, ConfigResourceType
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import structlog
import json
import time

from .config import kafka_config, Topics
from ..logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class PartitionMetrics:
    """파티션 메트릭"""
    topic: str
    partition: int
    size_bytes: int
    message_count: int
    lag: int
    throughput_msg_per_sec: float
    last_update: datetime

@dataclass
class PartitionHealth:
    """파티션 건강 상태"""
    topic: str
    partition: int
    is_healthy: bool
    issues: List[str]
    recommendations: List[str]

@dataclass
class TopicAnalysis:
    """토픽 분석 결과"""
    topic: str
    total_partitions: int
    total_messages: int
    total_size_mb: float
    avg_partition_size_mb: float
    max_partition_size_mb: float
    min_partition_size_mb: float
    size_variance: float
    hot_partitions: List[int]
    cold_partitions: List[int]
    recommendations: List[str]

class PartitionMonitor:
    """파티션 모니터링 및 최적화"""
    
    def __init__(self):
        self.config = kafka_config
        self.admin_client = None
        self.consumer = None
        
    def start(self) -> None:
        """모니터 시작"""
        try:
            # Admin Client 초기화
            admin_config = {
                'bootstrap_servers': self.config.bootstrap_servers,
                'client_id': f"{self.config.client_id}-partition-monitor"
            }
            self.admin_client = KafkaAdminClient(**admin_config)
            
            logger.info("파티션 모니터 시작 완료")
            
        except Exception as e:
            logger.error("파티션 모니터 시작 실패", error=str(e))
            raise
    
    def stop(self) -> None:
        """모니터 중지"""
        if self.admin_client:
            self.admin_client.close()
            self.admin_client = None
            
        if self.consumer:
            self.consumer.close()
            self.consumer = None
            
        logger.info("파티션 모니터 중지 완료")
    
    def analyze_partition_distribution(self, topic: str) -> TopicAnalysis:
        """파티션 분산 분석"""
        try:
            if not self.admin_client:
                self.start()
            
            # 토픽 메타데이터 조회
            metadata = self.admin_client.describe_topics([topic])
            topic_metadata = metadata[topic]
            
            partition_metrics = []
            
            # 각 파티션별 메트릭 수집
            for partition_id in range(len(topic_metadata.partitions)):
                metrics = self._get_partition_metrics(topic, partition_id)
                partition_metrics.append(metrics)
            
            # 분산 분석
            sizes = [m.size_bytes / (1024*1024) for m in partition_metrics]  # MB 단위
            message_counts = [m.message_count for m in partition_metrics]
            
            total_size_mb = sum(sizes)
            avg_size = sum(sizes) / len(sizes) if sizes else 0
            size_variance = sum((x - avg_size) ** 2 for x in sizes) / len(sizes) if sizes else 0
            
            # Hot/Cold 파티션 감지
            hot_threshold = avg_size * 1.5  # 평균의 1.5배 이상
            cold_threshold = avg_size * 0.5  # 평균의 0.5배 미만
            
            hot_partitions = [i for i, size in enumerate(sizes) if size > hot_threshold]
            cold_partitions = [i for i, size in enumerate(sizes) if size < cold_threshold and size > 0]
            
            # 권장사항 생성
            recommendations = self._generate_partition_recommendations(
                topic, len(sizes), size_variance, hot_partitions, cold_partitions
            )
            
            return TopicAnalysis(
                topic=topic,
                total_partitions=len(partition_metrics),
                total_messages=sum(message_counts),
                total_size_mb=total_size_mb,
                avg_partition_size_mb=avg_size,
                max_partition_size_mb=max(sizes) if sizes else 0,
                min_partition_size_mb=min(sizes) if sizes else 0,
                size_variance=size_variance,
                hot_partitions=hot_partitions,
                cold_partitions=cold_partitions,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error("파티션 분산 분석 실패", topic=topic, error=str(e))
            raise
    
    def _get_partition_metrics(self, topic: str, partition: int) -> PartitionMetrics:
        """개별 파티션 메트릭 조회"""
        try:
            # Consumer로 파티션 정보 조회
            consumer_config = {
                'bootstrap_servers': self.config.bootstrap_servers,
                'group_id': f'partition-monitor-{int(time.time())}',
                'auto_offset_reset': 'earliest',
                'enable_auto_commit': False,
                'consumer_timeout_ms': 5000
            }
            
            consumer = KafkaConsumer(**consumer_config)
            
            from kafka import TopicPartition
            tp = TopicPartition(topic, partition)
            
            # 파티션 할당
            consumer.assign([tp])
            
            # 시작/끝 오프셋 조회
            beginning_offsets = consumer.beginning_offsets([tp])
            end_offsets = consumer.end_offsets([tp])
            
            start_offset = beginning_offsets[tp]
            end_offset = end_offsets[tp]
            message_count = end_offset - start_offset
            
            # 추정 크기 (메시지당 평균 1KB로 가정)
            estimated_size = message_count * 1024
            
            consumer.close()
            
            return PartitionMetrics(
                topic=topic,
                partition=partition,
                size_bytes=estimated_size,
                message_count=message_count,
                lag=0,  # Consumer lag은 별도 계산 필요
                throughput_msg_per_sec=0.0,  # 실시간 계산 필요
                last_update=datetime.now()
            )
            
        except Exception as e:
            logger.warning("파티션 메트릭 조회 실패", 
                         topic=topic, 
                         partition=partition, 
                         error=str(e))
            
            return PartitionMetrics(
                topic=topic,
                partition=partition,
                size_bytes=0,
                message_count=0,
                lag=0,
                throughput_msg_per_sec=0.0,
                last_update=datetime.now()
            )
    
    def _generate_partition_recommendations(self, topic: str, partition_count: int,
                                          size_variance: float, hot_partitions: List[int],
                                          cold_partitions: List[int]) -> List[str]:
        """파티션 최적화 권장사항 생성"""
        recommendations = []
        
        # 분산도 체크
        if size_variance > 1000:  # 높은 분산
            recommendations.append(
                f"파티션 간 크기 차이가 큽니다 (분산: {size_variance:.1f}MB²). "
                "파티션 키 전략을 재검토하세요."
            )
        
        # Hot Partition 경고
        if hot_partitions:
            recommendations.append(
                f"Hot Partition 감지: {hot_partitions}. "
                "시간 기반 분산이나 추가 해시를 고려하세요."
            )
        
        # Cold Partition 경고
        if len(cold_partitions) > partition_count * 0.3:
            recommendations.append(
                f"사용률이 낮은 파티션이 많습니다: {len(cold_partitions)}개. "
                "파티션 수 감소를 고려하세요."
            )
        
        # 토픽별 특화 권장사항
        if topic == Topics.LAW_EVENTS:
            if partition_count > 5:
                recommendations.append(
                    "법령 이벤트는 볼륨이 낮으므로 파티션 수를 3개로 줄이는 것을 권장합니다."
                )
        elif topic == Topics.ARTICLE_EVENTS:
            if partition_count < 10:
                recommendations.append(
                    "조항 이벤트는 높은 볼륨이므로 파티션 수를 12개로 늘리는 것을 권장합니다."
                )
        
        # 성능 권장사항
        if not recommendations:
            recommendations.append("파티션 분산이 양호합니다. 현재 설정을 유지하세요.")
        
        return recommendations
    
    def check_consumer_lag(self, group_id: str, topic: str) -> Dict[int, int]:
        """Consumer 그룹의 파티션별 lag 조회"""
        try:
            if not self.admin_client:
                self.start()
            
            # Consumer 그룹 오프셋 조회
            group_offsets = self.admin_client.list_consumer_group_offsets(group_id)
            
            # 토픽의 현재 오프셋 조회
            consumer = KafkaConsumer(
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=f'lag-checker-{int(time.time())}',
                enable_auto_commit=False
            )
            
            from kafka import TopicPartition
            partitions = [TopicPartition(topic, i) for i in range(12)]  # 최대 파티션 수 가정
            
            end_offsets = consumer.end_offsets(partitions)
            consumer.close()
            
            lag_info = {}
            for tp, current_offset in end_offsets.items():
                if tp in group_offsets:
                    consumer_offset = group_offsets[tp].offset
                    lag = current_offset - consumer_offset
                    lag_info[tp.partition] = max(0, lag)
                else:
                    lag_info[tp.partition] = current_offset
            
            return lag_info
            
        except Exception as e:
            logger.error("Consumer lag 조회 실패", 
                        group_id=group_id, 
                        topic=topic, 
                        error=str(e))
            return {}
    
    def generate_health_report(self) -> Dict[str, Any]:
        """전체 파티션 건강 상태 리포트"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'topics': {},
            'overall_health': 'good',
            'critical_issues': [],
            'warnings': []
        }
        
        try:
            # 각 토픽별 분석
            for topic in Topics.event_topics():
                analysis = self.analyze_partition_distribution(topic)
                
                report['topics'][topic] = {
                    'partition_count': analysis.total_partitions,
                    'total_size_mb': analysis.total_size_mb,
                    'size_variance': analysis.size_variance,
                    'hot_partitions': analysis.hot_partitions,
                    'recommendations': analysis.recommendations
                }
                
                # 심각한 문제 감지
                if analysis.hot_partitions:
                    report['critical_issues'].append(
                        f"{topic}: Hot partitions detected - {analysis.hot_partitions}"
                    )
                    report['overall_health'] = 'critical'
                
                # 경고 사항
                if analysis.size_variance > 500:
                    report['warnings'].append(
                        f"{topic}: High partition size variance ({analysis.size_variance:.1f})"
                    )
                    if report['overall_health'] == 'good':
                        report['overall_health'] = 'warning'
            
        except Exception as e:
            logger.error("건강 상태 리포트 생성 실패", error=str(e))
            report['overall_health'] = 'error'
            report['critical_issues'].append(f"Health check failed: {str(e)}")
        
        return report
    
    def suggest_partition_rebalancing(self, topic: str) -> Dict[str, Any]:
        """파티션 리밸런싱 제안"""
        analysis = self.analyze_partition_distribution(topic)
        
        suggestions = {
            'topic': topic,
            'current_partitions': analysis.total_partitions,
            'recommended_partitions': analysis.total_partitions,
            'partition_key_strategy': 'current',
            'expected_improvement': {},
            'migration_plan': []
        }
        
        # 데이터 볼륨 기반 최적 파티션 수 계산
        daily_volume = analysis.total_messages  # 일일 메시지 수 가정
        optimal_partitions = self._calculate_optimal_partitions(topic, daily_volume)
        
        suggestions['recommended_partitions'] = optimal_partitions
        
        # 파티션 키 전략 제안
        if analysis.size_variance > 1000:
            suggestions['partition_key_strategy'] = 'improved_hash_with_time'
            suggestions['expected_improvement']['size_variance_reduction'] = '60%'
        
        # 마이그레이션 계획
        if optimal_partitions != analysis.total_partitions:
            suggestions['migration_plan'] = [
                f"1. 새로운 토픽 생성: {topic}-v2 (파티션: {optimal_partitions}개)",
                "2. 점진적 트래픽 전환 (24시간에 걸쳐 10%씩)",
                "3. 기존 토픽 데이터 마이그레이션",
                "4. 기존 토픽 제거"
            ]
        
        return suggestions
    
    def _calculate_optimal_partitions(self, topic: str, daily_volume: int) -> int:
        """최적 파티션 수 계산"""
        # 기본 처리량 가정 (메시지/초)
        base_throughput = {
            Topics.LAW_EVENTS: 10,       # 낮은 볼륨
            Topics.CONTENT_EVENTS: 50,   # 중간 볼륨
            Topics.ARTICLE_EVENTS: 200,  # 높은 볼륨
            Topics.BATCH_STATUS: 5,      # 매우 낮은 볼륨
            Topics.NOTIFICATIONS: 20     # 낮은 볼륨
        }
        
        target_throughput = base_throughput.get(topic, 50)
        daily_seconds = 24 * 60 * 60
        required_throughput = daily_volume / daily_seconds
        
        # Consumer당 처리 가능한 메시지 수 (초당)
        consumer_capacity = target_throughput * 0.7  # 70% 활용률
        
        optimal_count = max(1, int(required_throughput / consumer_capacity))
        
        # 토픽별 제한
        limits = {
            Topics.LAW_EVENTS: (1, 5),
            Topics.CONTENT_EVENTS: (2, 10),
            Topics.ARTICLE_EVENTS: (6, 20),
            Topics.BATCH_STATUS: (1, 1),
            Topics.NOTIFICATIONS: (1, 3)
        }
        
        min_partitions, max_partitions = limits.get(topic, (1, 12))
        return min(max(optimal_count, min_partitions), max_partitions)

# 전역 모니터 인스턴스
partition_monitor = PartitionMonitor()

def main():
    """CLI 실행용 메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Kafka 파티션 모니터')
    parser.add_argument('--action', choices=['analyze', 'health', 'suggest'], 
                       default='health', help='실행할 액션')
    parser.add_argument('--topic', help='분석할 토픽 (analyze, suggest 액션용)')
    
    args = parser.parse_args()
    
    try:
        partition_monitor.start()
        
        if args.action == 'analyze':
            if not args.topic:
                print("--topic 옵션이 필요합니다")
                return
            
            analysis = partition_monitor.analyze_partition_distribution(args.topic)
            print(json.dumps(analysis.__dict__, indent=2, default=str, ensure_ascii=False))
            
        elif args.action == 'health':
            report = partition_monitor.generate_health_report()
            print(json.dumps(report, indent=2, default=str, ensure_ascii=False))
            
        elif args.action == 'suggest':
            if not args.topic:
                print("--topic 옵션이 필요합니다")
                return
                
            suggestions = partition_monitor.suggest_partition_rebalancing(args.topic)
            print(json.dumps(suggestions, indent=2, default=str, ensure_ascii=False))
            
    finally:
        partition_monitor.stop()

if __name__ == "__main__":
    main()
