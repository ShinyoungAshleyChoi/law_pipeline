#!/usr/bin/env python3
"""알림 시스템 테스트 스크립트"""

import sys
import os
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_imports():
    """모듈 임포트 테스트"""
    try:
        from src.notifications import notification_service
        print("✅ notification_service 임포트 성공")
        
        from src.notifications import notify_error
        print("✅ notify_error 임포트 성공")
        
        from src.notifications import ErrorType, NotificationLevel
        print("✅ ErrorType, NotificationLevel 임포트 성공")
        
        return True
    except Exception as e:
        print(f"❌ 임포트 실패: {e}")
        return False

def test_notification_connection():
    """알림 시스템 연결 테스트"""
    print("🧪 알림 시스템 연결 테스트 중...")
    
    success = notification_service.test_notification_system()
    if success:
        print("✅ 알림 시스템 연결 성공")
    else:
        print("❌ 알림 시스템 연결 실패")
    
    return success

def test_error_notifications():
    """오류 알림 테스트"""
    print("\n🚨 오류 알림 테스트 중...")
    
    # 일반 오류 알림
    try:
        raise ValueError("테스트용 오류입니다")
    except Exception as e:
        success = notify_error(e, job_name="알림_테스트", error_details="테스트 목적으로 발생시킨 오류")
        print(f"일반 오류 알림: {'✅ 성공' if success else '❌ 실패'}")
    
    # API 연결 오류
    success = notify_api_error("법제처_API", "연결 타임아웃 발생", retry_count=3)
    print(f"API 연결 오류 알림: {'✅ 성공' if success else '❌ 실패'}")
    
    # 데이터베이스 오류
    success = notify_database_error("INSERT", "중복 키 오류", table_name="laws")
    print(f"데이터베이스 오류 알림: {'✅ 성공' if success else '❌ 실패'}")
    
    # 데이터 검증 오류
    success = notify_validation_error("법령데이터", "필수 필드 누락", affected_records=5)
    print(f"데이터 검증 오류 알림: {'✅ 성공' if success else '❌ 실패'}")
    
    # 시스템 오류 (긴급)
    success = notify_system_error("메모리_관리자", "메모리 부족 상황 발생")
    print(f"시스템 오류 알림: {'✅ 성공' if success else '❌ 실패'}")

def test_batch_notifications():
    """배치 작업 알림 테스트"""
    print("\n📊 배치 작업 알림 테스트 중...")
    
    # 배치 성공 알림
    success = notify_batch_success(
        job_name="법령_데이터_동기화",
        processed_laws=150,
        processed_articles=1250,
        duration="00:05:30"
    )
    print(f"배치 성공 알림: {'✅ 성공' if success else '❌ 실패'}")
    
    # 배치 실패 알림
    success = notify_batch_failure(
        job_name="법령_데이터_동기화",
        error_message="API 응답 오류로 인한 작업 중단",
        error_details="법제처 API 서버 점검으로 인한 일시적 장애"
    )
    print(f"배치 실패 알림: {'✅ 성공' if success else '❌ 실패'}")

def test_critical_notifications():
    """긴급 알림 테스트"""
    print("\n🔥 긴급 알림 테스트 중...")
    
    success = notify_critical(
        "연속 3회 배치 작업 실패 발생",
        job_name="법령_데이터_동기화",
        failure_count=3,
        last_success=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    print(f"긴급 알림: {'✅ 성공' if success else '❌ 실패'}")

def main():
    """메인 테스트 함수"""
    print("🚀 법제처 데이터 파이프라인 알림 시스템 테스트 시작")
    print("=" * 60)
    
    # 임포트 테스트
    if not test_imports():
        print("\n❌ 모듈 임포트에 실패했습니다.")
        return False
    
    print("\n✅ 알림 시스템 모듈 구조 검증 완료")
    print("실제 알림 발송 테스트는 슬랙 설정 후 수행 가능합니다.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)