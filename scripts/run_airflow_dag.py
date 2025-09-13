#!/usr/bin/env python3
"""
Airflow DAG 실행 스크립트
법제처 데이터 파이프라인 DAG를 수동으로 실행하거나 모니터링하는 스크립트
"""
import argparse
import sys
import os
import json
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional
from src.logging_config import get_logger

logger = get_logger(__name__)

def trigger_dag(dag_id: str, execution_date: Optional[str] = None, 
                conf: Optional[Dict[str, Any]] = None) -> bool:
    """
    DAG 실행 트리거
    
    Args:
        dag_id: 실행할 DAG ID
        execution_date: 실행 날짜 (YYYY-MM-DD 형식)
        conf: DAG 실행 시 전달할 설정
    
    Returns:
        bool: 실행 성공 여부
    """
    try:
        from airflow.api.client.local_client import Client
        
        client = Client(None, None)
        
        # 실행 날짜 설정
        if execution_date:
            exec_date = datetime.strptime(execution_date, '%Y-%m-%d')
        else:
            exec_date = datetime.now()
        
        # DAG 실행
        result = client.trigger_dag(
            dag_id=dag_id,
            execution_date=exec_date,
            conf=conf or {}
        )
        
        logger.info("DAG 실행 트리거 성공",
                   dag_id=dag_id,
                   execution_date=exec_date,
                   result=result)
        
        return True
        
    except Exception as e:
        logger.error("DAG 실행 트리거 실패",
                    dag_id=dag_id,
                    error=str(e))
        return False

def get_dag_status(dag_id: str, execution_date: Optional[str] = None) -> Dict[str, Any]:
    """
    DAG 실행 상태 조회
    
    Args:
        dag_id: 조회할 DAG ID
        execution_date: 실행 날짜 (YYYY-MM-DD 형식)
    
    Returns:
        Dict[str, Any]: DAG 실행 상태 정보
    """
    try:
        from airflow.models import DagRun, TaskInstance
        from airflow.utils.session import provide_session
        
        @provide_session
        def _get_status(session=None):
            # 최근 DAG 실행 조회
            if execution_date:
                exec_date = datetime.strptime(execution_date, '%Y-%m-%d')
                dag_run = session.query(DagRun).filter(
                    DagRun.dag_id == dag_id,
                    DagRun.execution_date == exec_date
                ).first()
            else:
                dag_run = session.query(DagRun).filter(
                    DagRun.dag_id == dag_id
                ).order_by(DagRun.execution_date.desc()).first()
            
            if not dag_run:
                return {'status': 'not_found', 'message': 'DAG 실행을 찾을 수 없습니다'}
            
            # 태스크 상태 조회
            task_instances = session.query(TaskInstance).filter(
                TaskInstance.dag_id == dag_id,
                TaskInstance.execution_date == dag_run.execution_date
            ).all()
            
            task_status = {}
            for ti in task_instances:
                task_status[ti.task_id] = {
                    'state': ti.state,
                    'start_date': ti.start_date.isoformat() if ti.start_date else None,
                    'end_date': ti.end_date.isoformat() if ti.end_date else None,
                    'duration': ti.duration if ti.duration else None
                }
            
            return {
                'dag_id': dag_id,
                'execution_date': dag_run.execution_date.isoformat(),
                'state': dag_run.state,
                'start_date': dag_run.start_date.isoformat() if dag_run.start_date else None,
                'end_date': dag_run.end_date.isoformat() if dag_run.end_date else None,
                'task_count': len(task_instances),
                'tasks': task_status
            }
        
        return _get_status()
        
    except Exception as e:
        logger.error("DAG 상태 조회 실패",
                    dag_id=dag_id,
                    error=str(e))
        return {'status': 'error', 'message': str(e)}

