#!/usr/bin/env python3
"""Mock API 테스트 스크립트"""
import sys
import asyncio
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mock.api_mock import create_mock_api_client


async def test_mock_api():
    """Mock API 기능 테스트"""
    print("🧪 Mock API 테스트를 시작합니다...\n")
    
    # Mock API 클라이언트 생성 (빠른 테스트를 위해 지연 비활성화)
    client = create_mock_api_client(enable_delay=False, error_rate=0.0)
    
    try:
        # 1. 법령 목록 조회 테스트
        print("1️⃣ 법령 목록 조회 테스트")
        print("-" * 30)
        
        laws_response = await client.get_law_list_async({'display': 5})
        
        if 'LawSearch' in laws_response and laws_response['LawSearch']['law']:
            laws = laws_response['LawSearch']['law']
            print(f"✅ 법령 {len(laws)}개 조회 성공:")
            
            for i, law in enumerate(laws[:3], 1):
                print(f"   {i}. {law['법령명']}")
                print(f"      - ID: {law['법령ID']}")
                print(f"      - 구분: {law['법령구분']}")
                print(f"      - 소관부처: {law['소관부처']}")
                print()
            
            # 첫 번째 법령으로 상세 조회 테스트
            first_law_id = laws[0]['법령ID']
            
            # 2. 법령 내용 조회 테스트
            print("2️⃣ 법령 내용 조회 테스트")
            print("-" * 30)
            
            content_response = await client.get_law_content_async(first_law_id)
            
            if 'LawContent' in content_response and 'law' in content_response['LawContent']:
                law_content = content_response['LawContent']['law']
                print(f"✅ 법령 내용 조회 성공:")
                print(f"   제목: {law_content['법령명']}")
                print(f"   내용 (첫 100자): {law_content['법령내용'][:100]}...")
                print()
            
            # 3. 법령 조문 조회 테스트
            print("3️⃣ 법령 조문 조회 테스트")
            print("-" * 30)
            
            articles_response = await client.get_law_articles_async(first_law_id)
            
            if 'LawArticles' in articles_response and 'articles' in articles_response['LawArticles']:
                articles = articles_response['LawArticles']['articles']
                print(f"✅ 조문 {len(articles)}개 조회 성공:")
                
                for article in articles[:3]:
                    print(f"   - {article['조문번호']}: {article['조문제목']}")
                print()
        
        # 4. 배치 조회 테스트
        print("4️⃣ 배치 조회 테스트")
        print("-" * 30)
        
        # 법령 ID 목록 생성
        law_ids = [f"LAW-2024-{i:03d}" for i in range(1, 6)]
        batch_results = client.batch_get_laws(law_ids, batch_size=3)
        
        successful_count = sum(1 for result in batch_results if 'error' not in result)
        print(f"✅ 배치 조회 완료: {successful_count}/{len(law_ids)} 성공")
        print()
        
        # 5. 검색 테스트
        print("5️⃣ 법령 검색 테스트")
        print("-" * 30)
        
        search_response = client.search_laws("개인정보", {'limit': 3})
        
        if 'LawSearch' in search_response and search_response['LawSearch']['law']:
            search_results = search_response['LawSearch']['law']
            print(f"✅ '개인정보' 검색 결과 {len(search_results)}개:")
            
            for result in search_results:
                print(f"   - {result['법령명']} ({result['법령구분']})")
            print()
        
        # 6. 최근 법령 조회 테스트
        print("6️⃣ 최근 법령 조회 테스트")
        print("-" * 30)
        
        recent_response = client.get_recent_laws(days=30, limit=5)
        
        if 'LawSearch' in recent_response and recent_response['LawSearch']['law']:
            recent_laws = recent_response['LawSearch']['law']
            print(f"✅ 최근 30일 법령 {len(recent_laws)}개 조회:")
            
            for law in recent_laws:
                print(f"   - {law['법령명']} ({law['공포일자']})")
            print()
        
        # 7. API 통계 출력
        print("7️⃣ API 사용 통계")
        print("-" * 30)
        
        stats = client.get_stats()
        print(f"✅ API 사용 통계:")
        print(f"   - 총 요청 수: {stats['total_requests']}")
        print(f"   - 에러율: {stats['error_rate']}")
        print(f"   - 지연 시뮬레이션: {stats['use_delay']}")
        print(f"   - Mock 데이터 사용 가능: {stats['mock_data_available']}")
        print()
        
        print("🎉 모든 Mock API 테스트가 성공적으로 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ Mock API 테스트 중 오류 발생: {e}")
        print(f"   오류 타입: {type(e).__name__}")
        return False
    
    return True


def test_error_scenarios():
    """에러 시나리오 테스트"""
    print("\n🚨 에러 시나리오 테스트")
    print("-" * 40)
    
    # 에러율을 높인 클라이언트 생성
    error_client = create_mock_api_client(enable_delay=False, error_rate=1.0)  # 100% 에러율
    
    try:
        # 에러가 발생해야 함
        laws_response = error_client.get_law_list({'display': 5})
        print("❌ 예상된 에러가 발생하지 않았습니다.")
        return False
    except Exception as e:
        print(f"✅ 예상된 에러가 정상적으로 발생했습니다: {type(e).__name__}")
        return True


def test_sync_api():
    """동기 API 테스트"""
    print("\n🔄 동기 API 테스트")
    print("-" * 30)
    
    client = create_mock_api_client(enable_delay=False, error_rate=0.0)
    
    try:
        # 동기 법령 목록 조회
        laws_response = client.get_law_list({'display': 3})
        
        if 'LawSearch' in laws_response and laws_response['LawSearch']['law']:
            laws = laws_response['LawSearch']['law']
            print(f"✅ 동기 API로 법령 {len(laws)}개 조회 성공")
            
            # 첫 번째 법령의 내용 조회
            first_law_id = laws[0]['법령ID']
            content_response = client.get_law_content(first_law_id)
            
            if 'LawContent' in content_response:
                print(f"✅ 동기 API로 법령 내용 조회 성공")
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ 동기 API 테스트 실패: {e}")
        return False


async def main():
    """메인 테스트 함수"""
    print("🚀 Mock API 테스트 시작")
    print("=" * 50)
    
    # 비동기 API 테스트
    async_success = await test_mock_api()
    
    # 동기 API 테스트
    sync_success = test_sync_api()
    
    # 에러 시나리오 테스트
    error_success = test_error_scenarios()
    
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    print(f"비동기 API 테스트: {'✅ 성공' if async_success else '❌ 실패'}")
    print(f"동기 API 테스트: {'✅ 성공' if sync_success else '❌ 실패'}")
    print(f"에러 시나리오 테스트: {'✅ 성공' if error_success else '❌ 실패'}")
    
    all_success = async_success and sync_success and error_success
    print(f"\n전체 결과: {'🎉 모든 테스트 성공!' if all_success else '⚠️ 일부 테스트 실패'}")
    
    return all_success


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n테스트가 중단되었습니다.")
        sys.exit(1)
