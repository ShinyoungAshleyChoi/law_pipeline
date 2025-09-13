#!/usr/bin/env python3
"""Mock 환경 설정 스크립트"""
import sys
import os
import argparse
from pathlib import Path

from src.mock.mock_config import setup_mock_environment, print_mock_environment_status
from src.mock.data_generator import create_mock_data


def main():
    parser = argparse.ArgumentParser(description="Mock 환경 설정 및 관리")
    parser.add_argument(
        "--environment", "-e",
        choices=["development", "testing", "demo"],
        default="development",
        help="환경 타입 (기본값: development)"
    )
    parser.add_argument(
        "--data-count", "-c",
        type=int,
        default=50,
        help="생성할 Mock 데이터 개수 (기본값: 50)"
    )
    parser.add_argument(
        "--regenerate", "-r",
        action="store_true",
        help="기존 Mock 데이터를 새로 생성"
    )
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="현재 Mock 환경 상태만 출력"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Mock 환경 완전 초기화"
    )
    
    args = parser.parse_args()
    
    try:
        if args.status:
            print_mock_environment_status()
            return
        
        # 강제 재생성 설정
        if args.regenerate:
            os.environ['FORCE_REGENERATE_MOCK_DATA'] = 'true'
        
        # 데이터 개수 설정
        os.environ['MOCK_DATA_COUNT'] = str(args.data_count)
        
        print(f"Mock 환경을 설정합니다... (환경: {args.environment}, 데이터: {args.data_count}개)")
        
        if args.reset:
            print("Mock 환경을 초기화합니다...")
            # sample_data 디렉토리 정리
            sample_data_dir = Path("sample_data")
            if sample_data_dir.exists():
                for file in sample_data_dir.glob("*.json"):
                    file.unlink()
                for file in sample_data_dir.glob("*.db"):
                    file.unlink()
                print("기존 Mock 데이터 파일들이 삭제되었습니다.")
        
        # Mock 환경 설정
        mock_env = setup_mock_environment(args.environment)
        
        if args.regenerate or not Path("sample_data/legal_documents.json").exists():
            print(f"Mock 데이터 {args.data_count}개를 생성합니다...")
            create_mock_data(args.data_count)
        
        # 상태 출력
        print("\n" + "="*50)
        print_mock_environment_status()
        print("="*50)
        
        print(f"\n✅ Mock 환경 설정이 완료되었습니다!")
        print(f"   - 환경 타입: {args.environment}")
        print(f"   - Mock 데이터 개수: {args.data_count}")
        print(f"   - Mock API: 활성화")
        print(f"   - Mock DB: 활성화")
        
        # 사용 예시
        print(f"\n📖 사용 예시:")
        print(f"   python -c \"from mock.mock_config import get_mock_environment; env=get_mock_environment(); print(env.get_environment_info())\"")
        
    except Exception as e:
        print(f"❌ Mock 환경 설정 중 오류 발생: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
