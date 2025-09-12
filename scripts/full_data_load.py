#!/usr/bin/env python3
"""전체 초기 데이터 적재 스크립트"""

import sys
import os
import argparse
from datetime import datetime, date
from typing import List, Dict, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.repository import LegalDataRepository
from src.database.models import JobType, JobStatus, LawList, LawContent, LawArticle
from src.logging_config import get_logger

logger = get_logger(__name__)

class FullDataLoader:
    """전체 초기 데이터 적재 클래스"""
    
    def __init__(self):
        self.repository = LegalDataRepository()
        self.job_id = None
        self.stats = {
            'total_laws': 0,
            'processed_laws': 0,
            'total_articles': 0,
            'processed_articles': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def load_full_data(self, use_mock_data: bool = True, batch_size: int = 100) -> bool:
        """전체 데이터 적재 실행"""
        try:
            # 배치 작업 시작
            self.job_id = self.repository.create_batch_job(JobType.FULL_SYNC)
            self.stats['start_time'] = datetime.now()
            
            logger.info("전체 데이터 적재 시작", job_id=self.job_id, use_mock=use_mock_data)
            
            # 배치 작업 상태를 RUNNING으로 업데이트
            self.repository.update_batch_job_status(
                self.job_id, JobStatus.RUNNING
            )
            
            if use_mock_data:
                success = self._load_mock_data(batch_size)
            else:
                success = self._load_api_data(batch_size)
            
            self.stats['end_time'] = datetime.now()
            
            # 배치 작업 완료 상태 업데이트
            final_status = JobStatus.SUCCESS if success else JobStatus.FAILED
            self.repository.update_batch_job_status(
                self.job_id, 
                final_status,
                processed_laws=self.stats['processed_laws'],
                processed_articles=self.stats['processed_articles'],
                error_count=self.stats['errors']
            )
            
            # 동기화 상태 업데이트
            if success:
                self.repository.update_sync_status(
                    sync_type="FULL",
                    sync_date=date.today(),
                    total_laws_count=self.stats['processed_laws'],
                    total_articles_count=self.stats['processed_articles']
                )
            
            self._print_summary()
            return success
            
        except Exception as e:
            logger.error("전체 데이터 적재 실패", error=str(e), job_id=self.job_id)
            if self.job_id:
                self.repository.update_batch_job_status(
                    self.job_id, JobStatus.FAILED, error_details=str(e)
                )
            return False
    
    def _load_mock_data(self, batch_size: int) -> bool:
        """Mock 데이터를 사용한 전체 적재"""
        logger.info("Mock 데이터를 사용한 전체 적재 시작")
        
        try:
            # Mock 법령 목록 데이터 생성
            mock_law_lists = self._generate_mock_law_lists(100)  # 100개 법령
            self.stats['total_laws'] = len(mock_law_lists)
            
            # 배치 단위로 처리
            for i in range(0, len(mock_law_lists), batch_size):
                batch = mock_law_lists[i:i + batch_size]
                
                with self.repository.transaction():
                    for law_list in batch:
                        try:
                            # 1. 법령 목록 저장
                            self.repository.save_law_list(law_list)
                            
                            # 2. 법령 본문 생성 및 저장
                            law_content = self._generate_mock_law_content(law_list)
                            self.repository.save_law_content(law_content)
                            
                            # 3. 법령 조항 생성 및 저장 (법령당 5-10개 조항)
                            articles = self._generate_mock_law_articles(law_list, 5)
                            for article in articles:
                                self.repository.save_law_article(article)
                                self.stats['processed_articles'] += 1
                            
                            self.stats['processed_laws'] += 1
                            
                            if self.stats['processed_laws'] % 10 == 0:
                                logger.info(f"처리 진행률: {self.stats['processed_laws']}/{self.stats['total_laws']}")
                                
                        except Exception as e:
                            logger.error("법령 처리 실패", law_id=law_list.law_id, error=str(e))
                            self.stats['errors'] += 1
                            continue
            
            logger.info("Mock 데이터 적재 완료", 
                       processed_laws=self.stats['processed_laws'],
                       processed_articles=self.stats['processed_articles'])
            return True
            
        except Exception as e:
            logger.error("Mock 데이터 적재 실패", error=str(e))
            return False
    
    def _load_api_data(self, batch_size: int) -> bool:
        """실제 API 데이터를 사용한 전체 적재"""
        logger.info("실제 API 데이터를 사용한 전체 적재 시작")
        
        # TODO: 실제 API 연동 구현
        # 현재는 Mock 데이터로 대체
        logger.warning("실제 API 연동은 아직 구현되지 않았습니다. Mock 데이터를 사용합니다.")
        return self._load_mock_data(batch_size)
    
    def _generate_mock_law_lists(self, count: int) -> List[LawList]:
        """Mock 법령 목록 데이터 생성"""
        law_lists = []
        
        for i in range(1, count + 1):
            law_list = LawList(
                law_id=i,
                law_serial_no=10000 + i,
                law_name_korean=f"테스트법령{i:03d}",
                law_abbr_name=f"테스트법{i:03d}",
                enforcement_date=20240101 + i,  # YYYYMMDD 형식
                promulgation_date=20231201 + i,
                ministry_name="법무부",
                ministry_code=1001,
                law_type_name="법률",
                revision_type="제정",
                current_history_code="현행",
                created_at=datetime.now()
            )
            law_lists.append(law_list)
        
        return law_lists
    
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
            article_content=f"{law_list.law_name_korean}의 본문 내용입니다.",
            created_at=datetime.now()
        )
    
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
        """적재 결과 요약 출력"""
        duration = None
        if self.stats['start_time'] and self.stats['end_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        print("\n" + "="*60)
        print("전체 데이터 적재 결과 요약")
        print("="*60)
        print(f"작업 ID: {self.job_id}")
        print(f"시작 시간: {self.stats['start_time']}")
        print(f"종료 시간: {self.stats['end_time']}")
        print(f"소요 시간: {duration:.2f}초" if duration else "소요 시간: 계산 불가")
        print(f"처리된 법령 수: {self.stats['processed_laws']}")
        print(f"처리된 조항 수: {self.stats['processed_articles']}")
        print(f"오류 발생 수: {self.stats['errors']}")
        print("="*60)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='전체 초기 데이터 적재 스크립트')
    parser.add_argument('--use-api', action='store_true', 
                       help='실제 API 사용 (기본값: Mock 데이터 사용)')
    parser.add_argument('--batch-size', type=int, default=100,
                       help='배치 처리 크기 (기본값: 100)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='상세 로그 출력')
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 데이터 적재 실행
    loader = FullDataLoader()
    success = loader.load_full_data(
        use_mock_data=not args.use_api,
        batch_size=args.batch_size
    )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()