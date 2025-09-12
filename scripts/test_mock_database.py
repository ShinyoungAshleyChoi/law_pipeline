#!/usr/bin/env python3
"""Mock 데이터베이스 테스트 스크립트"""
import sys
import json
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mock.database_mock import (
    create_mock_db_connection, 
    create_persistent_mock_db,
    MockLegalDocumentRepository
)
from src.mock.data_generator import MockDataGenerator


def test_basic_db_operations():
    """기본 데이터베이스 작업 테스트"""
    print("🧪 Mock 데이터베이스 기본 작업 테스트")
    print("-" * 40)
    
    try:
        # 메모리 DB 연결 생성
        db = create_mock_db_connection()
        
        # 1. 통계 조회 테스트
        print("1️⃣ 기본 통계 조회")
        stats = db.get_statistics()
        print(f"   총 문서 수: {stats['total_documents']}")
        print(f"   문서 타입별: {stats['by_doc_type']}")
        print(f"   카테고리별: {stats['by_category']}")
        print()
        
        # 2. 문서 검색 테스트
        print("2️⃣ 문서 검색 테스트")
        recent_docs = db.get_recent_documents(30, 5)
        print(f"   최근 30일 문서: {len(recent_docs)}개")
        
        for doc in recent_docs[:3]:
            print(f"   - {doc['id']}: {doc['title'][:50]}...")
        print()
        
        # 3. 키워드 검색 테스트
        print("3️⃣ 키워드 검색 테스트")
        search_results = db.search_documents("개인정보", limit=3)
        print(f"   '개인정보' 검색 결과: {len(search_results)}개")
        
        for doc in search_results:
            print(f"   - {doc['id']}: {doc['title'][:40]}...")
        print()
        
        # 4. 특정 문서 조회 테스트
        print("4️⃣ 특정 문서 조회 테스트")
        if recent_docs:
            first_doc_id = recent_docs[0]['id']
            doc_detail = db.get_document(first_doc_id, include_tags=True)
            
            if doc_detail:
                print(f"   문서 ID: {doc_detail['id']}")
                print(f"   제목: {doc_detail['title'][:50]}...")
                print(f"   타입: {doc_detail['doc_type']}")
                print(f"   카테고리: {doc_detail['category']}")
                print(f"   태그: {doc_detail.get('tags', [])}")
                print()
        
        # 5. 새 문서 추가 테스트
        print("5️⃣ 새 문서 추가 테스트")
        generator = MockDataGenerator()
        new_doc = generator.generate_legal_document("TEST-2024-999")
        
        doc_id = db.insert_document(new_doc)
        print(f"   새 문서 추가 성공: {doc_id}")
        
        # 추가된 문서 확인
        added_doc = db.get_document(doc_id)
        if added_doc:
            print(f"   추가된 문서 확인: {added_doc['title'][:50]}...")
        print()
        
        # 6. 문서 업데이트 테스트
        print("6️⃣ 문서 업데이트 테스트")
        update_success = db.update_document(doc_id, {
            'status': 'updated',
            'tags': ['테스트', '업데이트']
        })
        
        if update_success:
            updated_doc = db.get_document(doc_id, include_tags=True)
            print(f"   업데이트 성공: 상태={updated_doc['status']}, 태그={updated_doc['tags']}")
        print()
        
        # 7. 처리 로그 조회 테스트
        print("7️⃣ 처리 로그 조회 테스트")
        logs = db.get_processing_logs(doc_id, limit=5)
        print(f"   문서 {doc_id}의 처리 로그 {len(logs)}개:")
        
        for log in logs:
            print(f"   - {log['timestamp']}: {log['action']} ({log['status']})")
        print()
        
        # 8. 동기화 상태 테스트
        print("8️⃣ 동기화 상태 테스트")
        db.update_sync_status('test', 'completed', {'processed': 100})
        
        sync_statuses = db.get_sync_status()
        print(f"   동기화 상태 {len(sync_statuses)}개:")
        
        for status in sync_statuses:
            print(f"   - {status['source_type']}: {status['status']}")
        print()
        
        # 9. 문서 삭제 테스트
        print("9️⃣ 문서 삭제 테스트")
        delete_success = db.delete_document(doc_id)
        print(f"   문서 삭제: {'✅ 성공' if delete_success else '❌ 실패'}")
        
        # 삭제 확인
        deleted_doc = db.get_document(doc_id)
        print(f"   삭제 확인: {'✅ 문서 없음' if not deleted_doc else '❌ 문서 존재'}")
        print()
        
        # 최종 통계
        final_stats = db.get_statistics()
        print(f"🏁 최종 문서 수: {final_stats['total_documents']}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ 기본 DB 테스트 실패: {e}")
        return False


