#!/usr/bin/env python3
"""데이터 검증 및 일관성 체크 스크립트"""

import sys
import os
import argparse
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from src.database.repository import LegalDataRepository
from src.database.models import JobType, JobStatus
from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ValidationResult:
    """검증 결과 데이터 클래스"""
    check_name: str
    is_valid: bool
    error_count: int
    warning_count: int
    details: List[str]
    execution_time_ms: float

@dataclass
class ValidationSummary:
    """전체 검증 요약 데이터 클래스"""
    total_checks: int
    passed_checks: int
    failed_checks: int
    total_errors: int
    total_warnings: int
    execution_time_seconds: float
    results: List[ValidationResult]

class DataValidator:
    """데이터 검증 및 일관성 체크 클래스"""
    
    def __init__(self):
        self.repository = LegalDataRepository()
        self.job_id = None
    
    def run_full_validation(self, fix_issues: bool = False) -> ValidationSummary:
        """전체 데이터 검증 실행"""
        start_time = datetime.now()
        
        try:
            # 배치 작업 시작
            self.job_id = self.repository.create_batch_job(JobType.VALIDATION)
            self.repository.update_batch_job_status(self.job_id, JobStatus.RUNNING)
            
            logger.info("데이터 검증 시작", job_id=self.job_id, fix_issues=fix_issues)
            
            # 검증 항목들 실행
            validation_results = []
            
            # 1. 기본 데이터 무결성 검증
            validation_results.append(self._check_data_integrity())
            
            # 2. 법령 데이터 일관성 검증
            validation_results.append(self._check_law_consistency())
            
            # 3. 조항 데이터 일관성 검증
            validation_results.append(self._check_article_consistency())
            
            # 4. 관계 무결성 검증
            validation_results.append(self._check_relationship_integrity())
            
            # 5. 중복 데이터 검증
            validation_results.append(self._check_duplicate_data())
            
            # 6. 날짜 데이터 검증
            validation_results.append(self._check_date_consistency())
            
            # 7. 통계 데이터 검증
            validation_results.append(self._check_statistics_consistency())
            
            # 문제 해결 시도 (옵션)
            if fix_issues:
                self._fix_detected_issues(validation_results)
            
            # 요약 생성
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            summary = ValidationSummary(
                total_checks=len(validation_results),
                passed_checks=sum(1 for r in validation_results if r.is_valid),
                failed_checks=sum(1 for r in validation_results if not r.is_valid),
                total_errors=sum(r.error_count for r in validation_results),
                total_warnings=sum(r.warning_count for r in validation_results),
                execution_time_seconds=execution_time,
                results=validation_results
            )
            
            # 배치 작업 완료
            final_status = JobStatus.SUCCESS if summary.failed_checks == 0 else JobStatus.FAILED
            self.repository.update_batch_job_status(
                self.job_id,
                final_status,
                error_count=summary.total_errors
            )
            
            logger.info("데이터 검증 완료",
                       job_id=self.job_id,
                       passed_checks=summary.passed_checks,
                       failed_checks=summary.failed_checks,
                       total_errors=summary.total_errors)
            
            return summary
            
        except Exception as e:
            logger.error("데이터 검증 실패", error=str(e), job_id=self.job_id)
            if self.job_id:
                self.repository.update_batch_job_status(
                    self.job_id, JobStatus.FAILED, error_details=str(e)
                )
            raise
    
    def _check_data_integrity(self) -> ValidationResult:
        """기본 데이터 무결성 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            with self.repository._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. NULL 값 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_list 
                    WHERE law_id IS NULL OR law_name_korean IS NULL
                """)
                null_law_count = cursor.fetchone()[0]
                if null_law_count > 0:
                    errors.append(f"법령 목록에서 필수 필드가 NULL인 레코드 {null_law_count}개 발견")
                
                cursor.execute("""
                    SELECT COUNT(*) FROM law_articles 
                    WHERE law_id IS NULL OR article_content IS NULL
                """)
                null_article_count = cursor.fetchone()[0]
                if null_article_count > 0:
                    errors.append(f"조항에서 필수 필드가 NULL인 레코드 {null_article_count}개 발견")
                
                # 2. 데이터 타입 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_list 
                    WHERE enforcement_date IS NOT NULL 
                    AND (enforcement_date < 19000101 OR enforcement_date > 99991231)
                """)
                invalid_date_count = cursor.fetchone()[0]
                if invalid_date_count > 0:
                    errors.append(f"잘못된 시행일자 형식 {invalid_date_count}개 발견")
                
                cursor.close()
                
        except Exception as e:
            errors.append(f"데이터 무결성 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="기본 데이터 무결성",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _check_law_consistency(self) -> ValidationResult:
        """법령 데이터 일관성 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            with self.repository._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 중복 법령ID 검증
                cursor.execute("""
                    SELECT law_id, COUNT(*) as cnt 
                    FROM law_list 
                    GROUP BY law_id 
                    HAVING cnt > 1
                """)
                duplicate_laws = cursor.fetchall()
                if duplicate_laws:
                    for law_id, count in duplicate_laws:
                        errors.append(f"중복된 법령ID {law_id}: {count}개")
                
                # 2. 법령명 일관성 검증
                cursor.execute("""
                    SELECT law_id, COUNT(DISTINCT law_name_korean) as name_count
                    FROM law_list 
                    GROUP BY law_id 
                    HAVING name_count > 1
                """)
                inconsistent_names = cursor.fetchall()
                if inconsistent_names:
                    for law_id, name_count in inconsistent_names:
                        warnings.append(f"법령ID {law_id}에 대해 서로 다른 법령명 {name_count}개 존재")
                
                # 3. 시행일자 논리 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_list 
                    WHERE promulgation_date IS NOT NULL 
                    AND enforcement_date IS NOT NULL
                    AND promulgation_date > enforcement_date
                """)
                invalid_date_logic = cursor.fetchone()[0]
                if invalid_date_logic > 0:
                    errors.append(f"공포일자가 시행일자보다 늦은 법령 {invalid_date_logic}개 발견")
                
                cursor.close()
                
        except Exception as e:
            errors.append(f"법령 일관성 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="법령 데이터 일관성",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _check_article_consistency(self) -> ValidationResult:
        """조항 데이터 일관성 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            with self.repository._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 조항 번호 중복 검증
                cursor.execute("""
                    SELECT law_key, article_no, COUNT(*) as cnt
                    FROM law_articles 
                    GROUP BY law_key, article_no, paragraph_no, item_no, subitem_no
                    HAVING cnt > 1
                """)
                duplicate_articles = cursor.fetchall()
                if duplicate_articles:
                    for law_key, article_no, count in duplicate_articles:
                        errors.append(f"법령키 {law_key}, 조항 {article_no}에서 중복 {count}개")
                
                # 2. 조항 내용 길이 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_articles 
                    WHERE article_content IS NOT NULL 
                    AND LENGTH(article_content) < 10
                """)
                short_content_count = cursor.fetchone()[0]
                if short_content_count > 0:
                    warnings.append(f"조항 내용이 너무 짧은 조항 {short_content_count}개 발견")
                
                # 3. 조항 번호 순서 검증
                cursor.execute("""
                    SELECT law_key, COUNT(*) as total_articles,
                           COUNT(DISTINCT article_no) as unique_articles
                    FROM law_articles 
                    GROUP BY law_key
                    HAVING total_articles != unique_articles
                """)
                inconsistent_numbering = cursor.fetchall()
                if inconsistent_numbering:
                    for law_key, total, unique in inconsistent_numbering:
                        warnings.append(f"법령키 {law_key}에서 조항 번호 불일치 (전체: {total}, 고유: {unique})")
                
                cursor.close()
                
        except Exception as e:
            errors.append(f"조항 일관성 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="조항 데이터 일관성",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _check_relationship_integrity(self) -> ValidationResult:
        """관계 무결성 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            with self.repository._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 고아 조항 검증 (법령 목록에 없는 법령ID를 참조하는 조항)
                cursor.execute("""
                    SELECT COUNT(*) FROM law_articles la
                    LEFT JOIN law_list ll ON la.law_id = ll.law_id
                    WHERE ll.law_id IS NULL
                """)
                orphan_articles = cursor.fetchone()[0]
                if orphan_articles > 0:
                    errors.append(f"고아 조항 {orphan_articles}개 발견 (참조하는 법령이 존재하지 않음)")
                
                # 2. 법령 본문과 조항의 일관성 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_content lc
                    LEFT JOIN law_list ll ON lc.law_id = ll.law_id
                    WHERE ll.law_id IS NULL
                """)
                orphan_contents = cursor.fetchone()[0]
                if orphan_contents > 0:
                    errors.append(f"고아 법령 본문 {orphan_contents}개 발견")
                
                # 3. 법령키와 법령ID 일관성 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_articles 
                    WHERE law_key != law_id
                """)
                inconsistent_keys = cursor.fetchone()[0]
                if inconsistent_keys > 0:
                    warnings.append(f"법령키와 법령ID가 일치하지 않는 조항 {inconsistent_keys}개 발견")
                
                cursor.close()
                
        except Exception as e:
            errors.append(f"관계 무결성 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="관계 무결성",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _check_duplicate_data(self) -> ValidationResult:
        """중복 데이터 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            with self.repository._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 완전히 동일한 법령 목록 검증
                cursor.execute("""
                    SELECT law_name_korean, enforcement_date, COUNT(*) as cnt
                    FROM law_list 
                    GROUP BY law_name_korean, enforcement_date
                    HAVING cnt > 1
                """)
                duplicate_law_names = cursor.fetchall()
                if duplicate_law_names:
                    for name, date, count in duplicate_law_names:
                        warnings.append(f"동일한 법령명과 시행일자를 가진 법령 {count}개: {name}")
                
                # 2. 동일한 조항 내용 검증
                cursor.execute("""
                    SELECT article_content, COUNT(*) as cnt
                    FROM law_articles 
                    WHERE LENGTH(article_content) > 50
                    GROUP BY article_content
                    HAVING cnt > 5
                """)
                duplicate_contents = cursor.fetchall()
                if duplicate_contents:
                    for content, count in duplicate_contents:
                        warnings.append(f"동일한 조항 내용이 {count}번 반복됨: {content[:50]}...")
                
                cursor.close()
                
        except Exception as e:
            errors.append(f"중복 데이터 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="중복 데이터",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _check_date_consistency(self) -> ValidationResult:
        """날짜 데이터 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            with self.repository._get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. 미래 날짜 검증
                today = int(date.today().strftime('%Y%m%d'))
                cursor.execute("""
                    SELECT COUNT(*) FROM law_list 
                    WHERE enforcement_date > %s
                """, (today,))
                future_enforcement = cursor.fetchone()[0]
                if future_enforcement > 0:
                    warnings.append(f"미래 시행일자를 가진 법령 {future_enforcement}개 발견")
                
                # 2. 너무 오래된 날짜 검증
                cursor.execute("""
                    SELECT COUNT(*) FROM law_list 
                    WHERE enforcement_date < 19000101
                """)
                very_old_dates = cursor.fetchone()[0]
                if very_old_dates > 0:
                    errors.append(f"1900년 이전 시행일자를 가진 법령 {very_old_dates}개 발견")
                
                # 3. 동기화 상태 날짜 검증
                cursor.execute("""
                    SELECT last_sync_date FROM sync_status 
                    WHERE last_sync_date > CURDATE()
                """)
                future_sync_dates = cursor.fetchall()
                if future_sync_dates:
                    errors.append(f"미래 동기화 날짜 {len(future_sync_dates)}개 발견")
                
                cursor.close()
                
        except Exception as e:
            errors.append(f"날짜 일관성 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="날짜 데이터 일관성",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _check_statistics_consistency(self) -> ValidationResult:
        """통계 데이터 검증"""
        start_time = datetime.now()
        errors = []
        warnings = []
        
        try:
            stats = self.repository.get_database_stats()
            
            # 1. 기본 통계 검증
            if stats.total_laws == 0:
                warnings.append("데이터베이스에 법령 데이터가 없습니다")
            
            if stats.total_articles == 0:
                warnings.append("데이터베이스에 조항 데이터가 없습니다")
            
            # 2. 평균 조항 수 검증
            if stats.total_laws > 0:
                avg_articles = stats.total_articles / stats.total_laws
                if avg_articles < 1:
                    warnings.append(f"법령당 평균 조항 수가 너무 적습니다: {avg_articles:.2f}")
                elif avg_articles > 1000:
                    warnings.append(f"법령당 평균 조항 수가 너무 많습니다: {avg_articles:.2f}")
            
            # 3. 동기화 상태 검증
            if stats.last_sync_date is None:
                warnings.append("마지막 동기화 날짜가 설정되지 않았습니다")
            elif stats.last_sync_date < date.today() - timedelta(days=7):
                warnings.append(f"마지막 동기화가 오래되었습니다: {stats.last_sync_date}")
                
        except Exception as e:
            errors.append(f"통계 일관성 검증 중 오류: {str(e)}")
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return ValidationResult(
            check_name="통계 데이터 일관성",
            is_valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
            details=errors + warnings,
            execution_time_ms=execution_time
        )
    
    def _fix_detected_issues(self, validation_results: List[ValidationResult]):
        """감지된 문제들 자동 수정 시도"""
        logger.info("감지된 문제들 자동 수정 시도 시작")
        
        try:
            with self.repository.transaction():
                # 간단한 수정 작업들만 수행
                with self.repository._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # 1. NULL 값을 기본값으로 대체
                    cursor.execute("""
                        UPDATE law_list 
                        SET law_name_korean = CONCAT('법령_', law_id)
                        WHERE law_name_korean IS NULL OR law_name_korean = ''
                    """)
                    
                    # 2. 잘못된 날짜 형식 수정 (기본값으로 대체)
                    cursor.execute("""
                        UPDATE law_list 
                        SET enforcement_date = 20240101
                        WHERE enforcement_date IS NOT NULL 
                        AND (enforcement_date < 19000101 OR enforcement_date > 99991231)
                    """)
                    
                    cursor.close()
                    
            logger.info("자동 수정 완료")
            
        except Exception as e:
            logger.error("자동 수정 실패", error=str(e))
    
    def print_validation_report(self, summary: ValidationSummary):
        """검증 결과 리포트 출력"""
        print("\n" + "="*80)
        print("데이터 검증 결과 리포트")
        print("="*80)
        print(f"전체 검증 항목: {summary.total_checks}")
        print(f"통과한 검증: {summary.passed_checks}")
        print(f"실패한 검증: {summary.failed_checks}")
        print(f"총 오류 수: {summary.total_errors}")
        print(f"총 경고 수: {summary.total_warnings}")
        print(f"실행 시간: {summary.execution_time_seconds:.2f}초")
        print("="*80)
        
        for result in summary.results:
            status = "✅ PASS" if result.is_valid else "❌ FAIL"
            print(f"\n{status} {result.check_name}")
            print(f"  실행 시간: {result.execution_time_ms:.1f}ms")
            print(f"  오류: {result.error_count}개, 경고: {result.warning_count}개")
            
            if result.details:
                print("  상세 내용:")
                for detail in result.details[:5]:  # 최대 5개만 표시
                    print(f"    - {detail}")
                if len(result.details) > 5:
                    print(f"    ... 및 {len(result.details) - 5}개 추가 항목")
        
        print("\n" + "="*80)

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='데이터 검증 및 일관성 체크 스크립트')
    parser.add_argument('--fix', action='store_true',
                       help='감지된 문제들 자동 수정 시도')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='상세 로그 출력')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='요약만 출력')
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        import logging
        logging.getLogger().setLevel(logging.WARNING)
    
    # 데이터 검증 실행
    validator = DataValidator()
    try:
        summary = validator.run_full_validation(fix_issues=args.fix)
        
        if not args.quiet:
            validator.print_validation_report(summary)
        else:
            print(f"검증 완료: {summary.passed_checks}/{summary.total_checks} 통과, "
                  f"오류 {summary.total_errors}개, 경고 {summary.total_warnings}개")
        
        # 오류가 있으면 종료 코드 1 반환
        sys.exit(0 if summary.failed_checks == 0 else 1)
        
    except Exception as e:
        logger.error("데이터 검증 실행 실패", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()