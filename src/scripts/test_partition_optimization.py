#!/usr/bin/env python3
"""
Kafka 파티션 최적화 테스트 스크립트
새로운 파티셔닝 전략의 효과를 시뮬레이션하고 검증
"""
import asyncio
import time
import json
from datetime import datetime, date
from typing import Dict, List, Any, Tuple
import hashlib
import random

# 프로젝트 모듈 import
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.logging_config import get_logger

logger = get_logger(__name__)

class PartitionSimulator:
    """파티션 분산 시뮬레이터"""
    
    def __init__(self, partition_count: int):
        self.partition_count = partition_count
        self.partitions = {i: [] for i in range(partition_count)}
    
    def add_message(self, key: str, message_size: int = 1024):
        """메시지를 파티션에 추가"""
        # 해시 기반 파티션 할당
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        partition_id = hash_value % self.partition_count
        
        self.partitions[partition_id].append({
            'key': key,
            'size': message_size,
            'timestamp': time.time()
        })
        
        return partition_id
    
    def get_distribution_stats(self) -> Dict[str, Any]:
        """파티션 분산 통계"""
        sizes = [len(self.partitions[i]) for i in range(self.partition_count)]
        total_messages = sum(sizes)
        
        if total_messages == 0:
            return {
                'total_messages': 0,
                'avg_per_partition': 0,
                'max_partition_size': 0,
                'min_partition_size': 0,
                'variance': 0,
                'distribution_score': 100
            }
        
        avg_size = total_messages / self.partition_count
        variance = sum((size - avg_size) ** 2 for size in sizes) / self.partition_count
        
        # 분산 점수 계산 (0-100, 100이 가장 균등한 분산)
        max_possible_variance = (total_messages ** 2) / 4  # 최악의 경우
        distribution_score = max(0, 100 - (variance / max_possible_variance) * 100)
        
        return {
            'total_messages': total_messages,
            'avg_per_partition': avg_size,
            'max_partition_size': max(sizes),
            'min_partition_size': min(sizes),
            'variance': variance,
            'distribution_score': distribution_score,
            'partition_sizes': sizes
        }

class LegacyPartitionStrategy:
    """기존 파티션 전략 (개선 전)"""
    
    @staticmethod
    def get_law_partition_key(law_id: str, **kwargs) -> str:
        """법령 이벤트 파티션 키 (기존 방식)"""
        return law_id
    
    @staticmethod
    def get_content_partition_key(law_id: str, **kwargs) -> str:
        """본문 이벤트 파티션 키 (기존 방식)"""
        return law_id
    
    @staticmethod
    def get_article_partition_key(law_master_no: str, article_no: int = None, **kwargs) -> str:
        """조항 이벤트 파티션 키 (기존 방식)"""
        return law_master_no

class OptimizedPartitionStrategy:
    """최적화된 파티션 전략 (개선 후)"""
    
    @staticmethod
    def get_law_partition_key(law_id: str, ministry_code: int = None, **kwargs) -> str:
        """법령 이벤트 파티션 키 (개선된 방식)"""
        if ministry_code:
            # 소관부처 기반 분산
            return f"ministry_{ministry_code % 3}"
        
        # 시간 기반 분산
        time_bucket = int(time.time() / 3600)
        combined_key = f"{law_id}_{time_bucket}"
        hash_value = int(hashlib.md5(combined_key.encode()).hexdigest(), 16)
        return str(hash_value % 1000000)
    
    @staticmethod
    def get_content_partition_key(law_id: str, content_size: int = 10000, **kwargs) -> str:
        """본문 이벤트 파티션 키 (개선된 방식)"""
        # 본문 크기 기반 분산
        size_bucket = "large" if content_size > 50000 else "medium" if content_size > 10000 else "small"
        combined_key = f"{law_id}_{size_bucket}"
        hash_value = int(hashlib.md5(combined_key.encode()).hexdigest(), 16)
        return str(hash_value % 1000000)
    
    @staticmethod
    def get_article_partition_key(law_master_no: str, article_no: int = None, 
                                  ministry_code: int = None, **kwargs) -> str:
        """조항 이벤트 파티션 키 (개선된 방식)"""
        if law_master_no and article_no:
            # 관련 조항 그룹핑 (10개 단위)
            article_group = article_no // 10
            
            if ministry_code:
                combined_key = f"ministry_{ministry_code}_group_{article_group}"
            else:
                combined_key = f"{law_master_no}_group_{article_group}"
                
            hash_value = int(hashlib.md5(combined_key.encode()).hexdigest(), 16)
            return str(hash_value % 1000000)
        
        return law_master_no