def test_repository_pattern():
    """Repository 패턴 테스트"""
    print("\n🗄️ Repository 패턴 테스트")
    print("-" * 30)
    
    try:
        # Repository 생성
        repo = MockLegalDocumentRepository()
        
        # 1. 전체 문서 수 확인
        total_count = repo.count_all()
        print(f"1️⃣ 전체 문서 수: {total_count}")
        
        # 2. 최근 문서 조회
        recent_docs = repo.find_recent(days=30, limit=5)
        print(f"2️⃣ 최근 문서: {len(recent_docs)}개")
        
        # 3. 검색 기능
        search_results = repo.search("AI", doc_type="법률", limit=3)
        print(f"3️⃣ 'AI' 관련 법률: {len(search_results)}개")
        
        # 4. 새 문서 저장
        generator = MockDataGenerator()
        new_doc = generator.generate_legal_document("REPO-TEST-001")
        
        saved_id = repo.save(new_doc)
        print(f"4️⃣ 새 문서 저장: {saved_id}")
        
        # 5. ID로 문서 조회
        found_doc = repo.find_by_id(saved_id)
        print(f"5️⃣ ID 조회: {'✅ 성공' if found_doc else '❌ 실패'}")
        
        # 6. 문서 업데이트
        update_success = repo.update(saved_id, {'status': 'repo_updated'})
        print(f"6️⃣ 문서 업데이트: {'✅ 성공' if update_success else '❌ 실패'}")
        
        # 7. 통계 조회
        stats = repo.get_stats()
        print(f"7️⃣ Repository 통계: 총 {stats['total_documents']}개 문서")
        
        # 8. 문서 삭제
        delete_success = repo.delete(saved_id)
        print(f"8️⃣ 문서 삭제: {'✅ 성공' if delete_success else '❌ 실패'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Repository 패턴 테스트 실패: {e}")
        return False


def test_persistent_database():
    """영구 데이터베이스 테스트"""
    print("\n💾 영구 데이터베이스 테스트")
    print("-" * 35)
    
    try:
        # 영구 DB 생성 (파일로 저장)
        persistent_db = create_persistent_mock_db("test_persistent.db")
        
        # 초기 데이터 확인
        initial_stats = persistent_db.get_statistics()
        print(f"1️⃣ 초기 문서 수: {initial_stats['total_documents']}")
        
        # 새 데이터 추가
        generator = MockDataGenerator()
        test_docs = generator.generate_multiple_documents(5)
        
        inserted_count = persistent_db.bulk_insert_documents(test_docs)
        print(f"2️⃣ 대량 삽입: {inserted_count}개 성공")
        
        # 최종 통계
        final_stats = persistent_db.get_statistics()
        print(f"3️⃣ 최종 문서 수: {final_stats['total_documents']}")
        
        # DB 파일 확인
        db_path = Path("sample_data/test_persistent.db")
        print(f"4️⃣ DB 파일 존재: {'✅ 있음' if db_path.exists() else '❌ 없음'}")
        
        if db_path.exists():
            file_size = db_path.stat().st_size
            print(f"   파일 크기: {file_size:,} bytes")
        
        persistent_db.close()
        
        # 파일 정리 (테스트 후)
        if db_path.exists():
            db_path.unlink()
            print("5️⃣ 테스트 DB 파일 삭제 완료")
        
        return True
        
    except Exception as e:
        print(f"❌ 영구 DB 테스트 실패: {e}")
        return False


def test_bulk_operations():
    """대량 작업 테스트"""
    print("\n📦 대량 작업 테스트")
    print("-" * 25)
    
    try:
        db = create_mock_db_connection()
        generator = MockDataGenerator()
        
        # 1. 대량 데이터 생성
        print("1️⃣ 대량 데이터 생성 중...")
        bulk_docs = generator.generate_multiple_documents(20)
        
        # 2. 대량 삽입
        start_time = __import__('time').time()
        inserted_count = db.bulk_insert_documents(bulk_docs)
        end_time = __import__('time').time()
        
        print(f"2️⃣ 대량 삽입 완료: {inserted_count}개 ({end_time - start_time:.2f}초)")
        
        # 3. 통계 확인
        stats = db.get_statistics()
        print(f"3️⃣ 총 문서 수: {stats['total_documents']}")
        
        # 4. 대량 검색
        all_docs = db.search_documents(limit=100)
        print(f"4️⃣ 대량 조회: {len(all_docs)}개 반환")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ 대량 작업 테스트 실패: {e}")
        return False


def main():
    """메인 테스트 함수"""
    print("🚀 Mock 데이터베이스 테스트 시작")
    print("=" * 50)
    
    # 각 테스트 실행
    test_results = []
    
    test_results.append(("기본 DB 작업", test_basic_db_operations()))
    test_results.append(("Repository 패턴", test_repository_pattern()))
    test_results.append(("영구 데이터베이스", test_persistent_database()))
    test_results.append(("대량 작업", test_bulk_operations()))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    
    for test_name, success in test_results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"{test_name}: {status}")
    
    all_success = all(result[1] for result in test_results)
    print(f"\n전체 결과: {'🎉 모든 테스트 성공!' if all_success else '⚠️ 일부 테스트 실패'}")
    
    return all_success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n테스트가 중단되었습니다.")
        sys.exit(1)
