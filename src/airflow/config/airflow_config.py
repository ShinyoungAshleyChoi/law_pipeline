"""
Airflow 설정 관리
"""
from datetime import timedelta
from typing import Dict, Any
import os

# Airflow 기본 설정
AIRFLOW_CONFIG = {
    # 기본 DAG 설정
    'default_args': {
        'owner': 'legal-data-team',
        'depends_on_past': False,
        'email_on_failure': True,
        'email_on_retry': False,
        'retries': 3,
        'retry_delay': timedelta(minutes=5),
        'retry_exponential_backoff': True,
        'max_retry_delay': timedelta(minutes=30),
        'execution_timeout': timedelta(hours=2),
        'sla': timedelta(hours=3),
    },
    
    # 스케줄 설정
    'schedules': {
        'incremental_update': '0 2 * * *',  # 매일 새벽 2시
        'health_check': '*/30 * * * *',     # 30분마다
        'cleanup': '0 3 * * *',             # 매일 새벽 3시
    },
    
    # 성능 설정
    'performance': {
        'max_active_runs': 1,
        'max_active_tasks': 5,
        'catchup': False,
        'dagbag_import_timeout': 30,
    },
    
    # 알림 설정
    'notifications': {
        'email_enabled': True,
        'slack_enabled': True,
        'on_success': True,
        'on_failure': True,
        'on_retry': False,
    },
    
    # 로깅 설정
    'logging': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'enable_remote_logging': False,
    }
}

def get_dag_config(dag_id: str) -> Dict[str, Any]:
    """DAG별 설정 조회"""
    base_config = AIRFLOW_CONFIG.copy()
    
    # DAG별 특별 설정
    dag_specific_configs = {
        'legal_data_pipeline': {
            'description': '법제처 API 데이터 파이프라인 - 증분 업데이트',
            'schedule_interval': AIRFLOW_CONFIG['schedules']['incremental_update'],
            'tags': ['legal', 'data-pipeline', 'incremental'],
            'max_active_runs': 1,
            'catchup': False,
        },
        'legal_data_health_check': {
            'description': '법제처 API 및 시스템 상태 모니터링',
            'schedule_interval': AIRFLOW_CONFIG['schedules']['health_check'],
            'tags': ['legal', 'monitoring', 'health-check'],
            'max_active_runs': 3,
            'catchup': False,
        },
        'legal_data_cleanup': {
            'description': '임시 파일 및 로그 정리',
            'schedule_interval': AIRFLOW_CONFIG['schedules']['cleanup'],
            'tags': ['legal', 'maintenance', 'cleanup'],
            'max_active_runs': 1,
            'catchup': False,
        }
    }
    
    if dag_id in dag_specific_configs:
        base_config.update(dag_specific_configs[dag_id])
    
    return base_config

def get_connection_config() -> Dict[str, str]:
    """연결 설정 조회"""
    return {
        'mysql_conn_id': 'legal_mysql_default',
        'slack_conn_id': 'legal_slack_default',
        'email_conn_id': 'legal_email_default',
    }

def get_variable_config() -> Dict[str, Any]:
    """Airflow Variable 기본값"""
    return {
        'legal_pipeline_config': {
            'max_retry_count': 3,
            'retry_delay_minutes': 5,
            'execution_timeout_hours': 2,
            'sla_hours': 3,
            'notification_enabled': True,
            'data_validation_enabled': True,
            'batch_size': 50,
            'api_timeout_seconds': 30,
            'max_concurrent_tasks': 5
        },
        'legal_pipeline_schedule': {
            'incremental_cron': '0 2 * * *',
            'health_check_cron': '*/30 * * * *',
            'cleanup_cron': '0 3 * * *'
        },
        'legal_pipeline_notifications': {
            'slack_channel': '#legal-data-alerts',
            'email_recipients': ['admin@company.com'],
            'critical_alert_enabled': True,
            'success_notification_enabled': True
        }
    }

# 환경별 설정
ENVIRONMENT_CONFIGS = {
    'development': {
        'schedule_interval': None,  # 수동 실행만
        'email_on_failure': False,
        'slack_enabled': False,
        'retries': 1,
    },
    'staging': {
        'schedule_interval': '0 4 * * *',  # 새벽 4시
        'email_on_failure': True,
        'slack_enabled': True,
        'retries': 2,
    },
    'production': {
        'schedule_interval': '0 2 * * *',  # 새벽 2시
        'email_on_failure': True,
        'slack_enabled': True,
        'retries': 3,
    }
}

def get_environment_config() -> Dict[str, Any]:
    """환경별 설정 조회"""
    env = os.getenv('AIRFLOW_ENV', 'development').lower()
    return ENVIRONMENT_CONFIGS.get(env, ENVIRONMENT_CONFIGS['development'])