"""데이터베이스 저장소 계층 종합 테스트"""
import pytest
from datetime import date, datetime, timedelta
from typing import List
import uuid

from src.database.repository import LegalDataRepository
from src.database.models import (
    Law, Article, LawVersion, BatchJob, SyncStatus,
    JobStatus, JobType, SyncType
)
from src.database.connection import db_connection


class TestLegalDataRepository:
    """법령 데이터 저장소 종합 테스트"""
    
    @pytest.fixture
    def repository(self):
        """저장소 인스턴스 생성"""
        return LegalDataRepository()
    
    @pytest.fixture
    def sample_law(self):
        """테스트용 법령 데이터"""
        return Law(
            law_id="LAW001",
            law_master_no="MASTER001",
            law_name="테스트 법령",
            law_type="법률",
            promulgation_date=date(2024, 1, 1),
            enforcement_date=date(2024, 2, 1),
            content="테스트 법령 내용",
            is_latest=True
        )
    
    @pytest.fixture
    def sample_articles(self):
        """테스트용 조항 데이터"""
        return [
            Article(
                law_master_no="MASTER001",
                article_no="1",
                article_title="제1조",
                article_content="제1조 내용",
                article_order=1
            ),
            Article(
                law_master_no="MASTER001",
                article_no="2",
                article_title="제2조",
                article_content="제2조 내용",
                article_order=2
            )
        ]
    
    @pytest.fixture
    def sample_law_version(self):
        """테스트용 법령 버전 데이터"""
        return LawVersion(
            law_id="LAW001",
            law_master_no="MASTER001",
            version_no=1,
            enforcement_date=date(2024, 2, 1),
            is_latest=True
        )
    
    def test_database_connection(self):
        """데이터베이스 연결 테스트"""
        assert db_connection.test_connection() == True
    
    def test_transaction_context_manager(self, repository):
        """트랜잭션 컨텍스트 매니저 테스트"""
        with repository.transaction():
            # 트랜잭션 내에서 작업 수행
            assert repository._transaction_active == True
        
        # 트랜잭션 종료 후
        assert repository._transaction_active == False
    
    def test_transaction_rollback(self, repository, sample_law):
        """트랜잭션 롤백 테스트"""
        try:
            with repository.transaction():
                # 법령 저장
                repository.save_law(sample_law)
                
                # 의도적으로 예외 발생
                raise Exception("테스트 예외")
                
        except Exception:
            pass
        
        # 롤백되어 데이터가 저장되지 않았는지 확인
        saved_law = repository.get_law_by_master_no(sample_law.law_master_no)
        assert saved_law is None
    
    def test_save_and_get_law(self, repository, sample_law):
        """법령 저장 및 조회 테스트"""
        # 법령 저장
        result = repository.save_law(sample_law)
        assert result == True
        
        # 법령마스터번호로 조회
        saved_law = repository.get_law_by_master_no(sample_law.law_master_no)
        assert saved_law is not None
        assert saved_law.law_id == sample_law.law_id
        assert saved_law.law_name == sample_law.law_name
        
        # 법령ID로 최신 법령 조회
        latest_law = repository.get_law_by_id(sample_law.law_id)
        assert latest_law is not None
        assert latest_law.is_latest == True
        
        # 정리
        repository.delete_law_by_master_no(sample_law.law_master_no)
    
    def test_save_and_get_articles(self, repository, sample_law, sample_articles):
        """조항 저장 및 조회 테스트"""
        # 먼저 법령 저장
        repository.save_law(sample_law)
        
        # 조항 저장
        result = repository.save_articles(sample_articles)
        assert result == True
        
        # 조항 조회
        saved_articles = repository.get_articles_by_law_master_no(sample_law.law_master_no)
        assert len(saved_articles) == 2
        assert saved_articles[0].article_no == "1"
        assert saved_articles[1].article_no == "2"
        
        # 정리
        repository.delete_law_by_master_no(sample_law.law_master_no)
    
    def test_law_version_management(self, repository, sample_law, sample_law_version):
        """법령 버전 관리 테스트"""
        # 법령 및 버전 저장
        repository.save_law(sample_law)
        repository.save_law_version(sample_law_version)
        
        # 기존 버전 조회
        versions = repository.get_existing_law_versions(sample_law.law_id)
        assert len(versions) == 1
        assert versions[0].version_no == 1
        
        # 새 버전 추가
        new_version = LawVersion(
            law_id="LAW001",
            law_master_no="MASTER002",
            version_no=2,
            enforcement_date=date(2024, 3, 1),
            is_latest=False
        )
        
        new_law = Law(
            law_id="LAW001",
            law_master_no="MASTER002",
            law_name="테스트 법령 개정",
            law_type="법률",
            enforcement_date=date(2024, 3, 1),
            is_latest=False
        )
        
        repository.save_law(new_law)
        repository.save_law_version(new_version)
        
        # 최신 버전 플래그 업데이트
        repository.update_latest_flags("LAW001", "MASTER002")
        
        # 최신 버전 확인
        latest_law = repository.get_law_by_id("LAW001")
        assert latest_law.law_master_no == "MASTER002"
        assert latest_law.is_latest == True
        
        # 정리
        repository.delete_law_by_master_no("MASTER001")
        repository.delete_law_by_master_no("MASTER002")
    
    def test_batch_job_management(self, repository):
        """배치 작업 관리 테스트"""
        # 배치 작업 생성
        job_id = repository.create_batch_job(
            JobType.INCREMENTAL_SYNC, 
            last_sync_date=date.today()
        )
        assert job_id is not None
        
        # 배치 작업 조회
        batch_job = repository.get_batch_job(job_id)
        assert batch_job is not None
        assert batch_job.job_type == JobType.INCREMENTAL_SYNC
        assert batch_job.status == JobStatus.PENDING
        
        # 배치 작업 상태 업데이트
        result = repository.update_batch_job_status(
            job_id, 
            JobStatus.SUCCESS,
            processed_laws=10,
            processed_articles=50
        )
        assert result == True
        
        # 업데이트된 상태 확인
        updated_job = repository.get_batch_job(job_id)
        assert updated_job.status == JobStatus.SUCCESS
        assert updated_job.processed_laws == 10
        assert updated_job.processed_articles == 50
        
        # 최근 배치 작업 조회
        recent_jobs = repository.get_recent_batch_jobs(limit=5)
        assert len(recent_jobs) >= 1
        assert any(job.job_id == job_id for job in recent_jobs)
    
    def test_sync_status_management(self, repository):
        """동기화 상태 관리 테스트"""
        sync_date = date.today()
        
        # 동기화 상태 업데이트
        result = repository.update_sync_status(
            "INCREMENTAL",
            sync_date,
            total_laws_count=100,
            total_articles_count=500
        )
        assert result == True
        
        # 동기화 상태 조회
        sync_status = repository.get_sync_status("INCREMENTAL")
        assert sync_status is not None
        assert sync_status.last_sync_date == sync_date
        assert sync_status.total_laws_count == 100
        
        # 마지막 동기화 날짜 조회
        last_sync_date = repository.get_last_sync_date("INCREMENTAL")
        assert last_sync_date == sync_date
    
    def test_bulk_operations(self, repository):
        """대량 처리 테스트"""
        # 테스트용 법령 데이터 생성
        laws = []
        versions = []
        
        for i in range(5):
            law = Law(
                law_id=f"BULK_LAW_{i:03d}",
                law_master_no=f"BULK_MASTER_{i:03d}",
                law_name=f"대량 테스트 법령 {i+1}",
                law_type="법률",
                enforcement_date=date.today(),
                is_latest=True
            )
            laws.append(law)
            
            version = LawVersion(
                law_id=f"BULK_LAW_{i:03d}",
                law_master_no=f"BULK_MASTER_{i:03d}",
                version_no=1,
                enforcement_date=date.today(),
                is_latest=True
            )
            versions.append(version)
        
        # 대량 저장
        inserted, updated = repository.bulk_save_laws(laws)
        assert inserted == 5
        assert updated == 0
        
        version_inserted, version_updated = repository.bulk_save_law_versions(versions)
        assert version_inserted == 5
        assert version_updated == 0
        
        # 저장된 데이터 확인
        law_ids = [f"BULK_LAW_{i:03d}" for i in range(5)]
        saved_laws = repository.get_laws_by_ids(law_ids)
        assert len(saved_laws) == 5
        
        # 정리
        for law in laws:
            repository.delete_law_by_master_no(law.law_master_no)
    
    def test_data_integrity_validation(self, repository):
        """데이터 정합성 검증 테스트"""
        # 정상 데이터로 검증
        validation_result = repository.validate_data_integrity()
        assert 'is_valid' in validation_result
        assert 'issues' in validation_result
        assert 'statistics' in validation_result
    
    def test_database_statistics(self, repository):
        """데이터베이스 통계 테스트"""
        stats = repository.get_database_stats()
        assert hasattr(stats, 'total_laws')
        assert hasattr(stats, 'total_articles')
        assert hasattr(stats, 'latest_laws')
        assert hasattr(stats, 'total_versions')
        
        # 통계 값이 음수가 아닌지 확인
        assert stats.total_laws >= 0
        assert stats.total_articles >= 0
        assert stats.latest_laws >= 0
        assert stats.total_versions >= 0
    
    def test_batch_job_statistics(self, repository):
        """배치 작업 통계 테스트"""
        # 테스트용 배치 작업 생성
        job_id = repository.create_batch_job(JobType.VALIDATION)
        repository.update_batch_job_status(job_id, JobStatus.SUCCESS, processed_laws=5)
        
        # 통계 조회
        stats = repository.get_batch_job_statistics(days=7)
        assert 'period_days' in stats
        assert 'statistics' in stats
        assert 'generated_at' in stats
        assert stats['period_days'] == 7
    
    def test_enforcement_date_range_query(self, repository):
        """시행일 범위 조회 테스트"""
        # 테스트용 법령 생성
        test_law = Law(
            law_id="DATE_TEST_LAW",
            law_master_no="DATE_TEST_MASTER",
            law_name="시행일 테스트 법령",
            enforcement_date=date.today(),
            is_latest=True
        )
        
        repository.save_law(test_law)
        
        # 시행일 범위로 조회
        start_date = date.today() - timedelta(days=1)
        end_date = date.today() + timedelta(days=1)
        
        laws_in_range = repository.get_laws_by_enforcement_date_range(
            start_date, end_date, latest_only=True
        )
        
        # 테스트 법령이 포함되어 있는지 확인
        assert any(law.law_master_no == "DATE_TEST_MASTER" for law in laws_in_range)
        
        # 정리
        repository.delete_law_by_master_no("DATE_TEST_MASTER")
    
    def test_error_handling(self, repository):
        """오류 처리 테스트"""
        # 존재하지 않는 법령 조회
        non_existent_law = repository.get_law_by_master_no("NON_EXISTENT")
        assert non_existent_law is None
        
        # 존재하지 않는 배치 작업 조회
        non_existent_job = repository.get_batch_job("NON_EXISTENT_JOB")
        assert non_existent_job is None
        
        # 빈 리스트로 대량 저장
        inserted, updated = repository.bulk_save_laws([])
        assert inserted == 0
        assert updated == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])