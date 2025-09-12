"""데이터베이스 저장소 계층 단위 테스트 (Mock 사용)"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
from contextlib import contextmanager

from src.database.repository import LegalDataRepository
from src.database.models import (
    Law, Article, LawVersion, BatchJob, SyncStatus,
    JobStatus, JobType, SyncType
)


class TestLegalDataRepositoryUnit:
    """법령 데이터 저장소 단위 테스트 (Mock 사용)"""
    
    @pytest.fixture
    def repository(self):
        """저장소 인스턴스 생성"""
        return LegalDataRepository()
    
    @pytest.fixture
    def mock_connection(self):
        """Mock 데이터베이스 연결"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor
    
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
    
    def test_transaction_context_manager(self, repository):
        """트랜잭션 컨텍스트 매니저 테스트"""
        with patch('src.database.repository.db_connection') as mock_db:
            mock_conn = Mock()
            
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # 트랜잭션 시작
            with repository.transaction():
                assert repository._transaction_active == True
                assert repository._current_connection == mock_conn
            
            # 트랜잭션 종료 후
            assert repository._transaction_active == False
            assert repository._current_connection is None
            
            # 커밋이 호출되었는지 확인
            mock_conn.start_transaction.assert_called_once()
            mock_conn.commit.assert_called_once()
    
    def test_transaction_rollback_on_exception(self, repository):
        """트랜잭션 예외 시 롤백 테스트"""
        with patch('src.database.repository.db_connection') as mock_db:
            mock_conn = Mock()
            
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # 예외 발생 시 롤백 테스트
            with pytest.raises(ValueError):
                with repository.transaction():
                    raise ValueError("테스트 예외")
            
            # 롤백이 호출되었는지 확인
            mock_conn.rollback.assert_called_once()
    
    def test_save_law_new(self, repository, sample_law, mock_connection):
        """새 법령 저장 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # 기존 법령이 없다고 가정
            mock_cursor.fetchone.return_value = None
            mock_cursor.rowcount = 1
            
            result = repository.save_law(sample_law)
            
            assert result == True
            # INSERT 쿼리가 실행되었는지 확인
            assert mock_cursor.execute.call_count >= 1
            mock_cursor.close.assert_called()
    
    def test_save_law_update(self, repository, sample_law, mock_connection):
        """기존 법령 업데이트 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # 기존 법령이 있다고 가정
            existing_law_data = {
                'id': 1,
                'law_id': 'LAW001',
                'law_master_no': 'MASTER001',
                'law_name': '기존 법령',
                'law_type': '법률',
                'promulgation_date': date(2024, 1, 1),
                'enforcement_date': date(2024, 2, 1),
                'content': '기존 내용',
                'is_latest': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            mock_cursor.fetchone.return_value = existing_law_data
            mock_cursor.rowcount = 1
            
            result = repository.save_law(sample_law)
            
            assert result == True
            # UPDATE 쿼리가 실행되었는지 확인
            assert mock_cursor.execute.call_count >= 1
    
    def test_get_law_by_id(self, repository, mock_connection):
        """법령ID로 조회 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # Mock 데이터 반환
            law_data = {
                'id': 1,
                'law_id': 'LAW001',
                'law_master_no': 'MASTER001',
                'law_name': '테스트 법령',
                'law_type': '법률',
                'promulgation_date': date(2024, 1, 1),
                'enforcement_date': date(2024, 2, 1),
                'content': '테스트 내용',
                'is_latest': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            }
            mock_cursor.fetchone.return_value = law_data
            
            result = repository.get_law_by_id("LAW001")
            
            assert result is not None
            assert result.law_id == "LAW001"
            assert result.law_name == "테스트 법령"
            mock_cursor.close.assert_called()
    
    def test_save_articles(self, repository, mock_connection):
        """조항 저장 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        articles = [
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
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            mock_cursor.rowcount = 2
            
            result = repository.save_articles(articles)
            
            assert result == True
            # DELETE와 INSERT 쿼리가 실행되었는지 확인
            assert mock_cursor.execute.call_count >= 1
            assert mock_cursor.executemany.call_count >= 1
    
    def test_create_batch_job(self, repository, mock_connection):
        """배치 작업 생성 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            job_id = repository.create_batch_job(
                JobType.INCREMENTAL_SYNC,
                last_sync_date=date.today()
            )
            
            assert job_id is not None
            assert "INCREMENTAL_SYNC" in job_id
            mock_cursor.execute.assert_called()
            mock_cursor.close.assert_called()
    
    def test_update_batch_job_status(self, repository, mock_connection):
        """배치 작업 상태 업데이트 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            mock_cursor.rowcount = 1
            
            result = repository.update_batch_job_status(
                "test_job_id",
                JobStatus.SUCCESS,
                processed_laws=10,
                processed_articles=50
            )
            
            assert result == True
            mock_cursor.execute.assert_called()
            mock_cursor.close.assert_called()
    
    def test_update_latest_flags(self, repository, mock_connection):
        """최신 버전 플래그 업데이트 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            result = repository.update_latest_flags("LAW001", "MASTER002")
            
            assert result == True
            # 4개의 UPDATE 쿼리가 실행되어야 함 (laws 2개, law_versions 2개)
            assert mock_cursor.execute.call_count == 4
            mock_cursor.close.assert_called()
    
    def test_bulk_save_laws(self, repository, mock_connection):
        """법령 대량 저장 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        laws = [
            Law(
                law_id=f"BULK_LAW_{i:03d}",
                law_master_no=f"BULK_MASTER_{i:03d}",
                law_name=f"대량 테스트 법령 {i+1}",
                law_type="법률",
                enforcement_date=date.today(),
                is_latest=True
            )
            for i in range(3)
        ]
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # 트랜잭션 컨텍스트 매니저 Mock
            repository._transaction_active = True
            repository._current_connection = mock_conn
            
            # 기존 법령이 없다고 가정
            mock_cursor.fetchall.return_value = []
            mock_cursor.rowcount = 3
            
            inserted, updated = repository.bulk_save_laws(laws)
            
            assert inserted == 3
            assert updated == 0
            
            # 기존 법령 조회와 대량 삽입이 실행되었는지 확인
            assert mock_cursor.execute.call_count >= 1
            assert mock_cursor.executemany.call_count >= 1
    
    def test_validate_data_integrity(self, repository, mock_connection):
        """데이터 정합성 검증 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # 정상 데이터 시나리오
            mock_cursor.fetchone.side_effect = [
                (0,),  # 고아 조항 없음
                (0,),  # 고아 버전 없음
            ]
            mock_cursor.fetchall.side_effect = [
                [],    # 중복 법령마스터번호 없음
                [],    # 다중 최신 버전 없음
            ]
            
            result = repository.validate_data_integrity()
            
            assert result['is_valid'] == True
            assert len(result['issues']) == 0
            assert 'statistics' in result
    
    def test_get_database_stats(self, repository, mock_connection):
        """데이터베이스 통계 조회 테스트"""
        mock_conn, mock_cursor = mock_connection
        
        with patch('src.database.repository.db_connection') as mock_db:
            @contextmanager
            def mock_get_connection():
                yield mock_conn
            
            mock_db.get_connection = mock_get_connection
            
            # Mock 통계 데이터
            mock_cursor.fetchone.side_effect = [
                (100,),      # 총 법령 수
                (95,),       # 최신 법령 수
                (500,),      # 총 조항 수
                (150,),      # 총 버전 수
                (date.today(),),  # 마지막 동기화 날짜
                None         # 마지막 배치 작업 없음
            ]
            
            stats = repository.get_database_stats()
            
            assert stats.total_laws == 100
            assert stats.latest_laws == 95
            assert stats.total_articles == 500
            assert stats.total_versions == 150
            assert stats.last_sync_date == date.today()
    
    def test_error_handling(self, repository):
        """오류 처리 테스트"""
        with patch('src.database.repository.db_connection') as mock_db:
            # 데이터베이스 연결 오류 시뮬레이션
            mock_db.get_connection.side_effect = Exception("Connection failed")
            
            # 법령 저장 실패
            sample_law = Law(
                law_id="ERROR_LAW",
                law_master_no="ERROR_MASTER",
                law_name="오류 테스트 법령"
            )
            
            result = repository.save_law(sample_law)
            assert result == False
            
            # 법령 조회 실패
            result = repository.get_law_by_id("ERROR_LAW")
            assert result is None
    
    def test_empty_list_handling(self, repository):
        """빈 리스트 처리 테스트"""
        # 빈 법령 리스트 저장
        inserted, updated = repository.bulk_save_laws([])
        assert inserted == 0
        assert updated == 0
        
        # 빈 조항 리스트 저장
        result = repository.save_articles([])
        assert result == True
        
        # 빈 법령ID 리스트 조회
        laws = repository.get_laws_by_ids([])
        assert laws == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])