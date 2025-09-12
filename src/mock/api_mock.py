"""Mock API 클라이언트"""
import json
import time
import random
from typing import Dict, Any, List, Optional
from pathlib import Path
import asyncio
import httpx
from unittest.mock import MagicMock

from .data_generator import MockDataGenerator


class MockAPIClient:
    """개발환경용 Mock API 클라이언트"""
    
    def __init__(self, config=None, use_delay: bool = True):
        """
        Mock API 클라이언트 초기화
        
        Args:
            config: API 설정 (실제 API 클라이언트와 호환성을 위해)
            use_delay: API 호출 지연 시뮬레이션 여부
        """
        self.config = config
        self.use_delay = use_delay
        self.data_generator = MockDataGenerator()
        self.request_count = 0
        self.error_rate = 0.05  # 5% 확률로 에러 시뮬레이션
        
        # Mock 데이터 파일 경로
        self.mock_data_path = Path("sample_data")
        
    def get_law_list(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 목록 조회 (동기)"""
        if params is None:
            params = {}
            
        self._simulate_network_delay()
        self._simulate_api_error()
        
        # 기본 파라미터 설정
        default_params = {
            'display': 10,
            'start': 1,
            'type': 'law',
            'search': params.get('search', '')
        }
        default_params.update(params)
        
        # Mock 응답 생성
        response = self.data_generator.generate_api_response_mock("lawList.do", default_params)
        
        self.request_count += 1
        return response
    
    async def get_law_list_async(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 목록 조회 (비동기)"""
        if params is None:
            params = {}
            
        await self._simulate_network_delay_async()
        self._simulate_api_error()
        
        # 동기 메서드 호출
        return self.get_law_list(params)
    
    def get_law_content(self, law_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 내용 조회 (동기)"""
        if params is None:
            params = {}
            
        self._simulate_network_delay()
        self._simulate_api_error()
        
        params['LSO_ID'] = law_id
        response = self.data_generator.generate_api_response_mock("lawContent.do", params)
        
        self.request_count += 1
        return response
    
    async def get_law_content_async(self, law_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 내용 조회 (비동기)"""
        if params is None:
            params = {}
            
        await self._simulate_network_delay_async()
        self._simulate_api_error()
        
        return self.get_law_content(law_id, params)
    
    def get_law_articles(self, law_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 조문 조회 (동기)"""
        if params is None:
            params = {}
            
        self._simulate_network_delay()
        self._simulate_api_error()
        
        params['LSO_ID'] = law_id
        response = self.data_generator.generate_api_response_mock("lawArticles.do", params)
        
        self.request_count += 1
        return response
    
    async def get_law_articles_async(self, law_id: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 조문 조회 (비동기)"""
        if params is None:
            params = {}
            
        await self._simulate_network_delay_async()
        self._simulate_api_error()
        
        return self.get_law_articles(law_id, params)
    
    def batch_get_laws(self, law_ids: List[str], batch_size: int = 10) -> List[Dict[str, Any]]:
        """배치로 여러 법령 조회"""
        results = []
        
        for i in range(0, len(law_ids), batch_size):
            batch = law_ids[i:i + batch_size]
            batch_results = []
            
            for law_id in batch:
                try:
                    content = self.get_law_content(law_id)
                    batch_results.append(content)
                except Exception as e:
                    # 에러가 발생해도 계속 진행
                    batch_results.append({
                        "error": str(e),
                        "law_id": law_id
                    })
            
            results.extend(batch_results)
            
            # 배치 간 지연
            if self.use_delay and i + batch_size < len(law_ids):
                time.sleep(random.uniform(0.5, 1.5))
        
        return results
    
    def search_laws(self, query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """법령 검색"""
        if filters is None:
            filters = {}
            
        search_params = {
            'search': query,
            'display': filters.get('limit', 20),
            'start': filters.get('offset', 1) + 1,  # API는 1부터 시작
            'type': filters.get('doc_type', 'law')
        }
        
        return self.get_law_list(search_params)
    
    def get_recent_laws(self, days: int = 30, limit: int = 50) -> Dict[str, Any]:
        """최근 법령 조회"""
        params = {
            'display': limit,
            'start': 1,
            'recent_days': days
        }
        
        return self.get_law_list(params)
    
    def _simulate_network_delay(self):
        """네트워크 지연 시뮬레이션"""
        if not self.use_delay:
            return
            
        # 100ms ~ 2초 사이의 랜덤 지연
        delay = random.uniform(0.1, 2.0)
        time.sleep(delay)
    
    async def _simulate_network_delay_async(self):
        """비동기 네트워크 지연 시뮬레이션"""
        if not self.use_delay:
            return
            
        delay = random.uniform(0.1, 2.0)
        await asyncio.sleep(delay)
    
    def _simulate_api_error(self):
        """API 에러 시뮬레이션"""
        if random.random() < self.error_rate:
            error_types = [
                ("ConnectionError", "네트워크 연결 오류"),
                ("TimeoutError", "요청 시간 초과"),
                ("HTTPError", "서버 오류 (500)"),
                ("RateLimitError", "요청 한도 초과")
            ]
            
            error_type, error_msg = random.choice(error_types)
            
            if error_type == "ConnectionError":
                raise ConnectionError(error_msg)
            elif error_type == "TimeoutError":
                raise TimeoutError(error_msg)
            elif error_type == "HTTPError":
                raise httpx.HTTPStatusError(error_msg, request=MagicMock(), response=MagicMock(status_code=500))
            elif error_type == "RateLimitError":
                raise httpx.HTTPStatusError("Rate limit exceeded", request=MagicMock(), response=MagicMock(status_code=429))
    
    def get_stats(self) -> Dict[str, Any]:
        """Mock API 사용 통계"""
        return {
            "total_requests": self.request_count,
            "error_rate": self.error_rate,
            "use_delay": self.use_delay,
            "mock_data_available": self.mock_data_path.exists()
        }
    
    def reset_stats(self):
        """통계 초기화"""
        self.request_count = 0
    
    def set_error_rate(self, rate: float):
        """에러율 설정 (0.0 ~ 1.0)"""
        self.error_rate = max(0.0, min(1.0, rate))
    
    def enable_delay(self, enabled: bool = True):
        """지연 시뮬레이션 활성화/비활성화"""
        self.use_delay = enabled
    
    # 실제 API 클라이언트와의 호환성을 위한 메서드들
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockHTTPClient:
    """Mock HTTP 클라이언트 (httpx 호환)"""
    
    def __init__(self, base_url: str = "", timeout: float = 30.0):
        self.base_url = base_url
        self.timeout = timeout
        self.api_client = MockAPIClient()
    
    def get(self, url: str, params: Dict[str, Any] = None, **kwargs) -> 'MockResponse':
        """GET 요청 시뮬레이션"""
        if params is None:
            params = {}
            
        # URL에서 엔드포인트 추출
        if "lawList.do" in url:
            data = self.api_client.get_law_list(params)
        elif "lawContent.do" in url:
            law_id = params.get('LSO_ID', 'LAW-2024-001')
            data = self.api_client.get_law_content(law_id, params)
        elif "lawArticles.do" in url:
            law_id = params.get('LSO_ID', 'LAW-2024-001')
            data = self.api_client.get_law_articles(law_id, params)
        else:
            data = {"error": "Unknown endpoint"}
        
        return MockResponse(data)
    
    async def aget(self, url: str, params: Dict[str, Any] = None, **kwargs) -> 'MockResponse':
        """비동기 GET 요청 시뮬레이션"""
        if params is None:
            params = {}
            
        if "lawList.do" in url:
            data = await self.api_client.get_law_list_async(params)
        elif "lawContent.do" in url:
            law_id = params.get('LSO_ID', 'LAW-2024-001')
            data = await self.api_client.get_law_content_async(law_id, params)
        elif "lawArticles.do" in url:
            law_id = params.get('LSO_ID', 'LAW-2024-001')
            data = await self.api_client.get_law_articles_async(law_id, params)
        else:
            data = {"error": "Unknown endpoint"}
        
        return MockResponse(data)


class MockResponse:
    """Mock HTTP 응답"""
    
    def __init__(self, data: Dict[str, Any], status_code: int = 200):
        self.data = data
        self.status_code = status_code
        self._text = json.dumps(data, ensure_ascii=False, indent=2)
    
    def json(self) -> Dict[str, Any]:
        return self.data
    
    @property
    def text(self) -> str:
        return self._text
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=MagicMock(),
                response=self
            )


# 팩토리 함수
def create_mock_api_client(config=None, enable_delay: bool = True, error_rate: float = 0.05) -> MockAPIClient:
    """Mock API 클라이언트 생성"""
    client = MockAPIClient(config, enable_delay)
    client.set_error_rate(error_rate)
    return client


def create_mock_http_client(base_url: str = "", timeout: float = 30.0) -> MockHTTPClient:
    """Mock HTTP 클라이언트 생성"""
    return MockHTTPClient(base_url, timeout)


# 실제 API 클라이언트를 Mock으로 대체하는 패치 함수
def patch_api_client(api_module, mock_client: MockAPIClient = None):
    """실제 API 클라이언트를 Mock으로 패치"""
    if mock_client is None:
        mock_client = create_mock_api_client()
    
    # API 모듈의 클라이언트를 Mock으로 교체
    if hasattr(api_module, 'client'):
        api_module.client = mock_client
    if hasattr(api_module, 'APIClient'):
        api_module.APIClient = lambda *args, **kwargs: mock_client
    
    return mock_client


if __name__ == "__main__":
    # 테스트용 코드
    import asyncio
    
    async def test_mock_api():
        client = create_mock_api_client(enable_delay=False, error_rate=0.0)
        
        # 법령 목록 조회 테스트
        laws = await client.get_law_list_async({'display': 5})
        print("법령 목록:")
        print(json.dumps(laws, ensure_ascii=False, indent=2))
        
        # 법령 내용 조회 테스트
        if laws.get('LawSearch', {}).get('law'):
            law_id = laws['LawSearch']['law'][0]['법령ID']
            content = await client.get_law_content_async(law_id)
            print(f"\n법령 {law_id} 내용:")
            print(json.dumps(content, ensure_ascii=False, indent=2))
        
        # 통계 출력
        print(f"\nAPI 사용 통계: {client.get_stats()}")
    
    # 비동기 테스트 실행
    asyncio.run(test_mock_api())
