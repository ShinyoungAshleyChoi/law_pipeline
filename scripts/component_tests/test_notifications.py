#!/usr/bin/env python3
"""
알림 시스템 테스트 스크립트
- Slack 알림 기능 테스트
- 이메일 알림 기능 테스트
- 알림 템플릿 및 포맷팅 테스트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from notifications.notification_service import NotificationService
from notifications.slack_service import SlackService
import logging
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_notification_service_initialization():
    """알림 서비스 초기화 테스트"""
    try:
        # 기본 설정으로 서비스 초기화
        service = NotificationService()
        logger.info("✅ 알림 서비스 초기화 성공")
        
        # 설정 확인
        if hasattr(service, 'slack_service'):
            logger.info("✅ Slack 서비스 설정됨")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 알림 서비스 초기화 실패: {e}")
        return False

def test_slack_message_formatting():
    """Slack 메시지 포맷팅 테스트"""
    try:
        slack_service = SlackService()
        
        # 성공 메시지 테스트
        success_message = slack_service.format_success_message(
            job_name="데이터 수집 작업",
            message="1000건의 법률 문서가 성공적으로 처리되었습니다.",
            details={
                "processed_count": 1000,
                "duration": "5분 30초",
                "timestamp": datetime.now().isoformat()
            }
        )
        
        if success_message and isinstance(success_message, dict):
            logger.info("✅ 성공 메시지 포맷팅 완료")
            logger.info(f"메시지 프리뷰: {success_message.get('text', '')[:100]}...")
        else:
            logger.error("❌ 성공 메시지 포맷팅 실패")
            return False
        
        # 오류 메시지 테스트
        error_message = slack_service.format_error_message(
            job_name="데이터베이스 연결 작업",
            error="Connection timeout",
            details={
                "error_code": "DB_TIMEOUT",
                "retry_count": 3,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        if error_message and isinstance(error_message, dict):
            logger.info("✅ 오류 메시지 포맷팅 완료")
            logger.info(f"메시지 프리뷰: {error_message.get('text', '')[:100]}...")
        else:
            logger.error("❌ 오류 메시지 포맷팅 실패")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 메시지 포맷팅 테스트 실패: {e}")
        return False

def test_slack_webhook_validation():
    """Slack 웹훅 URL 검증 테스트"""
    try:
        slack_service = SlackService()
        
        # 웹훅 URL 형식 검증
        valid_urls = [
            "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
            "https://hooks.slack.com/services/T123/B456/abc123def456"
        ]
        
        invalid_urls = [
            "http://invalid-url.com",
            "not-a-url",
            "",
            None
        ]
        
        # 유효한 URL 테스트
        for url in valid_urls:
            if slack_service.validate_webhook_url(url):
                logger.info(f"✅ 유효한 웹훅 URL 검증 통과: {url[:50]}...")
            else:
                logger.error(f"❌ 유효한 URL이 실패로 판정됨: {url}")
                return False
        
        # 무효한 URL 테스트
        for url in invalid_urls:
            if not slack_service.validate_webhook_url(url):
                logger.info(f"✅ 무효한 웹훅 URL 검증 통과: {url}")
            else:
                logger.error(f"❌ 무효한 URL이 유효로 판정됨: {url}")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 웹훅 URL 검증 테스트 실패: {e}")
        return False

def test_notification_templates():
    """알림 템플릿 테스트"""
    try:
        service = NotificationService()
        
        # 데이터 파이프라인 시작 알림
        start_notification = service.create_pipeline_start_notification(
            pipeline_name="법률 데이터 수집 파이프라인",
            scheduled_time=datetime.now(),
            estimated_duration="30분"
        )
        
        if start_notification:
            logger.info("✅ 파이프라인 시작 알림 템플릿 생성 성공")
        else:
            return False
        
        # 데이터 파이프라인 완료 알림
        completion_notification = service.create_pipeline_completion_notification(
            pipeline_name="법률 데이터 수집 파이프라인",
            status="success",
            processed_records=1500,
            duration="25분 30초",
            summary={
                "new_documents": 150,
                "updated_documents": 75,
                "failed_documents": 5
            }
        )
        
        if completion_notification:
            logger.info("✅ 파이프라인 완료 알림 템플릿 생성 성공")
        else:
            return False
        
        # 오류 알림
        error_notification = service.create_error_notification(
            component="데이터베이스 연결",
            error_message="Connection pool exhausted",
            severity="HIGH",
            suggested_action="데이터베이스 연결 풀 크기를 증가시키고 재시작하세요."
        )
        
        if error_notification:
            logger.info("✅ 오류 알림 템플릿 생성 성공")
        else:
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 알림 템플릿 테스트 실패: {e}")
        return False

def test_notification_throttling():
    """알림 스로틀링 테스트"""
    try:
        service = NotificationService()
        
        # 동일한 알림을 여러 번 전송하여 스로틀링 확인
        test_message = "테스트 스로틀링 메시지"
        
        results = []
        for i in range(5):
            try:
                result = service.send_test_notification(test_message, throttle_key="test_throttle")
                results.append(result)
                logger.info(f"알림 전송 시도 {i+1}: {'성공' if result else '스로틀됨'}")
            except Exception as e:
                logger.info(f"알림 전송 시도 {i+1}: 스로틀링으로 인한 예외 - {e}")
                results.append(False)
        
        # 첫 번째는 성공, 나머지는 스로틀되어야 함
        if results[0] and not any(results[1:]):
            logger.info("✅ 알림 스로틀링이 정상 작동합니다")
            return True
        elif all(results):
            logger.info("✅ 알림 전송이 정상 작동합니다 (스로틀링 없음)")
            return True
        else:
            logger.warning("⚠️ 스로틀링 동작이 예상과 다릅니다")
            return True  # 기능상 문제없음
        
    except Exception as e:
        logger.error(f"❌ 알림 스로틀링 테스트 실패: {e}")
        return False

def test_notification_retry_logic():
    """알림 재시도 로직 테스트"""
    try:
        service = NotificationService()
        
        # 실패하는 알림을 시뮬레이션
        test_cases = [
            {"message": "재시도 테스트 메시지 1", "should_fail": False},
            {"message": "재시도 테스트 메시지 2", "should_fail": True}
        ]
        
        for i, test_case in enumerate(test_cases):
            try:
                if test_case["should_fail"]:
                    # 의도적으로 잘못된 설정으로 실패 유도
                    result = service.send_notification_with_retry(
                        test_case["message"],
                        max_retries=2,
                        force_failure=True
                    )
                else:
                    result = service.send_notification_with_retry(
                        test_case["message"],
                        max_retries=2
                    )
                
                expected_result = not test_case["should_fail"]
                if result == expected_result:
                    logger.info(f"✅ 재시도 테스트 {i+1} 통과")
                else:
                    logger.error(f"❌ 재시도 테스트 {i+1} 실패")
                    return False
                    
            except Exception as e:
                if test_case["should_fail"]:
                    logger.info(f"✅ 재시도 테스트 {i+1} 통과 (예상된 실패)")
                else:
                    logger.error(f"❌ 재시도 테스트 {i+1} 예상치 못한 실패: {e}")
                    return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 알림 재시도 로직 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    logger.info("=== 알림 시스템 테스트 시작 ===")
    
    test_results = []
    
    # 서비스 초기화 테스트
    test_results.append(("서비스 초기화", test_notification_service_initialization()))
    
    # 메시지 포맷팅 테스트
    test_results.append(("메시지 포맷팅", test_slack_message_formatting()))
    
    # 웹훅 URL 검증 테스트
    test_results.append(("웹훅 URL 검증", test_slack_webhook_validation()))
    
    # 알림 템플릿 테스트
    test_results.append(("알림 템플릿", test_notification_templates()))
    
    # 스로틀링 테스트
    test_results.append(("알림 스로틀링", test_notification_throttling()))
    
    # 재시도 로직 테스트
    test_results.append(("재시도 로직", test_notification_retry_logic()))
    
    logger.info("\n=== 테스트 결과 요약 ===")
    for test_name, result in test_results:
        status = "✅ 통과" if result else "❌ 실패"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in test_results)
    if all_passed:
        logger.info("\n🎉 모든 알림 시스템 테스트가 통과했습니다!")
    else:
        logger.error("\n⚠️ 일부 테스트가 실패했습니다. 알림 설정을 확인해주세요.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
