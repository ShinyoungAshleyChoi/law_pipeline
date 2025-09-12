# Mock 환경 가이드

법제처 과제 프로젝트의 개발환경에서 Mock 데이터를 활용하여 실제 API 호출 없이도 전체 파이프라인을 테스트할 수 있습니다.

## 🎭 Mock 환경 개요

Mock 환경은 다음 구성 요소들을 시뮬레이션합니다:
- **Mock API 클라이언트**: 법제처 Open API를 시뮬레이션
- **Mock 데이터베이스**: SQLite 기반의 경량 DB
- **Mock 데이터 생성기**: 실제와 유사한 법률 문서 데이터 생성

## 🚀 빠른 시작

### 1. Mock 환경 설정

```bash
# 개발용 Mock 환경 설정 (기본)
make mock-setup

# 테스트용 Mock 환경 설정
make mock-setup-test

# 데모용 Mock 환경 설정  
make mock-setup-demo
```

### 2. Mock 데이터 생성

```bash
# 기본 50개 Mock 데이터 생성
make mock-data

# 특정 개수 Mock 데이터 생성 (예: 100개)
echo "100" | make mock-data
```

### 3. Mock 환경 테스트

```bash
# 모든 Mock 테스트 실행
make mock-test-all

# API 테스트만 실행
make mock-test-api

# 데이터베이스 테스트만 실행
make mock-test-db
```

### 4. Mock 환경으로 파이프라인 실행

```bash
# 전체 파이프라인 실행
make mock-run

# 문서 검색
make mock-run-search

# 통계 조회
make mock-run-stats
```

## ⚙️ 환경 설정

### 환경 변수

`.env` 파일을 통해 Mock 환경을 설정할 수 있습니다:

```bash
# Mock 환경 활성화
USE_MOCK_DATA=true
USE_MOCK_API=true
USE_MOCK_DB=true

# 환경 타입 (development, testing, demo)
MOCK_ENVIRONMENT=development

# Mock 데이터 설정
MOCK_DATA_COUNT=50
MOCK_API_DELAY=true
MOCK_API_ERROR_RATE=0.02

# Mock 데이터베이스
MOCK_DB_PATH=sample_data/mock_legal.db
```

### 설정 파일

`config/mock.yaml` 파일에서 상세 설정이 가능합니다:

```yaml
mock_environment:
  enabled: true
  environment_type: development
  
  data:
    initial_count: 50
    auto_regenerate: false
    
  api:
    enabled: true
    enable_delay: true
    error_rate: 0.02
    
  database:
    enabled: true
    type: "memory"  # 또는 "sqlite"
    auto_populate: true
```

## 🎯 환경 타입별 특성

### Development 환경
- API 지연 없음 (빠른 개발)
- 낮은 에러율 (1%)
- 메모리 DB 사용
- 상세한 디버그 로그

```bash
make mock-setup  # development가 기본값
```

### Testing 환경  
- API 지연 없음 (빠른 테스트)
- 약간 높은 에러율 (5%) - 에러 상황 테스트
- 메모리 DB 사용
- 경고 레벨 로그

```bash
make mock-setup-test
```

### Demo 환경
- 실제와 유사한 API 지연
- 적당한 에러율 (2%)
- 영구 SQLite DB 사용
- 표준 로그 레벨

```bash
make mock-setup-demo
```

## 📊 Mock 데이터 구조

### 법률 문서 데이터

```json
{
  "id": "LAW-2024-001",
  "title": "개인정보보호법 기본법 제정안",
  "content": "제1조(목적) 이 법은 개인정보보호에 관한...",
  "doc_type": "법률",
  "category": "정보보호", 
  "source": "국회 법제사법위원회",
  "published_date": "2024-03-15T09:00:00Z",
  "status": "active",
  "tags": ["개인정보", "프라이버시", "데이터보호"],
  "metadata": {
    "bill_number": "2024001",
    "proposer": "김민수 의원 외 20인",
    "committee": "법제사법위원회",
    "language": "ko"
  }
}
```

### API 응답 형식

Mock API는 실제 법제처 OpenAPI와 호환되는 응답을 생성합니다:

```json
{
  "LawSearch": {
    "law": [...],
    "totalCnt": 50,
    "display": 10,
    "start": 1
  }
}
```

## 🧪 테스트 및 검증

### API 기능 테스트

```bash
# 개별 API 기능 테스트
python scripts/test_mock_api.py
```

**테스트 항목:**
- 법령 목록 조회 (동기/비동기)
- 법령 내용 조회
- 법령 조문 조회  
- 배치 조회
- 검색 기능
- 에러 시뮬레이션

### 데이터베이스 테스트

```bash
# DB 기능 테스트
python scripts/test_mock_database.py
```

