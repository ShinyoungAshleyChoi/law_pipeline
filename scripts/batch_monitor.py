#!/usr/bin/env python3
"""배치 작업 수동 실행 및 모니터링 도구"""

import sys
import os
import argparse
import time
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import subprocess

from src.database.repository import LegalDataRepository
from src.database.models import BatchJob, JobStatus, JobType
from src.logging_config import get_logger

# 다른 스크립트의 클래스 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from full_data_load import FullDataLoader
from incremental_update import IncrementalUpdater

logger = get_logger(__name__)

@dataclass
class BatchJobSummary:
    """배치 작업 요약 정보"""
    job_id: str
    job_type: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[float]
    processed_laws: int
    processed_articles: int
    error_count: int
    success_rate: float

class BatchMonitor:
    """배치 작업 모니터링 클래스"""
    
    def __init__(self):
        self.repository = LegalDataRepository()
    
    def run_batch_job(self, job_type: str, **kwargs) -> bool:
        """배치 작업 수동 실행"""
        try:
            logger.info(f"{job_type} 배치 작업 수동 실행 시작")
            
            if job_type == "full_load":
                return self._run_full_load(**kwargs)
            elif job_type == "incremental_update":
                return self._run_incremental_update(**kwargs)
            elif job_type == "validation":
                return self._run_validation(**kwargs)
            else:
                logger.error(f"지원하지 않는 작업 유형: {job_type}")
                return False
                
        except Exception as e:
            logger.error(f"배치 작업 실행 실패: {str(e)}")
            return False
    
    def _run_full_load(self, use_api: bool = False, batch_size: int = 100) -> bool:
        """전체 데이터 적재 실행"""
        script_path = os.path.join(os.path.dirname(__file__), "full_data_load.py")
        cmd = ["uv", "run", "python", script_path]
        
        if use_api:
            cmd.append("--use-api")
        cmd.extend(["--batch-size", str(batch_size)])
        
        logger.info(f"전체 데이터 적재 실행: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                logger.info("전체 데이터 적재 성공")
                print(result.stdout)
                return True
            else:
                logger.error("전체 데이터 적재 실패")
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("전체 데이터 적재 타임아웃 (1시간)")
            return False
        except Exception as e:
            logger.error(f"전체 데이터 적재 실행 오류: {str(e)}")
            return False
    
    def _run_incremental_update(self, use_api: bool = False, target_date: Optional[str] = None) -> bool:
        """증분 업데이트 실행"""
        script_path = os.path.join(os.path.dirname(__file__), "incremental_update.py")
        cmd = ["uv", "run", "python", script_path]
        
        if use_api:
            cmd.append("--use-api")
        if target_date:
            cmd.extend(["--target-date", target_date])
        
        logger.info(f"증분 업데이트 실행: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            
            if result.returncode == 0:
                logger.info("증분 업데이트 성공")
                print(result.stdout)
                return True
            else:
                logger.error("증분 업데이트 실패")
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("증분 업데이트 타임아웃 (30분)")
            return False
        except Exception as e:
            logger.error(f"증분 업데이트 실행 오류: {str(e)}")
            return False
    
    def _run_validation(self, fix_issues: bool = False) -> bool:
        """데이터 검증 실행"""
        script_path = os.path.join(os.path.dirname(__file__), "data_validation.py")
        cmd = ["uv", "run", "python", script_path]
        
        if fix_issues:
            cmd.append("--fix")
        
        logger.info(f"데이터 검증 실행: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                logger.info("데이터 검증 성공")
                print(result.stdout)
                return True
            else:
                logger.warning("데이터 검증에서 문제 발견")
                print(result.stdout)
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("데이터 검증 타임아웃 (10분)")
            return False
        except Exception as e:
            logger.error(f"데이터 검증 실행 오류: {str(e)}")
            return False
    
    def monitor_running_jobs(self, refresh_interval: int = 5) -> None:
        """실행 중인 작업 모니터링"""
        print("실행 중인 배치 작업 모니터링을 시작합니다...")
        print("Ctrl+C를 눌러 종료하세요.\n")
        
        try:
            while True:
                running_jobs = self._get_running_jobs()
                
                if running_jobs:
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 실행 중인 작업:")
                    print("-" * 80)
                    
                    for job in running_jobs:
                        duration = self._calculate_duration(job.start_time, datetime.now())
                        print(f"작업 ID: {job.job_id}")
                        print(f"작업 유형: {job.job_type.value}")
                        print(f"시작 시간: {job.start_time}")
                        print(f"실행 시간: {duration}")
                        print(f"처리된 법령: {job.processed_laws}")
                        print(f"처리된 조항: {job.processed_articles}")
                        print(f"오류 수: {job.error_count}")
                        print("-" * 80)
                else:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 실행 중인 작업이 없습니다.")
                
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print("\n모니터링을 종료합니다.")
    
    def show_job_history(self, days: int = 7, limit: int = 20) -> None:
        """배치 작업 이력 조회"""
        try:
            recent_jobs = self.repository.get_recent_batch_jobs(limit)
            
            if not recent_jobs:
                print("배치 작업 이력이 없습니다.")
                return
            
            print(f"\n최근 {days}일간 배치 작업 이력 (최대 {limit}개):")
            print("=" * 120)
            print(f"{'작업 ID':<25} {'유형':<15} {'상태':<10} {'시작 시간':<20} {'소요 시간':<10} {'법령':<8} {'조항':<8} {'오류':<6}")
            print("=" * 120)
            
            for job in recent_jobs:
                duration = self._calculate_duration(job.start_time, job.end_time) if job.end_time else "실행중"
                
                print(f"{job.job_id:<25} {job.job_type.value:<15} {job.status.value:<10} "
                      f"{job.start_time.strftime('%Y-%m-%d %H:%M:%S'):<20} {duration:<10} "
                      f"{job.processed_laws:<8} {job.processed_articles:<8} {job.error_count:<6}")
            
            print("=" * 120)
            
            # 통계 요약
            self._print_job_statistics(recent_jobs)
            
        except Exception as e:
            logger.error(f"작업 이력 조회 실패: {str(e)}")
    
    def show_failed_jobs(self, days: int = 7) -> None:
        """실패한 작업 조회"""
        try:
            failed_jobs = self.repository.get_failed_batch_jobs(days)
            
            if not failed_jobs:
                print(f"최근 {days}일간 실패한 작업이 없습니다.")
                return
            
            print(f"\n최근 {days}일간 실패한 배치 작업:")
            print("=" * 100)
            
            for job in failed_jobs:
                print(f"작업 ID: {job.job_id}")
                print(f"작업 유형: {job.job_type.value}")
                print(f"실패 시간: {job.end_time or job.start_time}")
                print(f"오류 상세: {job.error_details or '상세 정보 없음'}")
                print("-" * 100)
            
        except Exception as e:
            logger.error(f"실패한 작업 조회 실패: {str(e)}")
    
    def show_system_status(self) -> None:
        """시스템 상태 조회"""
        try:
            print("\n시스템 상태 정보:")
            print("=" * 60)
            
            # 데이터베이스 통계
            stats = self.repository.get_database_stats()
            print(f"총 법령 수: {stats.total_laws:,}")
            print(f"총 조항 수: {stats.total_articles:,}")
            print(f"평균 조항/법령: {stats.average_articles_per_law:.1f}")
            print(f"마지막 동기화: {stats.last_sync_date or '없음'}")
            
            # 최근 작업 상태
            recent_jobs = self.repository.get_recent_batch_jobs(5)
            if recent_jobs:
                print(f"\n최근 작업 상태:")
                success_count = sum(1 for job in recent_jobs if job.status == JobStatus.SUCCESS)
                print(f"최근 5개 작업 중 성공: {success_count}/5")
                
                last_job = recent_jobs[0]
                print(f"마지막 작업: {last_job.job_type.value} ({last_job.status.value})")
                print(f"마지막 작업 시간: {last_job.start_time}")
            
            # 동기화 상태
            last_sync = self.repository.get_last_sync_date("INCREMENTAL")
            if last_sync:
                days_since_sync = (date.today() - last_sync).days
                sync_status = "정상" if days_since_sync <= 1 else f"지연됨 ({days_since_sync}일)"
                print(f"동기화 상태: {sync_status}")
            else:
                print("동기화 상태: 미설정")
            
            print("=" * 60)
            
        except Exception as e:
            logger.error(f"시스템 상태 조회 실패: {str(e)}")
    
    def _get_running_jobs(self) -> List[BatchJob]:
        """실행 중인 작업 목록 조회"""
        try:
            recent_jobs = self.repository.get_recent_batch_jobs(50)
            return [job for job in recent_jobs if job.status == JobStatus.RUNNING]
        except Exception as e:
            logger.error(f"실행 중인 작업 조회 실패: {str(e)}")
            return []
    
    def _calculate_duration(self, start_time: datetime, end_time: Optional[datetime]) -> str:
        """작업 소요 시간 계산"""
        if not end_time:
            return "실행중"
        
        duration = end_time - start_time
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}초"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}분 {seconds}초"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}시간 {minutes}분"
    
    def _print_job_statistics(self, jobs: List[BatchJob]) -> None:
        """작업 통계 출력"""
        if not jobs:
            return
        
        total_jobs = len(jobs)
        success_jobs = sum(1 for job in jobs if job.status == JobStatus.SUCCESS)
        failed_jobs = sum(1 for job in jobs if job.status == JobStatus.FAILED)
        running_jobs = sum(1 for job in jobs if job.status == JobStatus.RUNNING)
        
        success_rate = (success_jobs / total_jobs) * 100 if total_jobs > 0 else 0
        
        print(f"\n통계 요약:")
        print(f"전체 작업: {total_jobs}개")
        print(f"성공: {success_jobs}개 ({success_rate:.1f}%)")
        print(f"실패: {failed_jobs}개")
        print(f"실행중: {running_jobs}개")
        
        # 작업 유형별 통계
        job_types = {}
        for job in jobs:
            job_type = job.job_type.value
            if job_type not in job_types:
                job_types[job_type] = {'total': 0, 'success': 0}
            job_types[job_type]['total'] += 1
            if job.status == JobStatus.SUCCESS:
                job_types[job_type]['success'] += 1
        
        print(f"\n작업 유형별 통계:")
        for job_type, stats in job_types.items():
            success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
            print(f"  {job_type}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='배치 작업 수동 실행 및 모니터링 도구')
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령어')
    
    # run 명령어
    run_parser = subparsers.add_parser('run', help='배치 작업 실행')
    run_parser.add_argument('job_type', choices=['full_load', 'incremental_update', 'validation'],
                           help='실행할 작업 유형')
    run_parser.add_argument('--use-api', action='store_true',
                           help='실제 API 사용 (기본값: Mock 데이터)')
    run_parser.add_argument('--batch-size', type=int, default=100,
                           help='배치 크기 (full_load용)')
    run_parser.add_argument('--target-date', type=str,
                           help='대상 날짜 YYYY-MM-DD (incremental_update용)')
    run_parser.add_argument('--fix', action='store_true',
                           help='문제 자동 수정 (validation용)')
    
    # monitor 명령어
    monitor_parser = subparsers.add_parser('monitor', help='실행 중인 작업 모니터링')
    monitor_parser.add_argument('--interval', type=int, default=5,
                               help='새로고침 간격 (초)')
    
    # history 명령어
    history_parser = subparsers.add_parser('history', help='작업 이력 조회')
    history_parser.add_argument('--days', type=int, default=7,
                               help='조회할 일수')
    history_parser.add_argument('--limit', type=int, default=20,
                               help='최대 조회 개수')
    
    # failed 명령어
    failed_parser = subparsers.add_parser('failed', help='실패한 작업 조회')
    failed_parser.add_argument('--days', type=int, default=7,
                              help='조회할 일수')
    
    # status 명령어
    subparsers.add_parser('status', help='시스템 상태 조회')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    monitor = BatchMonitor()
    
    try:
        if args.command == 'run':
            kwargs = {}
            if args.job_type == 'full_load':
                kwargs = {'use_api': args.use_api, 'batch_size': args.batch_size}
            elif args.job_type == 'incremental_update':
                kwargs = {'use_api': args.use_api, 'target_date': args.target_date}
            elif args.job_type == 'validation':
                kwargs = {'fix_issues': args.fix}
            
            success = monitor.run_batch_job(args.job_type, **kwargs)
            sys.exit(0 if success else 1)
            
        elif args.command == 'monitor':
            monitor.monitor_running_jobs(args.interval)
            
        elif args.command == 'history':
            monitor.show_job_history(args.days, args.limit)
            
        elif args.command == 'failed':
            monitor.show_failed_jobs(args.days)
            
        elif args.command == 'status':
            monitor.show_system_status()
            
    except KeyboardInterrupt:
        print("\n작업이 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"명령 실행 실패: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()