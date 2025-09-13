#!/usr/bin/env python3
"""
Mock 환경을 사용한 Airflow DAG 실행 스크립트
src에 구현된 Mock 환경과 DAG를 활용하여 파이프라인을 테스트
"""
import os
import sys
import asyncio
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mock.mock_config import setup_mock_environment, print_mock_environment_status
from logging_config import get_logger

logger = get_logger(__name__)

class MockAirflowDAGRunner:
    """Mock 환경에서 Airflow DAG를 실행하는 러너"""
    
    def __init__(self, environment_type: str = "development"):
        """
        DAG 러너 초기화
        
        Args:
            environment_type: Mock 환경 타입 (development, testing, demo)
        """
        self.environment_type = environment_type
        self.project_root = project_root
        self.airflow_home = project_root / ".airflow"
        self.mock_env = None
        
        # Mock 환경 강제 활성화
        os.environ['ENABLE_MOCK'] = 'true'
        os.environ['MOCK_ENVIRONMENT'] = environment_type
        
    def setup_environment(self):
        """환경 설정 및 초기화"""
        print(f"🔧 {self.environment_type} Mock 환경 설정 중...")
        
        # Mock 환경 설정
        self.mock_env = setup_mock_environment(self.environment_type)
        
        # Airflow 환경 변수 설정
        os.environ['AIRFLOW_HOME'] = str(self.airflow_home)
        os.environ['AIRFLOW__CORE__DAGS_FOLDER'] = str(project_root / "src" / "airflow" / "dags")
        os.environ['AIRFLOW__CORE__EXECUTOR'] = 'LocalExecutor'
        os.environ['AIRFLOW__CORE__SQL_ALCHEMY_CONN'] = 'sqlite:///.airflow/airflow.db'
        os.environ['AIRFLOW__WEBSERVER__SECRET_KEY'] = 'mock-secret-key-for-testing'
        
        # Mock 데이터베이스 연결 정보 설정 (Airflow Connection 대신)
        if hasattr(self.mock_env, 'get_db_connection'):
            db_conn = self.mock_env.get_db_connection()
            if hasattr(db_conn, 'get_connection_string'):
                os.environ['LEGAL_DB_CONNECTION'] = db_conn.get_connection_string()
        
        print("✅ Mock 환경 설정 완료")
        
    def initialize_airflow(self):
        """Airflow 데이터베이스 초기화"""
        print("🚀 Airflow 데이터베이스 초기화 중...")
        
        try:
            # Airflow 홈 디렉토리 생성
            self.airflow_home.mkdir(exist_ok=True)
            
            # Airflow 데이터베이스 초기화
            result = subprocess.run([
                sys.executable, "-m", "airflow", "db", "migrate", "-y",
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode != 0:
                print(f"⚠️ Airflow DB 초기화 경고: {result.stderr}")
                # 이미 초기화된 경우이므로 계속 진행
            
            # Admin 사용자 생성 (이미 존재하는 경우 무시)
            subprocess.run([
                sys.executable, "-m", "airflow", "users", "create",
                "--username", "admin",
                "--firstname", "Admin",
                "--lastname", "User", 
                "--role", "Admin",
                "--email", "admin@legal-pipeline.com",
                "--password", "admin"
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            print("✅ Airflow 초기화 완료")
            
        except Exception as e:
            print(f"❌ Airflow 초기화 실패: {e}")
            raise
    
    def list_available_dags(self) -> list:
        """사용 가능한 DAG 목록 조회"""
        try:
            result = subprocess.run([
                sys.executable, "-m", "airflow", "dags", "list"
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                # DAG ID만 추출
                lines = result.stdout.strip().split('\n')
                dags = []
                for line in lines:
                    if line and not line.startswith('dag_id') and '|' in line:
                        dag_id = line.split('|')[0].strip()
                        if dag_id and dag_id != 'dag_id':
                            dags.append(dag_id)
                return dags
            else:
                print(f"⚠️ DAG 목록 조회 경고: {result.stderr}")
                return []
                
        except Exception as e:
            print(f"❌ DAG 목록 조회 실패: {e}")
            return []
    
    def trigger_dag(self, dag_id: str, conf: Optional[Dict[str, Any]] = None) -> bool:
        """DAG 실행 트리거"""
        print(f"🚀 DAG '{dag_id}' 실행 중...")
        
        try:
            cmd = [
                sys.executable, "-m", "airflow", "dags", "trigger",
                dag_id,
                "--execution-date", datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            if conf:
                import json
                cmd.extend(["--conf", json.dumps(conf)])
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                print(f"✅ DAG '{dag_id}' 트리거 성공")
                print(f"📄 출력: {result.stdout}")
                return True
            else:
                print(f"❌ DAG '{dag_id}' 트리거 실패: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ DAG 트리거 실패: {e}")
            return False
    
    def test_dag(self, dag_id: str, task_id: Optional[str] = None) -> bool:
        """DAG 또는 특정 태스크 테스트"""
        execution_date = datetime.now().strftime("%Y-%m-%d")
        
        if task_id:
            print(f"🧪 태스크 '{task_id}' (DAG: {dag_id}) 테스트 중...")
            cmd = [
                sys.executable, "-m", "airflow", "tasks", "test",
                dag_id, task_id, execution_date
            ]
        else:
            print(f"🧪 DAG '{dag_id}' 전체 테스트 중...")
            # 모든 태스크를 순차적으로 테스트
            tasks = self.get_dag_tasks(dag_id)
            success = True
            for task in tasks:
                task_success = self.test_dag(dag_id, task)
                success = success and task_success
            return success
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                print(f"✅ 테스트 성공")
                print(f"📄 출력: {result.stdout[-500:]}")  # 마지막 500자만 출력
                return True
            else:
                print(f"❌ 테스트 실패: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 테스트 실행 실패: {e}")
            return False
    
    def get_dag_tasks(self, dag_id: str) -> list:
        """DAG의 태스크 목록 조회"""
        try:
            result = subprocess.run([
                sys.executable, "-m", "airflow", "tasks", "list", dag_id
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                tasks = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                return tasks
            else:
                return []
                
        except Exception as e:
            print(f"❌ 태스크 목록 조회 실패: {e}")
            return []
    
    def run_dag_backfill(self, dag_id: str, start_date: str, end_date: str) -> bool:
        """DAG 백필 실행"""
        print(f"⏮️ DAG '{dag_id}' 백필 실행 중 ({start_date} ~ {end_date})...")
        
        try:
            result = subprocess.run([
                sys.executable, "-m", "airflow", "dags", "backfill",
                dag_id,
                "--start-date", start_date,
                "--end-date", end_date
            ], capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                print(f"✅ 백필 성공")
                return True
            else:
                print(f"❌ 백필 실패: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 백필 실행 실패: {e}")
            return False
    
    def show_dag_status(self, dag_id: Optional[str] = None):
        """DAG 상태 조회"""
        if dag_id:
            print(f"📊 DAG '{dag_id}' 상태 조회 중...")
            cmd = [sys.executable, "-m", "airflow", "dags", "state", dag_id, datetime.now().strftime("%Y-%m-%d")]
        else:
            print("📊 모든 DAG 상태 조회 중...")
            cmd = [sys.executable, "-m", "airflow", "dags", "list"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(self.project_root))
            
            if result.returncode == 0:
                print(f"📋 상태 정보:")
                print(result.stdout)
            else:
                print(f"⚠️ 상태 조회 경고: {result.stderr}")
                
        except Exception as e:
            print(f"❌ 상태 조회 실패: {e}")
    
    def cleanup(self):
        """리소스 정리"""
        if self.mock_env:
            self.mock_env.cleanup()

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Mock 환경 Airflow DAG 실행기")
    parser.add_argument(
        "--environment", "-e",
        choices=["development", "testing", "demo"],
        default="development",
        help="Mock 환경 타입"
    )
    parser.add_argument(
        "--action", "-a",
        choices=["list", "trigger", "test", "backfill", "status", "init"],
        default="list",
        help="실행할 액션"
    )
    parser.add_argument(
        "--dag-id", "-d",
        type=str,
        help="대상 DAG ID"
    )
    parser.add_argument(
        "--task-id", "-t",
        type=str,
        help="대상 태스크 ID (test 액션에서만 사용)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="백필 시작 날짜 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="백필 종료 날짜 (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--conf",
        type=str,
        help="DAG 설정 (JSON 형식)"
    )
    
    args = parser.parse_args()
    
    try:
        # DAG 러너 생성
        runner = MockAirflowDAGRunner(args.environment)
        
        # 환경 설정
        runner.setup_environment()
        
        # Mock 환경 상태 출력
        print_mock_environment_status()
        print()
        
        if args.action == "init":
            # Airflow 초기화
            runner.initialize_airflow()
            print("🏁 Airflow 초기화 완료")
            
        elif args.action == "list":
            # DAG 목록 조회
            runner.initialize_airflow()  # 필요시 초기화
            dags = runner.list_available_dags()
            
            print(f"\n📋 사용 가능한 DAG 목록:")
            if dags:
                for i, dag in enumerate(dags, 1):
                    print(f"   {i}. {dag}")
                    
                    # 태스크 목록도 표시
                    tasks = runner.get_dag_tasks(dag)
                    if tasks:
                        print(f"      태스크: {', '.join(tasks[:3])}")
                        if len(tasks) > 3:
                            print(f"      ... 총 {len(tasks)}개 태스크")
                    print()
            else:
                print("   ❌ 사용 가능한 DAG가 없습니다.")
        
        elif args.action == "trigger":
            # DAG 트리거
            if not args.dag_id:
                print("❌ --dag-id 옵션이 필요합니다.")
                sys.exit(1)
            
            runner.initialize_airflow()
            
            conf = None
            if args.conf:
                import json
                try:
                    conf = json.loads(args.conf)
                except json.JSONDecodeError as e:
                    print(f"❌ JSON 설정 파싱 실패: {e}")
                    sys.exit(1)
            
            success = runner.trigger_dag(args.dag_id, conf)
            if success:
                print("✅ DAG 트리거 완료")
            else:
                sys.exit(1)
        
        elif args.action == "test":
            # DAG/태스크 테스트
            if not args.dag_id:
                print("❌ --dag-id 옵션이 필요합니다.")
                sys.exit(1)
            
            runner.initialize_airflow()
            success = runner.test_dag(args.dag_id, args.task_id)
            
            if success:
                print("✅ 테스트 완료")
            else:
                sys.exit(1)
        
        elif args.action == "backfill":
            # 백필 실행
            if not args.dag_id or not args.start_date or not args.end_date:
                print("❌ --dag-id, --start-date, --end-date 옵션이 모두 필요합니다.")
                sys.exit(1)
            
            runner.initialize_airflow()
            success = runner.run_dag_backfill(args.dag_id, args.start_date, args.end_date)
            
            if success:
                print("✅ 백필 완료")
            else:
                sys.exit(1)
        
        elif args.action == "status":
            # 상태 조회
            runner.initialize_airflow()
            runner.show_dag_status(args.dag_id)
        
        # 리소스 정리
        runner.cleanup()
        print("\n🏁 Mock Airflow DAG 실행기 종료")
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
