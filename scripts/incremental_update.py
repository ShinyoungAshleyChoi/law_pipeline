#!/usr/bin/env python3
"""증분 업데이트 실행 스크립트"""

import sys
import os
import argparse
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

from src.database.repository import LegalDataRepository
from src.database.models import JobType, JobStatus, LawList, LawContent, LawArticle
from src.logging_config import get_logger

logger = get_logger(__name__)

class IncrementalUpdater:
    """증분 업데이트 클래스"""
    
    def __init__(self):
        self.repository = LegalDataRepository()
        self.job_id = None
        self.stats = {
            'last_sync_date': None,
            'current_sync_date': None,
            'updated_laws': 0,
            'updated_articles': 0,
            'new_laws': 0,
            'new_articles': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def run_incremental_update(self, use_mock_data: bool = True, 
                             target_date: Optional[date] = None) -> bool:
        """증분 업데이트 실행"""
        try:
            # 배치 작업 시작
            self.stats['last_sync_date'] = self.repository.get_last_sync_date("INCREMENTAL")
            self.stats['current_sync_date'] = target_date or date.today()
            
            self.job_id = self.repository.create_batch_job(
                JobType.INCREMENTAL_SYNC, 
                self.stats['last_sync_date']
            )
            self.stats['start_time'] = datetime.now()
            
            logger.info("증분 업데이트 시작", 
                       job_id=self.job_id,
                       last_sync_date=self.stats['last_sync_date'],
                       current_sync_date=self.stats['current_sync_date'],
                       use_mock=use_mock_data)
            
            # 배치 작업 상태를 RUNNING으로 업데이트
            self.repository.update_batch_job_status(
                self.job_id, JobStatus.RUNNING
            )
            
            if use_mock_data:
                success = self._run_mock_incremental_update()
            else:
                success = self._run_api_incremental_update()
            
            self.stats['end_time'] = datetime.now()
            
            # 배치 작업 완료 상태 업데이트
            final_status = JobStatus.SUCCESS if success else JobStatus.FAILED
            self.repository.update_batch_job_status(
                self.job_id,
                final_status,
                processed_laws=self.stats['updated_laws'] + self.stats['new_laws'],
                processed_articles=self.stats['updated_articles'] + self.stats['new_articles'],
                error_count=self.stats['errors']
            )
            
            # 동기화 상태 업데이트
            if success:
                self.repository.update_sync_status(
                    sync_type="INCREMENTAL",
                    sync_date=self.stats['current_sync_date'],
                    total_laws_count=self.stats['updated_laws'] + self.stats['new_laws'],
                    total_articles_count=self.stats['updated_articles'] + self.stats['new_articles']
                )
            
            self._print_summary()
            return success
            
        except Exception as e:
            logger.error("증분 업데이트 실패", error=str(e), job_id=self.job_id)
            if self.job_id:
                self.repository.update_batch_job_status(
                    self.job_id, JobStatus.FAILED, error_details=str(e)
                )
            return False
    
    def _run_mock_incremental_update(self) -> bool:
        """Mock 데이터를 사용한 증분 업데이트"""
        logger.info("Mock 데이터를 사용한 증분 업데이트 시작")
        
        try:
            # 마지막 동기화 이후 변경된 데이터 시뮬레이션
            if self.stats['last_sync_date'] is None:
                logger.info("첫 번째 증분 업데이트 - 최근 7일간의 데이터 처리")
                self.stats['last_sync_date'] = date.today() - timedelta(days=7)
            
            # 변경된 법령 목록 생성 (시뮬레이션)
            updated_laws = self._generate_updated_mock_laws()
            new_laws = self._generate_new_mock_laws()
            
            # 기존 법령 업데이트 처리
            for law_list in updated_laws:
                try:
                    with self.repository.transaction():
                        # 법령 목록 업데이트
                        self.repository.save_law_list(law_list)
                        
                        # 법령 본문 업데이트
                        law_content = self._generate_mock_law_content(law_list)
                        self.repository.save_law_content(law_content)
                        
                        # 조항 업데이트 (기존 조항 수정 + 새 조항 추가)
                        updated_articles = self._generate_updated_mock_articles(law_list)
                        for article in updated_articles:
                            self.repository.save_law_article(article)
                            self.stats['updated_articles'] += 1
                        
                        self.stats['updated_laws'] += 1
                        
                except Exception as e:
                    logger.error("기존 법령 업데이트 실패", law_id=law_list.law_id, error=str(e))
                    self.stats['errors'] += 1
                    continue
            
            # 새로운 법령 추가 처리
            for law_list in new_laws:
                try:
                    with self.repository.transaction():
                        # 새 법령 목록 저장
                        self.repository.save_law_list(law_list)
                        
                        # 새 법령 본문 저장
                        law_content = self._generate_mock_law_content(law_list)
                        self.repository.save_law_content(law_content)
                        
                        # 새 조항들 저장
                        new_articles = self._generate_mock_law_articles(law_list, 3)
                        for article in new_articles:
                            self.repository.save_law_article(article)
                            self.stats['new_articles'] += 1
                        
                        self.stats['new_laws'] += 1
                        
                except Exception as e:
                    logger.error("새 법령 추가 실패", law_id=law_list.law_id, error=str(e))
                    self.stats['errors'] += 1
                    continue
            
            logger.info("Mock 증분 업데이트 완료",
                       updated_laws=self.stats['updated_laws'],
                       new_laws=self.stats['new_laws'],
                       updated_articles=self.stats['updated_articles'],
                       new_articles=self.stats['new_articles'])
            return True
            
        except Exception as e:
            logger.error("Mock 증분 업데이트 실패", error=str(e))
            return False
    
    def _run_api_incremental_update(self) -> bool:
        """실제 API 데이터를 사용한 증분 업데이트"""
        logger.info("실제 API 데이터를 사용한 증분 업데이트 시작")
        
        # TODO: 실제 API 연동 구현
        # 현재는 Mock 데이터로 대체
        logger.warning("실제 API 연동은 아직 구현되지 않았습니다. Mock 데이터를 사용합니다.")
        return self._run_mock_incremental_update()
    
    def _generate_updated_mock_laws(self) -> List[LawList]:
        """업데이트된 Mock 법령 목록 생성"""
        updated_laws = []
        
        # 기존 법령 중 일부가 개정되었다고 가정 (ID 1-5)
        for i in range(1, 6):
            law_list = LawList(
                law_id=i,
                law_serial_no=10000 + i,
                law_name_korean=f"테스트법령{i:03d} (개정)",
                law_abbr_name=f"테스트법{i:03d}",
                enforcement_date=int(self.stats['current_sync_date'].strftime('%Y%m%d')),
                promulgation_date=int((self.stats['current_sync_date'] - timedelta(days=30)).strftime('%Y%m%d')),
                ministry_name="법무부",
                ministry_code=1001,
                law_type_name="법률",
                revision_type="개정",
                current_history_code="현행",
                created_at=datetime.now()
            )
            updated_laws.append(law_list)
        
        return updated_laws
    
    def _generate_new_mock_laws(self) -> List[LawList]:
        """새로운 Mock 법령 목록 생성"""
        new_laws = []
        
        # 새로운 법령 추가 (ID 201-203)
        for i in range(201, 204):
            law_list = LawList(
                law_id=i,
                law_serial_no=10000 + i,
                law_name_korean=f"신규테스트법령{i:03d}",
                law_abbr_name=f"신규테스트법{i:03d}",
                enforcement_date=int(self.stats['current_sync_date'].strftime('%Y%m%d')),
                promulgation_date=int((self.stats['current_sync_date'] - timedelta(days=15)).strftime('%Y%m%d')),
                ministry_name="법무부",
                ministry_code=1001,
                law_type_name="법률",
                revision_type="제정",
                current_history_code="현행",
                created_at=datetime.now()
            )
            new_laws.append(law_list)
        
        return new_laws
    
    def _generate_mock_law_content(self, law_list: LawList) -> LawContent:
        """Mock 법령 본문 데이터 생성"""
        return LawContent(
            law_id=law_list.law_id,
            law_name_korean=law_list.law_name_korean,
            enforcement_date=law_list.enforcement_date,
            promulgation_date=law_list.promulgation_date,
            ministry_name=law_list.ministry_name,
            ministry_code=law_list.ministry_code,
            law_type="법률",
            law_type_code="L001",
            article_content=f"{law_list.law_name_korean}의 본문 내용입니다. (업데이트됨: {datetime.now()})",
            created_at=datetime.now()
        )
    
    def _generate_updated_mock_articles(self, law_list: LawList) -> List[LawArticle]:
        """업데이트된 Mock 조항 데이터 생성"""
        articles = []
        
        # 기존 조항 수정 + 새 조항 추가
        for i in range(1, 4):  # 3개 조항
            article = LawArticle(
                law_key=law_list.law_id,
                law_id=law_list.law_id,
                law_name_korean=law_list.law_name_korean,
                enforcement_date=law_list.enforcement_date,
                ministry_name=law_list.ministry_name,
                ministry_code=law_list.ministry_code,
                article_no=i,
                article_title=f"제{i}조 (개정)",
                article_content=f"{law_list.law_name_korean} 제{i}조의 개정된 내용입니다. (업데이트: {datetime.now()})",
                paragraph_no=1,
                paragraph_content=f"제{i}조 제1항의 개정된 내용입니다.",
                created_at=datetime.now()
            )
            articles.append(article)
        
        return articles
    
    def _generate_mock_law_articles(self, law_list: LawList, article_count: int) -> List[LawArticle]:
        """Mock 법령 조항 데이터 생성"""
        articles = []
        
        for i in range(1, article_count + 1):
            article = LawArticle(
                law_key=law_list.law_id,
                law_id=law_list.law_id,
                law_name_korean=law_list.law_name_korean,
                enforcement_date=law_list.enforcement_date,
                ministry_name=law_list.ministry_name,
                ministry_code=law_list.ministry_code,
                article_no=i,
                article_title=f"제{i}조",
                article_content=f"{law_list.law_name_korean} 제{i}조의 내용입니다.",
                paragraph_no=1,
                paragraph_content=f"제{i}조 제1항의 내용입니다.",
                created_at=datetime.now()
            )
            articles.append(article)
        
        return articles
    
    def _print_summary(self):
        """증분 업데이트 결과 요약 출력"""
        duration = None
        if self.stats['start_time'] and self.stats['end_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print("\n" + "="*60)
        print("증분 업데이트 결과 요약")
        print("="*60)
        print(f"작업 ID: {self.job_id}")
        print(f"마지막 동기화 날짜: {self.stats['last_sync_date']}")
        print(f"현재 동기화 날짜: {self.stats['current_sync_date']}")
        print(f"시작 시간: {self.stats['start_time']}")
        print(f"종료 시간: {self.stats['end_time']}")
        print(f"소요 시간: {duration:.2f}초" if duration else "소요 시간: 계산 불가")
        print(f"업데이트된 법령 수: {self.stats['updated_laws']}")
        print(f"새로 추가된 법령 수: {self.stats['new_laws']}")
        print(f"업데이트된 조항 수: {self.stats['updated_articles']}")
        print(f"새로 추가된 조항 수: {self.stats['new_articles']}")
        print(f"오류 발생 수: {self.stats['errors']}")
        print("="*60)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='증분 업데이트 실행 스크립트')
    parser.add_argument('--use-api', action='store_true',
                       help='실제 API 사용 (기본값: Mock 데이터 사용)')
    parser.add_argument('--target-date', type=str,
                       help='대상 날짜 (YYYY-MM-DD 형식, 기본값: 오늘)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='상세 로그 출력')
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 대상 날짜 파싱
    target_date = None
    if args.target_date:
        try:
            target_date = datetime.strptime(args.target_date, '%Y-%m-%d').date()
        except ValueError:
            print(f"잘못된 날짜 형식: {args.target_date}. YYYY-MM-DD 형식을 사용하세요.")
            sys.exit(1)
    
    # 증분 업데이트 실행
    updater = IncrementalUpdater()
    success = updater.run_incremental_update(
        use_mock_data=not args.use_api,
        target_date=target_date
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()