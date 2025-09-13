"""Mock 환경 설정 관리"""
import os
from typing import Dict, Any, Optional
from pathlib import Path

from .data_generator import MockDataGenerator
from .api_mock import MockAPIClient, create_mock_api_client
from .database_mock import MockDatabaseConnection, create_mock_db_connection


class MockEnvironment:
    """Mock 환경 설정 및 관리자"""
    
    def __init__(self, 
                 use_mock_api: bool = True,
                 use_mock_db: bool = True,
                 mock_data_count: int = 50,
                 enable_api_delay: bool = True,
                 api_error_rate: float = 0.02):
        """
        Mock 환경 초기화
        
        Args:
            use_mock_api: Mock API 사용 여부
            use_mock_db: Mock 데이터베이스 사용 여부  
            mock_data_count: 초기 생성할 Mock 데이터 개수
            enable_api_delay: API 지연 시뮬레이션 여부
            api_error_rate: API 에러율 (0.0~1.0)
        """
        self.use_mock_api = use_mock_api
        self.use_mock_db = use_mock_db
        self.mock_data_count = mock_data_count
        self.enable_api_delay = enable_api_delay
        self.api_error_rate = api_error_rate
        
        # 컴포넌트들
        self.data_generator = MockDataGenerator()
        self.api_client = None
        self.db_connection = None
        
        # 초기화
        self._setup_mock_environment()
    
    def _setup_mock_environment(self):
        """Mock 환경 설정"""
        # Mock 데이터 생성
        self._ensure_mock_data()
        
        # Mock API 설정
        if self.use_mock_api:
            self.api_client = create_mock_api_client(
                enable_delay=self.enable_api_delay,
                error_rate=self.api_error_rate
            )
        
        # Mock DB 설정
        if self.use_mock_db:
            self.db_connection = create_mock_db_connection(populate=True)
    
    def _ensure_mock_data(self):
        """Mock 데이터 파일 확인 및 생성"""
        sample_data_dir = Path("sample_data")
        mock_file = sample_data_dir / "legal_documents.json"
        
        if not mock_file.exists() or self._should_regenerate_data():
            print(f"Mock 데이터를 생성합니다... (개수: {self.mock_data_count})")
            documents = self.data_generator.generate_multiple_documents(self.mock_data_count)
            self.data_generator.save_mock_data(documents, "legal_documents.json")
            print(f"Mock 데이터가 {mock_file}에 저장되었습니다.")
    
    def _should_regenerate_data(self) -> bool:
        """Mock 데이터 재생성 여부 결정"""
        # 환경 변수로 강제 재생성 설정
        if os.getenv('FORCE_REGENERATE_MOCK_DATA', '').lower() == 'true':
            return True
        
        # 파일이 너무 오래된 경우 (7일 이상)
        sample_data_dir = Path("sample_data")
        mock_file = sample_data_dir / "legal_documents.json"
        
        if mock_file.exists():
            import time
            file_age_days = (time.time() - mock_file.stat().st_mtime) / (24 * 3600)
            return file_age_days > 7
        
        return False
    
    def get_api_client(self):
        """API 클라이언트 반환"""
        if self.use_mock_api and self.api_client:
            return self.api_client
        else:
            # 실제 API 클라이언트를 반환해야 하는 경우
            from api.client import APIClient  # 실제 API 클라이언트
            return APIClient()
    
    def get_db_connection(self):
        """DB 연결 반환"""
        if self.use_mock_db and self.db_connection:
            return self.db_connection
        else:
            # 실제 DB 연결을 반환해야 하는 경우
            from ..database.connection import get_connection  # 실제 DB 연결
            return get_connection()
    
    def create_test_data(self, count: int = 10) -> str:
        """테스트용 추가 데이터 생성"""
        documents = self.data_generator.generate_multiple_documents(count)
        filename = f"test_data_{count}.json"
        file_path = self.data_generator.save_mock_data(documents, filename)
        
        # Mock DB에도 추가
        if self.db_connection:
            self.db_connection.bulk_insert_documents(documents)
        
        return file_path
    
    def reset_mock_data(self):
        """Mock 데이터 초기화"""
        print("Mock 데이터를 초기화합니다...")
        
        # 새 데이터 생성
        documents = self.data_generator.generate_multiple_documents(self.mock_data_count)
        self.data_generator.save_mock_data(documents, "legal_documents.json")
        
        # Mock DB 초기화
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = create_mock_db_connection(populate=True)
        
        # API 클라이언트 통계 리셋
        if self.api_client:
            self.api_client.reset_stats()
        
        print("Mock 데이터 초기화가 완료되었습니다.")
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Mock 환경 정보 반환"""
        info = {
            "use_mock_api": self.use_mock_api,
            "use_mock_db": self.use_mock_db,
            "mock_data_count": self.mock_data_count,
            "enable_api_delay": self.enable_api_delay,
            "api_error_rate": self.api_error_rate
        }
        
        # API 클라이언트 통계
        if self.api_client:
            info["api_stats"] = self.api_client.get_stats()
        
        # DB 통계
        if self.db_connection:
            info["db_stats"] = self.db_connection.get_statistics()
        
        return info
    
    def configure_for_development(self):
        """개발 환경 최적화 설정"""
        self.enable_api_delay = False  # 개발시 빠른 응답
        self.api_error_rate = 0.01     # 낮은 에러율
        
        if self.api_client:
            self.api_client.enable_delay(False)
            self.api_client.set_error_rate(0.01)
        
        print("개발 환경으로 설정되었습니다. (지연 없음, 낮은 에러율)")
    
    def configure_for_testing(self):
        """테스트 환경 최적화 설정"""
        self.enable_api_delay = False  # 테스트시 빠른 실행
        self.api_error_rate = 0.05     # 에러 상황 테스트를 위해 약간 높게
        
        if self.api_client:
            self.api_client.enable_delay(False)
            self.api_client.set_error_rate(0.05)
        
        print("테스트 환경으로 설정되었습니다. (지연 없음, 에러 시뮬레이션 포함)")
    
    def configure_for_demo(self):
        """데모 환경 최적화 설정"""
        self.enable_api_delay = True   # 실제와 비슷한 지연
        self.api_error_rate = 0.02     # 가끔 에러로 현실성 추가
        
        if self.api_client:
            self.api_client.enable_delay(True)
            self.api_client.set_error_rate(0.02)
        
        print("데모 환경으로 설정되었습니다. (실제 환경과 유사한 지연 및 에러율)")
    
    def cleanup(self):
        """리소스 정리"""
        if self.db_connection:
            self.db_connection.close()
        
        print("Mock 환경이 정리되었습니다.")


# 전역 Mock 환경 인스턴스
_mock_environment: Optional[MockEnvironment] = None


def get_mock_environment() -> MockEnvironment:
    """전역 Mock 환경 인스턴스 반환"""
    global _mock_environment
    
    if _mock_environment is None:
        # 환경 변수에서 설정 읽기
        use_mock_api = os.getenv('USE_MOCK_API', 'true').lower() == 'true'
        use_mock_db = os.getenv('USE_MOCK_DB', 'true').lower() == 'true'
        mock_data_count = int(os.getenv('MOCK_DATA_COUNT', '50'))
        enable_api_delay = os.getenv('MOCK_API_DELAY', 'true').lower() == 'true'
        api_error_rate = float(os.getenv('MOCK_API_ERROR_RATE', '0.02'))
        
        _mock_environment = MockEnvironment(
            use_mock_api=use_mock_api,
            use_mock_db=use_mock_db,
            mock_data_count=mock_data_count,
            enable_api_delay=enable_api_delay,
            api_error_rate=api_error_rate
        )
    
    return _mock_environment


def setup_mock_environment(environment_type: str = "development"):
    """Mock 환경 설정"""
    mock_env = get_mock_environment()
    
    if environment_type == "development":
        mock_env.configure_for_development()
    elif environment_type == "testing":
        mock_env.configure_for_testing()
    elif environment_type == "demo":
        mock_env.configure_for_demo()
    else:
        print(f"알 수 없는 환경 타입: {environment_type}")
    
    return mock_env


def is_mock_enabled() -> bool:
    """Mock 환경 사용 여부 확인"""
    return os.getenv('USE_MOCK_DATA', 'true').lower() == 'true'


def patch_components_with_mock():
    """실제 컴포넌트들을 Mock으로 패치"""
    if not is_mock_enabled():
        return
    
    mock_env = get_mock_environment()
    
    # API 클라이언트 패치
    if mock_env.use_mock_api:
        try:
            from api import client
            client.APIClient = lambda *args, **kwargs: mock_env.get_api_client()
            print("API 클라이언트가 Mock으로 패치되었습니다.")
        except ImportError:
            print("API 클라이언트 모듈을 찾을 수 없습니다.")
    
    # 데이터베이스 연결 패치
    if mock_env.use_mock_db:
        try:
            from ..database import connection
            connection.get_connection = lambda: mock_env.get_db_connection()
            print("데이터베이스 연결이 Mock으로 패치되었습니다.")
        except ImportError:
            print("데이터베이스 연결 모듈을 찾을 수 없습니다.")


# 컨텍스트 매니저로 임시 Mock 환경 사용
class TemporaryMockEnvironment:
    """임시 Mock 환경 컨텍스트 매니저"""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.original_env = None
        self.temp_env = None
    
    def __enter__(self):
        global _mock_environment
        self.original_env = _mock_environment
        self.temp_env = MockEnvironment(**self.kwargs)
        _mock_environment = self.temp_env
        return self.temp_env
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        global _mock_environment
        if self.temp_env:
            self.temp_env.cleanup()
        _mock_environment = self.original_env


# 편의 함수들
def create_mock_data_file(count: int = 100, filename: str = None) -> str:
    """Mock 데이터 파일 생성"""
    generator = MockDataGenerator()
    documents = generator.generate_multiple_documents(count)
    
    if filename is None:
        filename = f"mock_legal_documents_{count}.json"
    
    file_path = generator.save_mock_data(documents, filename)
    print(f"Mock 데이터 {count}개가 {file_path}에 생성되었습니다.")
    return file_path


def print_mock_environment_status():
    """Mock 환경 상태 출력"""
    if is_mock_enabled():
        mock_env = get_mock_environment()
        info = mock_env.get_environment_info()
        
        print("=== Mock 환경 상태 ===")
        print(f"Mock API 사용: {info['use_mock_api']}")
        print(f"Mock DB 사용: {info['use_mock_db']}")
        print(f"Mock 데이터 개수: {info['mock_data_count']}")
        print(f"API 지연 시뮬레이션: {info['enable_api_delay']}")
        print(f"API 에러율: {info['api_error_rate']}")
        
        if 'api_stats' in info:
            api_stats = info['api_stats']
            print(f"API 요청 수: {api_stats['total_requests']}")
        
        if 'db_stats' in info:
            db_stats = info['db_stats']
            print(f"DB 문서 수: {db_stats['total_documents']}")
            print(f"문서 타입별: {db_stats['by_doc_type']}")
        
        print("==================")
    else:
        print("Mock 환경이 비활성화되어 있습니다.")


if __name__ == "__main__":
    # 테스트 및 데모
    print("Mock 환경 테스트 시작...")
    
    # Mock 환경 생성
    mock_env = setup_mock_environment("development")
    
    # 환경 정보 출력
    print_mock_environment_status()
    
    # 테스트 데이터 생성
    test_file = mock_env.create_test_data(10)
    print(f"테스트 데이터가 {test_file}에 생성되었습니다.")
    
    # 임시 환경 테스트
    with TemporaryMockEnvironment(mock_data_count=5, enable_api_delay=False) as temp_env:
        print("임시 Mock 환경에서 작업 중...")
        temp_info = temp_env.get_environment_info()
        print(f"임시 환경 문서 수: {temp_info['mock_data_count']}")
    
    print("Mock 환경 테스트 완료!")