def list_recent_runs(dag_id: str, limit: int = 10) -> list[Dict[str, Any]]:
    """
    최근 DAG 실행 목록 조회
    
    Args:
        dag_id: 조회할 DAG ID
        limit: 조회할 실행 개수
    
    Returns:
        List[Dict[str, Any]]: 최근 실행 목록
    """
    try:
        from airflow.models import DagRun
        from airflow.utils.session import provide_session
        
        @provide_session
        def _get_recent_runs(session=None):
            dag_runs = session.query(DagRun).filter(
                DagRun.dag_id == dag_id
            ).order_by(DagRun.execution_date.desc()).limit(limit).all()
            
            runs = []
            for dag_run in dag_runs:
                runs.append({
                    'execution_date': dag_run.execution_date.isoformat(),
                    'state': dag_run.state,
                    'start_date': dag_run.start_date.isoformat() if dag_run.start_date else None,
                    'end_date': dag_run.end_date.isoformat() if dag_run.end_date else None,
                    'external_trigger': dag_run.external_trigger
                })
            
            return runs
        
        return _get_recent_runs()
        
    except Exception as e:
        logger.error("최근 실행 목록 조회 실패",
                    dag_id=dag_id,
                    error=str(e))
        return []

def run_incremental_update(target_date: Optional[str] = None, 
                          force: bool = False) -> bool:
    """
    증분 업데이트 실행
    
    Args:
        target_date: 대상 날짜 (YYYY-MM-DD 형식)
        force: 강제 실행 여부
    
    Returns:
        bool: 실행 성공 여부
    """
    logger.info("증분 업데이트 실행 시작",
               target_date=target_date,
               force=force)
    
    conf = {
        'force_full_sync': False,
        'target_date': target_date,
        'skip_validation': False,
        'notification_enabled': True
    }
    
    if force:
        conf['force_execution'] = True
    
    return trigger_dag('legal_data_pipeline', target_date, conf)

def run_health_check() -> Dict[str, Any]:
    """
    시스템 상태 확인 실행
    
    Returns:
        Dict[str, Any]: 상태 확인 결과
    """
    logger.info("시스템 상태 확인 시작")
    
    try:
        from src.api.client import api_client
        from src.database.repository import LegalDataRepository
        
        # API 상태 확인
        api_status = api_client.health_check()
        
        # 데이터베이스 상태 확인
        repository = LegalDataRepository()
        db_healthy = True
        db_error = None
        
        try:
            with repository.transaction():
                pass  # 간단한 연결 테스트
        except Exception as e:
            db_healthy = False
            db_error = str(e)
        
        # 마지막 업데이트 확인
        # 마지막 동기화 날짜 조회 (repository에서 직접)
        from src.database.repository import LegalDataRepository
        repository = LegalDataRepository()
        last_sync_date = repository.get_last_sync_date("INCREMENTAL") or date.today() - timedelta(days=7)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'api_status': {
                'healthy': api_status.is_healthy,
                'response_time_ms': api_status.response_time_ms,
                'error': api_status.error_message
            },
            'database_status': {
                'healthy': db_healthy,
                'error': db_error
            },
            'last_sync_date': last_sync_date.isoformat(),
            'data_age_hours': (datetime.now().date() - last_sync_date).days * 24,
            'overall_healthy': api_status.is_healthy and db_healthy
        }
        
        logger.info("시스템 상태 확인 완료", result=result)
        return result
        
    except Exception as e:
        logger.error("시스템 상태 확인 실패", error=str(e))
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'overall_healthy': False
        }

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='법제처 데이터 파이프라인 Airflow DAG 관리')
    
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령어')
    
    # 증분 업데이트 실행
    incremental_parser = subparsers.add_parser('incremental', help='증분 업데이트 실행')
    incremental_parser.add_argument('--date', type=str, help='대상 날짜 (YYYY-MM-DD)')
    incremental_parser.add_argument('--force', action='store_true', help='강제 실행')
    
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
            success = run_incremental_update(args.date, args.force)
            if success:
                print("✅ 증분 업데이트가 성공적으로 시작되었습니다.")
            else:
                print("❌ 증분 업데이트 시작에 실패했습니다.")
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
            else:
                print(f"❌ DAG '{args.dag_id}' 시작에 실패했습니다.")
                sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error("스크립트 실행 중 오류", error=str(e))
        print(f"❌ 오류 발생: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()