**테스트 항목:**
- CRUD 작업
- 검색 및 필터링
- Repository 패턴
- 대량 데이터 처리
- 통계 조회

### 통합 테스트

```bash
# 전체 파이프라인 통합 테스트
python src/main_with_mock.py --mode full
```

## 🛠️ 고급 사용법

### 커스텀 Mock 데이터 생성

```python
from src.mock.data_generator import MockDataGenerator

# 데이터 생성기 초기화
generator = MockDataGenerator()

# 특정 주제의 문서 생성
doc = generator.generate_legal_document("CUSTOM-2024-001")

# 여러 문서 생성
docs = generator.generate_multiple_documents(10)

# 파일로 저장
generator.save_mock_data(docs, "custom_data.json")
```

### Mock 환경 프로그래밍 방식 제어

```python
from src.mock.mock_config import get_mock_environment, TemporaryMockEnvironment

# 전역 Mock 환경 사용
mock_env = get_mock_environment()
api_client = mock_env.get_api_client()
db_connection = mock_env.get_db_connection()

# 임시 Mock 환경 (컨텍스트 매니저)
with TemporaryMockEnvironment(mock_data_count=10, enable_api_delay=False) as temp_env:
    # 임시 환경에서 작업
    temp_api = temp_env.get_api_client()
    response = temp_api.get_law_list({'display': 5})
```

### Mock API 클라이언트 커스터마이징

```python
from src.mock.api_mock import create_mock_api_client

# 에러율과 지연을 조정한 클라이언트 생성
client = create_mock_api_client(
    enable_delay=False,      # 지연 없음
    error_rate=0.1           # 10% 에러율
)

# 사용법은 실제 API 클라이언트와 동일
laws = await client.get_law_list_async({'display': 5})
```

## 📁 Mock 데이터 파일 구조

```
sample_data/
├── legal_documents.json          # 기본 Mock 데이터
├── mock_legal_documents_50.json  # 생성된 Mock 데이터
├── mock_legal.db                 # SQLite Mock DB (데모용)
└── test_data_10.json            # 테스트용 추가 데이터
```

## 🔧 트러블슈팅

### 일반적인 문제들

**1. Mock 데이터가 생성되지 않는 경우**
```bash
# Mock 환경 강제 재설정
make mock-reset

# 권한 문제 확인
ls -la sample_data/
```

**2. API 응답이 너무 느린 경우**
```bash
# 개발 환경으로 전환 (지연 없음)
export MOCK_API_DELAY=false
make mock-setup
```

**3. 데이터베이스 연결 오류**
```bash
# 메모리 DB로 전환
export MOCK_DB_PATH=":memory:"
make mock-setup
```

### 로그 확인

Mock 환경의 상세 로그 확인:

```bash
# Mock 환경 상태 확인
make mock-status

# 로그 파일 확인 (설정된 경우)
tail -f logs/mock_environment.log
```

## 📈 성능 및 제한사항

### 성능 특성
- **메모리 DB**: 매우 빠름, 재시작시 데이터 소실
- **SQLite DB**: 적당한 속도, 영구 저장
- **Mock API**: 실제 네트워크 지연 없음

### 제한사항
- Mock 데이터는 실제 법령과 다를 수 있음
- 복잡한 법률 관계나 참조는 시뮬레이션되지 않음
- 대용량 데이터 처리시 메모리 사용량 증가

## 🚀 프로덕션 전환

Mock 환경에서 실제 환경으로 전환:

```bash
# 환경 변수 변경
export USE_MOCK_DATA=false
export USE_MOCK_API=false  
export USE_MOCK_DB=false

# 실제 API 키 설정
export LEGAL_API_KEY=your-actual-api-key

# 실제 DB 연결 정보 설정
export DB_HOST=your-db-host
export DB_USER=your-db-user
export DB_PASSWORD=your-db-password
```

## 🤝 기여 가이드

Mock 환경 개선에 기여하고 싶다면:

1. **새로운 Mock 데이터 타입 추가**
   - `src/mock/data_generator.py` 수정
   - 새로운 문서 타입이나 카테고리 추가

2. **API 응답 개선**
   - `src/mock/api_mock.py` 수정
   - 실제 API와의 호환성 향상

3. **테스트 케이스 추가**
   - `scripts/test_mock_*.py` 파일들에 테스트 추가

4. **문서 업데이트**
   - 새로운 기능이나 변경사항 문서화

---

더 자세한 내용은 프로젝트의 다른 문서들을 참고하세요:
- [README.md](../README.md) - 전체 프로젝트 개요
- [API 문서](./API.md) - API 사용법
- [데이터베이스 스키마](./DATABASE.md) - DB 구조
