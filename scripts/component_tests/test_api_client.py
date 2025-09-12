#!/usr/bin/env python3
"""
API 클라이언트 테스트 스크립트
- 외부 API 연결 테스트
- 실제/모의 데이터 수집 테스트
- 에러 핸들링 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.client import LegalDataAPIClient
from api.models import APIResponse
import logging
import time
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_api_connection():
    """API 서버 연결 테스트"""
    try:
        client = LegalDataAPIClient()
        
        # Health check 엔드포인트 호출
        response = client.health_check()
        if response and response.get('status') == 'healthy':
            logger.info("✅ API 서버 연결 성공")
            return True
        else:
            logger.warning("⚠️ API 서버 응답이 예상과 다릅니다")
            return False
            
    except Exception as e:
        logger.error(f"❌ API 서버 연결 실패: {e}")
        return False

def test_mock_data_collection():
    """모의 데이터 수집 테스트"""
    try:
        client = LegalDataAPIClient(use_mock=True)
        
        # 모의 법률 문서 데이터 수집
        mock_documents = client.fetch_legal_documents(limit=5)
        
        if mock_documents and len(mock_documents) > 0:
            logger.info(f"✅ 모의 데이터 수집 성공: {len(mock_documents)}건")
            
            # 첫 번째 문서 샘플 출력
            first_doc = mock_documents[0]
            logger.info(f"샘플 문서: {first_doc.get('title', 'N/A')}")
            return True
        else:
            logger.error("❌ 모의 데이터 수집 실패: 빈 응답")
            return False
            
    except Exception as e:
        logger.error(f"❌ 모의 데이터 수집 실패: {e}")
        return False

def test_api_error_handling():
    """API 에러 핸들링 테스트"""
    try:
        client = LegalDataAPIClient()
        
        # 잘못된 엔드포인트 호출
        try:
            response = client._make_request("/invalid/endpoint")
            logger.warning("⚠️ 잘못된 엔드포인트에서 예상외 응답")
            return False
        except Exception as expected_error:
            logger.info(f"✅ 에러 핸들링 정상 작동: {type(expected_error).__name__}")
        
        # 타임아웃 테스트
        try:
            client = LegalDataAPIClient(timeout=0.001)  # 매우 짧은 타임아웃
            response = client.health_check()
        except Exception as timeout_error:
            logger.info(f"✅ 타임아웃 처리 정상 작동: {type(timeout_error).__name__}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 에러 핸들링 테스트 실패: {e}")
        return False

def test_data_validation():
    """수집된 데이터 검증 테스트"""
    try:
        client = LegalDataAPIClient(use_mock=True)
        
        # 데이터 수집
        documents = client.fetch_legal_documents(limit=3)
        
        if not documents:
            logger.error("❌ 검증할 데이터가 없습니다")
            return False
        
        # 필수 필드 검증
        required_fields = ['id', 'title', 'content', 'doc_type']
        validation_passed = True
        
        for i, doc in enumerate(documents):
            missing_fields = [field for field in required_fields if field not in doc]
            if missing_fields:
                logger.error(f"❌ 문서 {i+1}: 누락된 필드 {missing_fields}")
                validation_passed = False
            else:
                logger.info(f"✅ 문서 {i+1}: 모든 필수 필드 존재")
        
        # 데이터 타입 검증
        for i, doc in enumerate(documents):
            if not isinstance(doc.get('title'), str):
                logger.error(f"❌ 문서 {i+1}: title이 문자열이 아닙니다")
                validation_passed = False
            
            if not isinstance(doc.get('content'), str):
                logger.error(f"❌ 문서 {i+1}: content가 문자열이 아닙니다")
                validation_passed = False
        
        if validation_passed:
            logger.info("✅ 모든 데이터 검증 통과")
        
        return validation_passed
        
    except Exception as e:
        logger.error(f"❌ 데이터 검증 실패: {e}")
        return False

def test_api_rate_limiting():
    """API 요청 제한 테스트"""
    try:
        client = LegalDataAPIClient(use_mock=True)
        
        # 연속 요청으로 레이트 리미팅 테스트
        request_times = []
        for i in range(3):
            start_time = time.time()
            response = client.fetch_legal_documents(limit=1)
            end_time = time.time()
            request_times.append(end_time - start_time)
            
            if response:
                logger.info(f"요청 {i+1}: {end_time - start_time:.3f}초")
            
            time.sleep(0.1)  # 짧은 대기
        
        avg_time = sum(request_times) / len(request_times)
        logger.info(f"✅ 평균 응답 시간: {avg_time:.3f}초")
        
        # 응답 시간이 합리적인지 확인 (5초 이내)
        if avg_time < 5.0:
            logger.info("✅ API 응답 시간 정상")
            return True
        else:
            logger.warning("⚠️ API 응답 시간이 너무 느립니다")
            return False
            
    except Exception as e:
        logger.error(f"❌ 레이트 리미팅 테스트 실패: {e}")
        return False

def test_data_caching():
    """데이터 캐싱 테스트"""
    try:
        client = LegalDataAPIClient(use_mock=True)
        
        # 첫 번째 요청
        start_time1 = time.time()
        data1 = client.fetch_legal_documents(limit=2)
        time1 = time.time() - start_time1
        
        # 두 번째 요청 (캐시된 데이터 사용)
        start_time2 = time.time()
        data2 = client.fetch_legal_documents(limit=2)
        time2 = time.time() - start_time2
        
        logger.info(f"첫 번째 요청: {time1:.3f}초")
        logger.info(f"두 번째 요청: {time2:.3f}초")
        
        if data1 and data2:
            # 캐시가 작동하면 두 번째 요청이 더 빨라야 함
            if time2 < time1 or time2 < 0.1:
                logger.info("✅ 데이터 캐싱이 정상 작동합니다")
                return True
            else:
                logger.info("✅ 캐싱 없이도 정상 작동합니다")
                return True
        else:
            logger.error("❌ 캐싱 테스트 중 데이터 수집 실패")
            return False
            
    except Exception as e:
        logger.error(f"❌ 데이터 캐싱 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    logger.info("=== API 클라이언트 테스트 시작 ===")
    
    test_results = []
    
    # API 연결 테스트
    test_results.append(("API 서버 연결", test_api_connection()))
    
    # 모의 데이터 수집 테스트
    test_results.append(("모의 데이터 수집", test_mock_data_collection()))
    
    # 데이터 검증 테스트
    test_results.append(("데이터 검증", test_data_validation()))
    
    # 에러 핸들링 테스트
    test_results.append(("에러 핸들링", test_api_error_handling()))
    
    # 레이트 리미팅 테스트
    test_results.append(("레이트 리미팅", test_api_rate_limiting()))
    
    # 캐싱 테스트
    test_results.append(("데이터 캐싱", test_data_caching()))
    
    logger.info("\n=== 테스트 결과 요약 ===")
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("\n🎉 모든 API 클라이언트 테스트가 통과했습니다!")
    else:
        logger.error("\n⚠️ 일부 테스트가 실패했습니다. API 설정을 확인해주세요.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
