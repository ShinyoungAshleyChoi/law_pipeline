#!/usr/bin/env python3
"""
데이터베이스 연결 테스트 스크립트
- 데이터베이스 연결 상태 확인
- 기본 테이블 존재 여부 확인
- 샘플 데이터 삽입/조회 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from database.connection import get_database_connection
from database.repository import LegalDataRepository
from database.models import LegalDocument, CaseInfo
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_connection():
    """데이터베이스 연결 테스트"""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            logger.info("✅ 데이터베이스 연결 성공")
            return True
    except Exception as e:
        logger.error(f"❌ 데이터베이스 연결 실패: {e}")
        return False

def test_table_exists():
    """테이블 존재 여부 확인"""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]
            
            required_tables = ['legal_documents', 'case_info', 'processing_status']
            existing_tables = [table for table in required_tables if table in tables]
            
            logger.info(f"✅ 존재하는 테이블: {existing_tables}")
            if len(existing_tables) == len(required_tables):
                logger.info("✅ 모든 필수 테이블이 존재합니다")
                return True
            else:
                missing = set(required_tables) - set(existing_tables)
                logger.warning(f"⚠️ 누락된 테이블: {missing}")
                return False
    except Exception as e:
        logger.error(f"❌ 테이블 확인 실패: {e}")
        return False

def test_sample_data_operations():
    """샘플 데이터 삽입/조회 테스트"""
    try:
        repo = LegalDataRepository()
        
        # 샘플 법률문서 데이터
        sample_doc = LegalDocument(
            title="테스트 법률 문서",
            content="이것은 테스트용 법률 문서 내용입니다.",
            doc_type="법률",
            source="테스트 소스",
            published_date=datetime.now(),
            status="active"
        )
        
        # 데이터 삽입 테스트
        doc_id = repo.insert_legal_document(sample_doc)
        logger.info(f"✅ 샘플 문서 삽입 성공 (ID: {doc_id})")
        
        # 데이터 조회 테스트
        retrieved_doc = repo.get_legal_document(doc_id)
        if retrieved_doc:
            logger.info(f"✅ 데이터 조회 성공: {retrieved_doc.title}")
        
        # 데이터 삭제 (정리)
        repo.delete_legal_document(doc_id)
        logger.info("✅ 테스트 데이터 정리 완료")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 샘플 데이터 작업 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    logger.info("=== 데이터베이스 연결 테스트 시작 ===")
    
    test_results = []
    test_results.append(("데이터베이스 연결", test_database_connection()))
    test_results.append(("테이블 존재 확인", test_table_exists()))
    test_results.append(("샘플 데이터 작업", test_sample_data_operations()))
    
    logger.info("\n=== 테스트 결과 요약 ===")
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("\n🎉 모든 데이터베이스 테스트가 통과했습니다!")
    else:
        logger.error("\n⚠️ 일부 테스트가 실패했습니다. 설정을 확인해주세요.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
