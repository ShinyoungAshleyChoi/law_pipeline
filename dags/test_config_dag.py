"""
Airflow 환경에서 config 로드 테스트 DAG
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import sys
import os

# 프로젝트 src 경로를 Python path에 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_config_load():
    """설정 로드 테스트"""
    from config import config
    
    # 환경 정보 출력
    env_info = config.get_environment_info()
    print("=== 환경 정보 ===")
    for key, value in env_info.items():
        print(f"{key}: {value}")
    
    print(f"\n=== 설정 디렉토리 ===")
    print(f"설정 디렉토리 경로: {config.get_config_path()}")
    
    try:
        # 데이터베이스 설정 로드 테스트
        print(f"\n=== 데이터베이스 설정 테스트 ===")
        db_config = config.database
        print(f"데이터베이스 호스트: {db_config.host}")
        print(f"데이터베이스 포트: {db_config.port}")
        print("데이터베이스 설정 로드 성공!")
        
    except Exception as e:
        print(f"데이터베이스 설정 로드 실패: {e}")
    
    try:
        # API 설정 로드 테스트
        print(f"\n=== API 설정 테스트 ===")
        api_config = config.api
        print(f"API Base URL: {api_config.base_url}")
        print(f"API Timeout: {api_config.timeout}")
        print("API 설정 로드 성공!")
        
    except Exception as e:
        print(f"API 설정 로드 실패: {e}")

# DAG 기본 설정
default_args = {
    'owner': 'data-engineer',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# DAG 정의
dag = DAG(
    'test_config_load',
    default_args=default_args,
    description='Airflow 환경에서 config 로드 테스트',
    schedule_interval=None,  # 수동 실행
    catchup=False,
    tags=['test', 'config'],
)

# Task 정의
test_config_task = PythonOperator(
    task_id='test_config_load',
    python_callable=test_config_load,
    dag=dag,
)

test_config_task
