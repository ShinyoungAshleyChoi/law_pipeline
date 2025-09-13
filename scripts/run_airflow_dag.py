#!/usr/bin/env python3
"""
Airflow DAG 실행 스크립트 (Docker 연동)
Docker Compose로 실행된 Airflow와 연동하여 DAG 관리
batch_monitor.py를 활용한 실제 배치 작업 실행
"""
import argparse
import sys
import os
import json
import subprocess
import requests
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional
from src.logging_config import get_logger

# batch_monitor 모듈 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from batch_monitor import BatchMonitor

logger = get_logger(__name__)

# Docker Airflow 설정
AIRFLOW_BASE_URL = "http://localhost:8090"
AIRFLOW_USERNAME = "airflow"
AIRFLOW_PASSWORD = "airflow_admin_2024!"

def _check_airflow_connection() -> bool:
    """Airflow 연결 상태 확인"""
    try:
        response = requests.get(f"{AIRFLOW_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            logger.info("Airflow 연결 성공")
            return True
        else:
            logger.error(f"Airflow 연결 실패: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Airflow 연결 실패: {str(e)}")
        return False

def _ensure_dag_exists(dag_id: str) -> bool:
    """DAG 존재 여부 확인 및 생성"""
    try:
        # DAG 목록 조회
        response = requests.get(
            f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}",
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info(f"DAG '{dag_id}' 존재 확인")
            return True
        elif response.status_code == 404:
            logger.warning(f"DAG '{dag_id}'가 존재하지 않습니다. DAG 파일을 생성하겠습니다.")
            return _create_sample_dag(dag_id)
        else:
            logger.error(f"DAG 확인 실패: HTTP {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"DAG 확인 중 오류: {str(e)}")
        return False

def _create_sample_dag(dag_id: str) -> bool:
    """실제 batch_monitor.py를 사용하는 DAG 파일 생성"""
    try:
        # 배치 모니터 스크립트 경로
        batch_monitor_path = os.path.join(os.path.dirname(__file__), "batch_monitor.py")
        
        dag_content = f'''#!/usr/bin/env python3
"""
법제처 데이터 파이프라인 DAG - batch_monitor.py 연동
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
import subprocess
import os

# 배치 모니터 스크립트 경로
BATCH_MONITOR_PATH = "{batch_monitor_path}"
PROJECT_ROOT = "{os.path.dirname(os.path.dirname(__file__))}"

# DAG 기본 설정
default_args = {{
    'owner': 'legal-data-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=2),
}}

# DAG 정의
dag = DAG(
    dag_id='{dag_id}',
    default_args=default_args,
    description='법제처 데이터 파이프라인 - batch_monitor.py 활용',
    schedule_interval='@daily',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['legal', 'data-pipeline', 'batch-monitor'],
)

def check_system_health(**context):
    """시스템 상태 확인 - batch_monitor.py 사용"""
    try:
        cmd = ["uv", "run", "python", BATCH_MONITOR_PATH, "status"]
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ 시스템 상태 확인 완료")
            print(result.stdout)
            return True
        else:
            print("❌ 시스템 상태 확인 실패")
            print(result.stderr)
            raise Exception("시스템 상태 확인 실패")
            
    except subprocess.TimeoutExpired:
        raise Exception("시스템 상태 확인 타임아웃")
    except Exception as e:
        raise Exception(f"시스템 상태 확인 오류: {{str(e)}}")

def run_incremental_update(**context):
    """증분 업데이트 실행 - batch_monitor.py 사용"""
    try:
        # DAG 설정에서 파라미터 가져오기
        dag_run = context.get('dag_run')
        conf = dag_run.conf if dag_run else {{}}
        
        use_api = conf.get('use_api', False)
        target_date = conf.get('target_date')
        
        cmd = ["uv", "run", "python", BATCH_MONITOR_PATH, "run", "incremental_update"]
        
        if use_api:
            cmd.append("--use-api")
        if target_date:
            cmd.extend(["--target-date", target_date])
        
        print(f"증분 업데이트 실행: {{' '.join(cmd)}}")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            print("✅ 증분 업데이트 완료")
            print(result.stdout)
            return True
        else:
            print("❌ 증분 업데이트 실패")
            print(result.stderr)
            raise Exception("증분 업데이트 실패")
            
    except subprocess.TimeoutExpired:
        raise Exception("증분 업데이트 타임아웃 (30분)")
    except Exception as e:
        raise Exception(f"증분 업데이트 오류: {{str(e)}}")

def run_data_validation(**context):
    """데이터 검증 실행 - batch_monitor.py 사용"""
    try:
        # DAG 설정에서 파라미터 가져오기
        dag_run = context.get('dag_run')
        conf = dag_run.conf if dag_run else {{}}
        
        fix_issues = conf.get('fix_issues', False)
        
        cmd = ["uv", "run", "python", BATCH_MONITOR_PATH, "run", "validation"]
        
        if fix_issues:
            cmd.append("--fix")
        
        print(f"데이터 검증 실행: {{' '.join(cmd)}}")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            print("✅ 데이터 검증 완료")
            print(result.stdout)
            return True
        else:
            print("⚠️ 데이터 검증에서 문제 발견")
            print(result.stdout)
            print(result.stderr)
            # 검증 실패는 워크플로우를 중단하지 않음 (경고만)
            return True
            
    except subprocess.TimeoutExpired:
        raise Exception("데이터 검증 타임아웃 (10분)")
    except Exception as e:
        raise Exception(f"데이터 검증 오류: {{str(e)}}")

def send_notification(**context):
    """작업 완료 알림"""
    try:
        task_instance = context.get('task_instance')
        dag_run = context.get('dag_run')
        
        # 이전 태스크들의 상태 확인
        upstream_tasks = task_instance.get_direct_relatives(upstream=True)
        failed_tasks = []
        
        for task in upstream_tasks:
            task_state = task_instance.xcom_pull(task_ids=task.task_id)
            if not task_state:
                failed_tasks.append(task.task_id)
        
        # 알림 메시지 생성
        if failed_tasks:
            message = f"⚠️ 배치 작업 완료 (일부 실패)\\n실패한 태스크: {{', '.join(failed_tasks)}}"
        else:
            message = f"✅ 배치 작업 성공적으로 완료"
        
        message += f"\\n실행 시간: {{context.get('execution_date')}}"
        message += f"\\nDAG Run ID: {{dag_run.dag_run_id if dag_run else 'Unknown'}}"
        
        print(message)
        
        # 실제 환경에서는 Slack, 이메일 등으로 알림 전송
        # from src.notifications.slack_service import send_slack_notification
        # send_slack_notification(message)
        
        return message
        
    except Exception as e:
        print(f"알림 전송 실패: {{str(e)}}")
        return f"알림 전송 실패: {{str(e)}}"

# 태스크 정의
health_check = PythonOperator(
    task_id='health_check',
    python_callable=check_system_health,
    dag=dag,
)

incremental_update = PythonOperator(
    task_id='incremental_update',
    python_callable=run_incremental_update,
    dag=dag,
)

data_validation = PythonOperator(
    task_id='data_validation',
    python_callable=run_data_validation,
    dag=dag,
    trigger_rule='none_failed',  # 이전 태스크가 실패해도 실행
)

notification = PythonOperator(
    task_id='notification',
    python_callable=send_notification,
    dag=dag,
    trigger_rule='all_done',  # 모든 이전 태스크가 완료되면 실행
)

# 태스크 의존성 설정
health_check >> incremental_update >> data_validation >> notification
'''
        
        # DAG 파일 경로
        dag_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'airflow', 'dags')
        os.makedirs(dag_dir, exist_ok=True)
        
        dag_file = os.path.join(dag_dir, f'{dag_id}.py')
        
        with open(dag_file, 'w', encoding='utf-8') as f:
            f.write(dag_content)
        
        logger.info(f"DAG 파일 생성 완료: {dag_file}")
        
        # Airflow에서 DAG 파일을 인식할 시간을 줌
        import time
        time.sleep(10)
        
        return True
        
    except Exception as e:
        logger.error(f"DAG 파일 생성 실패: {str(e)}")
        return False

def trigger_dag(dag_id: str, execution_date: Optional[str] = None, 
                conf: Optional[Dict[str, Any]] = None) -> bool:
    """DAG 실행 트리거"""
    try:
        if not _check_airflow_connection():
            logger.error("Airflow에 연결할 수 없습니다.")
            return False
        
        if not _ensure_dag_exists(dag_id):
            logger.error(f"DAG '{dag_id}'를 확인/생성할 수 없습니다.")
            return False
        
        # DAG 실행
        trigger_data = {
            "dag_run_id": f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "logical_date": execution_date or datetime.now().isoformat(),
            "conf": conf or {}
        }
        
        response = requests.post(
            f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}/dagRuns",
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            json=trigger_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"DAG 실행 트리거 성공: {result.get('dag_run_id')}")
            return True
        else:
            logger.error(f"DAG 실행 트리거 실패: HTTP {response.status_code}, {response.text}")
            return False
        
    except Exception as e:
        logger.error(f"DAG 실행 트리거 실패: {str(e)}")
        return False