def generate_test_data() -> List[Dict[str, Any]]:
    """테스트 데이터 생성"""
    test_data = []
    
    # 소관부처별 법령 분포 (실제 데이터 기반 가정)
    ministry_distribution = {
        101: 500,   # 기획재정부 (많음)
        201: 300,   # 교육부
        301: 800,   # 법무부 (매우 많음)
        401: 150,   # 국방부
        501: 200,   # 행정안전부
        601: 100,   # 문화체육관광부
        701: 180,   # 농림축산식품부
        801: 120,   # 산업통상자원부
        901: 90,    # 보건복지부
        1001: 70    # 환경부
    }
    
    law_id_counter = 1
    
    for ministry_code, law_count in ministry_distribution.items():
        for _ in range(law_count):
            law_id = str(law_id_counter)
            law_master_no = str(law_id_counter * 100 + random.randint(1, 99))
            
            # 법령별 조항 수 (정규분포, 평균 25개)
            article_count = max(1, int(random.gauss(25, 10)))
            
            # 법령 본문 크기 (가변적)
            content_size = random.choice([
                random.randint(5000, 15000),   # 소규모 법령 (60%)
                random.randint(15000, 50000),  # 중간 규모 법령 (30%)
                random.randint(50000, 200000)  # 대규모 법령 (10%)
            ]) if random.random() < 0.4 else random.randint(5000, 15000)
            
            law_data = {
                'law_id': law_id,
                'law_master_no': law_master_no,
                'ministry_code': ministry_code,
                'article_count': article_count,
                'content_size': content_size
            }
            
            test_data.append(law_data)
            law_id_counter += 1
    
    return test_data

def simulate_partition_distribution(test_data: List[Dict[str, Any]], 
                                  strategy_class, partition_counts: Dict[str, int]) -> Dict[str, Any]:
    """파티션 분산 시뮬레이션"""
    
    # 각 토픽별 시뮬레이터 초기화
    simulators = {
        'law_events': PartitionSimulator(partition_counts['law_events']),
        'content_events': PartitionSimulator(partition_counts['content_events']),
        'article_events': PartitionSimulator(partition_counts['article_events'])
    }
    
    # 데이터 처리
    for law_data in test_data:
        # 1. 법령 이벤트
        law_key = strategy_class.get_law_partition_key(**law_data)
        simulators['law_events'].add_message(law_key, 1024)  # 평균 1KB
        
        # 2. 본문 이벤트  
        content_key = strategy_class.get_content_partition_key(**law_data)
        simulators['content_events'].add_message(content_key, law_data['content_size'])
        
        # 3. 조항 이벤트 (조항 수만큼)
        for article_no in range(1, law_data['article_count'] + 1):
            article_key = strategy_class.get_article_partition_key(
                law_data['law_master_no'], 
                article_no=article_no,
                ministry_code=law_data['ministry_code']
            )
            simulators['article_events'].add_message(article_key, 512)  # 평균 512B
    
    # 통계 수집
    results = {}
    for topic, simulator in simulators.items():
        results[topic] = simulator.get_distribution_stats()
    
    return results