def get_dag_status(dag_id: str, execution_date: Optional[str] = None) -> Dict[str, Any]:
    """DAG 실행 상태 조회"""
    try:
        if not _check_airflow_connection():
            return {'status': 'error', 'message': 'Airflow 연결 실패'}
        
        # 최근 DAG 실행 조회
        response = requests.get(
            f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}/dagRuns",
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            params={'limit': 1, 'order_by': '-logical_date'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            dag_runs = data.get('dag_runs', [])
            
            if not dag_runs:
                return {'status': 'not_found', 'message': 'DAG 실행을 찾을 수 없습니다'}
            
            dag_run = dag_runs[0]
            return {
                'dag_id': dag_id,
                'dag_run_id': dag_run.get('dag_run_id'),
                'logical_date': dag_run.get('logical_date'),
                'state': dag_run.get('state'),
                'start_date': dag_run.get('start_date'),
                'end_date': dag_run.get('end_date'),
                'external_trigger': dag_run.get('external_trigger', False)
            }
        else:
            return {'status': 'error', 'message': f'HTTP {response.status_code}'}
        
    except Exception as e:
        logger.error(f"DAG 상태 조회 실패: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def list_recent_runs(dag_id: str, limit: int = 10) -> list[Dict[str, Any]]:
    """최근 DAG 실행 목록 조회"""
    try:
        if not _check_airflow_connection():
            return []
        
        response = requests.get(
            f"{AIRFLOW_BASE_URL}/api/v1/dags/{dag_id}/dagRuns",
            auth=(AIRFLOW_USERNAME, AIRFLOW_PASSWORD),
            params={'limit': limit, 'order_by': '-logical_date'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('dag_runs', [])
        else:
            logger.error(f"DAG 실행 목록 조회 실패: HTTP {response.status_code}")
            return []
        
    except Exception as e:
        logger.error(f"최근 실행 목록 조회 실패: {str(e)}")
        return []

def run_incremental_update(target_date: Optional[str] = None, 
                          force: bool = False, use_api: bool = False) -> bool:
    """증분 업데이트 실행 - batch_monitor.py 직접 사용"""
    logger.info("batch_monitor.py를 통한 증분 업데이트 실행 시작", 
                target_date=target_date, force=force, use_api=use_api)
    
    try:
        # BatchMonitor 인스턴스 생성
        monitor = BatchMonitor()
        
        # 직접 배치 작업 실행
        kwargs = {
            'use_api': use_api,
            'target_date': target_date
        }
        
        success = monitor.run_batch_job('incremental_update', **kwargs)
        
        if success:
            logger.info("batch_monitor.py를 통한 증분 업데이트 성공")
            
            # 추가로 Airflow DAG도 트리거
            conf = {
                'use_api': use_api,
                'target_date': target_date,
                'force_execution': force,
                'triggered_by': 'batch_monitor_integration'
            }
            
            dag_success = trigger_dag('legal_data_pipeline', target_date, conf)
            if dag_success:
                logger.info("Airflow DAG도 성공적으로 트리거됨")
            else:
                logger.warning("Airflow DAG 트리거는 실패했지만 배치 작업 자체는 성공")
            
            return True
        else:
            logger.error("batch_monitor.py를 통한 증분 업데이트 실패")
            return False
            
    except Exception as e:
        logger.error(f"batch_monitor.py 연동 중 오류: {str(e)}")
        return False

def run_health_check() -> Dict[str, Any]:
    """시스템 상태 확인 실행 - batch_monitor.py 활용"""
    logger.info("batch_monitor.py를 통한 시스템 상태 확인 시작")
    
    try:
        # BatchMonitor 인스턴스 생성
        monitor = BatchMonitor()
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'batch_monitor_available': True,
            'airflow_status': {
                'healthy': _check_airflow_connection(),
                'url': AIRFLOW_BASE_URL
            }
        }
        
        # batch_monitor.py의 시스템 상태 확인 기능 활용
        try:
            # 시스템 상태 조회는 출력 기반이므로 subprocess로 실행
            batch_monitor_path = os.path.join(os.path.dirname(__file__), "batch_monitor.py")
            cmd = ["uv", "run", "python", batch_monitor_path, "status"]
            
            process_result = subprocess.run(
                cmd, 
                cwd=os.path.dirname(os.path.dirname(__file__)),
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if process_result.returncode == 0:
                result['batch_system_status'] = {
                    'healthy': True,
                    'details': process_result.stdout
                }
            else:
                result['batch_system_status'] = {
                    'healthy': False,
                    'error': process_result.stderr
                }
                
        except subprocess.TimeoutExpired:
            result['batch_system_status'] = {
                'healthy': False,
                'error': '시스템 상태 확인 타임아웃'
            }
        except Exception as e:
            result['batch_system_status'] = {
                'healthy': False,
                'error': f'시스템 상태 확인 오류: {str(e)}'
            }
        
        # 전체 시스템 상태 판단
        result['overall_healthy'] = (
            result['airflow_status']['healthy'] and
            result['batch_system_status'].get('healthy', False)
        )
        
        logger.info("batch_monitor.py를 통한 시스템 상태 확인 완료", result=result)
        return result
        
    except Exception as e:
        logger.error(f"batch_monitor.py 연동 중 오류: {str(e)}")
        return {
            'timestamp': datetime.now().isoformat(),
            'batch_monitor_available': False,
            'error': str(e),
            'overall_healthy': False
        }

def run_full_load(use_api: bool = False, batch_size: int = 100) -> bool:
    """전체 데이터 적재 실행 - batch_monitor.py 활용"""
    logger.info("batch_monitor.py를 통한 전체 데이터 적재 실행 시작",
                use_api=use_api, batch_size=batch_size)
    
    try:
        # BatchMonitor 인스턴스 생성
        monitor = BatchMonitor()
        
        # 직접 배치 작업 실행
        kwargs = {
            'use_api': use_api,
            'batch_size': batch_size
        }
        
        success = monitor.run_batch_job('full_load', **kwargs)
        
        if success:
            logger.info("batch_monitor.py를 통한 전체 데이터 적재 성공")
            return True
        else:
            logger.error("batch_monitor.py를 통한 전체 데이터 적재 실패")
            return False
            
    except Exception as e:
        logger.error(f"batch_monitor.py 연동 중 오류: {str(e)}")
        return False

def run_data_validation(fix_issues: bool = False) -> bool:
    """데이터 검증 실행 - batch_monitor.py 활용"""
    logger.info("batch_monitor.py를 통한 데이터 검증 실행 시작", fix_issues=fix_issues)
    
    try:
        # BatchMonitor 인스턴스 생성
        monitor = BatchMonitor()
        
        # 직접 배치 작업 실행
        kwargs = {
            'fix_issues': fix_issues
        }
        
        success = monitor.run_batch_job('validation', **kwargs)
        
        if success:
            logger.info("batch_monitor.py를 통한 데이터 검증 성공")
            return True
        else:
            logger.warning("batch_monitor.py를 통한 데이터 검증에서 문제 발견")
            return False
            
    except Exception as e:
        logger.error(f"batch_monitor.py 연동 중 오류: {str(e)}")
        return False

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='법제처 데이터 파이프라인 Airflow DAG 관리 (batch_monitor.py 연동)')
    
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령어')
    
    # 증분 업데이트 실행
    incremental_parser = subparsers.add_parser('incremental', help='증분 업데이트 실행')
    incremental_parser.add_argument('--date', type=str, help='대상 날짜 (YYYY-MM-DD)')
    incremental_parser.add_argument('--force', action='store_true', help='강제 실행')
    incremental_parser.add_argument('--use-api', action='store_true', help='실제 API 사용')
    
    # 전체 데이터 적재 실행
    fullload_parser = subparsers.add_parser('fullload', help='전체 데이터 적재 실행')
    fullload_parser.add_argument('--use-api', action='store_true', help='실제 API 사용')
    fullload_parser.add_argument('--batch-size', type=int, default=100, help='배치 크기')
    
    # 데이터 검증 실행
    validation_parser = subparsers.add_parser('validation', help='데이터 검증 실행')
    validation_parser.add_argument('--fix', action='store_true', help='문제 자동 수정')
    
    # DAG 상태 조회
    status_parser = subparsers.add_parser('status', help='DAG 실행 상태 조회')
    status_parser.add_argument('--dag-id', type=str, default='legal_data_pipeline', help='DAG ID')
    status_parser.add_argument('--date', type=str, help='실행 날짜 (YYYY-MM-DD)')
    
    # 최근 실행 목록
    list_parser = subparsers.add_parser('list', help='최근 실행 목록 조회')
    list_parser.add_argument('--dag-id', type=str, default='legal_data_pipeline', help='DAG ID')
    list_parser.add_argument('--limit', type=int, default=10, help='조회할 실행 개수')
    
    # 시스템 상태 확인
    health_parser = subparsers.add_parser('health', help='시스템 상태 확인')
    
    # DAG 트리거
    trigger_parser = subparsers.add_parser('trigger', help='DAG 수동 실행')
    trigger_parser.add_argument('--dag-id', type=str, default='legal_data_pipeline', help='DAG ID')
    trigger_parser.add_argument('--date', type=str, help='실행 날짜 (YYYY-MM-DD)')
    trigger_parser.add_argument('--conf', type=str, help='설정 JSON')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'incremental':
            success = run_incremental_update(args.date, args.force, args.use_api)
            if success:
                print("✅ 증분 업데이트가 성공적으로 완료되었습니다.")
                print(f"🔗 Airflow UI에서 확인: {AIRFLOW_BASE_URL}")
            else:
                print("❌ 증분 업데이트에 실패했습니다.")
                sys.exit(1)
        
        elif args.command == 'fullload':
            success = run_full_load(args.use_api, args.batch_size)
            if success:
                print("✅ 전체 데이터 적재가 성공적으로 완료되었습니다.")
            else:
                print("❌ 전체 데이터 적재에 실패했습니다.")
                sys.exit(1)
        
        elif args.command == 'validation':
            success = run_data_validation(args.fix)
            if success:
                print("✅ 데이터 검증이 성공적으로 완료되었습니다.")
            else:
                print("⚠️ 데이터 검증에서 문제가 발견되었습니다.")
                sys.exit(1)
        
        elif args.command == 'status':
            status = get_dag_status(args.dag_id, args.date)
            print(json.dumps(status, indent=2, ensure_ascii=False))
        
        elif args.command == 'list':
            runs = list_recent_runs(args.dag_id, args.limit)
            print(json.dumps(runs, indent=2, ensure_ascii=False))
        
        elif args.command == 'health':
            health = run_health_check()
            print(json.dumps(health, indent=2, ensure_ascii=False))
            
            if not health.get('overall_healthy', False):
                sys.exit(1)
        
        elif args.command == 'trigger':
            conf = json.loads(args.conf) if args.conf else None
            success = trigger_dag(args.dag_id, args.date, conf)
            if success:
                print(f"✅ DAG '{args.dag_id}'가 성공적으로 시작되었습니다.")
                print(f"🔗 Airflow UI에서 확인: {AIRFLOW_BASE_URL}")
            else:
                print(f"❌ DAG '{args.dag_id}' 시작에 실패했습니다.")
                sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"스크립트 실행 중 오류: {str(e)}")
        print(f"❌ 오류 발생: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