def compare_strategies():
    """전략 비교"""
    print("🔄 Kafka 파티션 전략 비교 테스트")
    print("=" * 60)
    
    # 테스트 데이터 생성
    print("📊 테스트 데이터 생성 중...")
    test_data = generate_test_data()
    print(f"✅ 총 {len(test_data)}개 법령 데이터 생성 완료")
    
    # 파티션 수 설정
    legacy_partitions = {
        'law_events': 6,      # 기존 설정
        'content_events': 4,  # 기존 설정
        'article_events': 8   # 기존 설정
    }
    
    optimized_partitions = {
        'law_events': 3,      # 최적화된 설정
        'content_events': 6,  # 최적화된 설정  
        'article_events': 12  # 최적화된 설정
    }
    
    print("\n🔍 기존 전략 시뮬레이션...")
    legacy_results = simulate_partition_distribution(
        test_data, LegacyPartitionStrategy, legacy_partitions
    )
    
    print("⚡ 최적화된 전략 시뮬레이션...")
    optimized_results = simulate_partition_distribution(
        test_data, OptimizedPartitionStrategy, optimized_partitions
    )
    
    # 결과 비교
    print("\n📈 결과 비교")
    print("=" * 60)
    
    for topic in ['law_events', 'content_events', 'article_events']:
        legacy = legacy_results[topic]
        optimized = optimized_results[topic]
        
        print(f"\n📋 {topic.replace('_', ' ').title()}")
        print("-" * 40)
        print(f"파티션 수:")
        print(f"  기존:     {legacy_partitions[topic]}개")
        print(f"  최적화:   {optimized_partitions[topic]}개")
        
        print(f"총 메시지 수: {legacy['total_messages']:,}개")
        
        print(f"분산 점수 (높을수록 좋음):")
        print(f"  기존:     {legacy['distribution_score']:.1f}점")
        print(f"  최적화:   {optimized['distribution_score']:.1f}점")
        print(f"  개선:     {optimized['distribution_score'] - legacy['distribution_score']:+.1f}점")
        
        print(f"분산 (낮을수록 좋음):")
        print(f"  기존:     {legacy['variance']:.1f}")
        print(f"  최적화:   {optimized['variance']:.1f}")
        
        improvement = ((legacy['variance'] - optimized['variance']) / legacy['variance'] * 100) if legacy['variance'] > 0 else 0
        print(f"  개선:     {improvement:+.1f}%")
        
        print(f"파티션 크기 범위:")
        print(f"  기존:     {legacy['min_partition_size']} ~ {legacy['max_partition_size']}")
        print(f"  최적화:   {optimized['min_partition_size']} ~ {optimized['max_partition_size']}")
    
    # 전체 요약
    print(f"\n🎯 전체 요약")
    print("=" * 60)
    
    total_legacy_score = sum(legacy_results[topic]['distribution_score'] for topic in legacy_results) / 3
    total_optimized_score = sum(optimized_results[topic]['distribution_score'] for topic in optimized_results) / 3
    
    print(f"평균 분산 점수:")
    print(f"  기존 전략:     {total_legacy_score:.1f}점")
    print(f"  최적화 전략:   {total_optimized_score:.1f}점")
    print(f"  전체 개선:     {total_optimized_score - total_legacy_score:+.1f}점")
    
    if total_optimized_score > total_legacy_score:
        print(f"✅ 최적화된 파티션 전략이 {total_optimized_score - total_legacy_score:.1f}점 더 우수합니다!")
    else:
        print(f"⚠️ 기존 전략이 더 나은 결과를 보여줍니다.")
    
    # 상세 결과를 JSON으로 저장
    results = {
        'timestamp': datetime.now().isoformat(),
        'test_data_size': len(test_data),
        'legacy_strategy': {
            'partition_counts': legacy_partitions,
            'results': legacy_results,
            'avg_score': total_legacy_score
        },
        'optimized_strategy': {
            'partition_counts': optimized_partitions,
            'results': optimized_results,
            'avg_score': total_optimized_score
        },
        'improvement': {
            'score_improvement': total_optimized_score - total_legacy_score,
            'percentage_improvement': ((total_optimized_score - total_legacy_score) / total_legacy_score * 100) if total_legacy_score > 0 else 0
        }
    }
    
    # 결과 파일 저장
    with open('partition_optimization_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n💾 상세 결과가 'partition_optimization_results.json'에 저장되었습니다.")
    
    return results

def generate_hot_partition_scenario():
    """Hot Partition 시나리오 테스트"""
    print("\n🔥 Hot Partition 시나리오 테스트")
    print("=" * 60)
    
    # 특정 부처에 집중된 데이터 생성 (Hot Partition 유발)
    hot_ministry_data = []
    
    # 법무부(301)에 70% 집중
    for i in range(700):
        hot_ministry_data.append({
            'law_id': str(i + 10000),
            'law_master_no': str((i + 10000) * 100),
            'ministry_code': 301,  # 법무부 집중
            'article_count': 30,
            'content_size': 30000
        })
    
    # 나머지 부처에 30% 분산
    other_ministries = [101, 201, 401, 501]
    for i in range(300):
        ministry = random.choice(other_ministries)
        hot_ministry_data.append({
            'law_id': str(i + 20000),
            'law_master_no': str((i + 20000) * 100),
            'ministry_code': ministry,
            'article_count': 20,
            'content_size': 15000
        })
    
    print(f"📊 Hot Partition 테스트 데이터: {len(hot_ministry_data)}개 법령")
    print("   - 법무부(301): 70% 집중")
    print("   - 기타 부처: 30% 분산")
    
    # 기존 전략으로 시뮬레이션
    legacy_hot_results = simulate_partition_distribution(
        hot_ministry_data, LegacyPartitionStrategy, {'law_events': 6, 'content_events': 4, 'article_events': 8}
    )
    
    # 최적화 전략으로 시뮬레이션
    optimized_hot_results = simulate_partition_distribution(
        hot_ministry_data, OptimizedPartitionStrategy, {'law_events': 3, 'content_events': 6, 'article_events': 12}
    )
    
    print(f"\n🔥 Hot Partition 저항성 테스트 - 법령 이벤트")
    print("-" * 50)
    
    legacy_law = legacy_hot_results['law_events']
    optimized_law = optimized_hot_results['law_events']
    
    print(f"기존 전략 (Hot Partition 위험):")
    print(f"  최대 파티션: {legacy_law['max_partition_size']} 메시지")
    print(f"  최소 파티션: {legacy_law['min_partition_size']} 메시지")
    print(f"  분산 점수: {legacy_law['distribution_score']:.1f}점")
    
    print(f"최적화 전략 (Hot Partition 방지):")
    print(f"  최대 파티션: {optimized_law['max_partition_size']} 메시지")
    print(f"  최소 파티션: {optimized_law['min_partition_size']} 메시지")
    print(f"  분산 점수: {optimized_law['distribution_score']:.1f}점")
    
    hot_partition_improvement = optimized_law['distribution_score'] - legacy_law['distribution_score']
    print(f"Hot Partition 저항성 개선: {hot_partition_improvement:+.1f}점")
    
    if hot_partition_improvement > 10:
        print("✅ 최적화된 전략이 Hot Partition을 효과적으로 방지합니다!")
    else:
        print("⚠️ Hot Partition 방지 효과가 제한적입니다.")

def main():
    """메인 실행 함수"""
    print("🚀 Kafka 파티션 최적화 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 일반 시나리오 테스트
        results = compare_strategies()
        
        # Hot Partition 시나리오 테스트
        generate_hot_partition_scenario()
        
        print(f"\n✅ 모든 테스트 완료!")
        print(f"⏰ 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return results
        
    except Exception as e:
        logger.error("파티션 최적화 테스트 실패", error=str(e))
        print(f"❌ 테스트 실패: {str(e)}")
        return None

if __name__ == "__main__":
    main()
