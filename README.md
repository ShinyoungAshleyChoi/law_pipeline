# 법제처 API 데이터 파이프라인

법제처에서 제공하는 API를 통해 법령 및 법령 조항을 관리하는 데이터 파이프라인입니다.

## 주요 기능

- 법제처 API를 통한 법령 데이터 수집
- MySQL 데이터베이스를 활용한 데이터 저장 및 관리
- 법령-조항 간의 관계 매핑 및 버전 관리
- Airflow를 통한 배치 작업 스케줄링
- 슬랙 기반 실시간 알림 시스템

## 기술 스택

- **언어**: Python 3.9+
- **데이터베이스**: MySQL 8.0+
- **워크플로우**: Apache Airflow
- **의존성 관리**: uv

## 프로젝트 구조

```
legal-data-pipeline/
├── src/
│   └── legal_data_pipeline/
│       ├── collectors/          # API 데이터 수집
│       ├── processors/          # 데이터 처리 및 변환
│       ├── database/           # 데이터베이스 연동
│       ├── notifications/      # 알림 시스템
│       └── airflow/           # Airflow DAG
├── config/                    # 설정 파일
├── scripts/                   # 실행 스크립트
├── tests/                     # 테스트 코드
└── docker/                    # Docker 설정
```

## 설치 및 실행

### 1. 프로젝트 클론 및 의존성 설치

```bash
git clone <repository-url>
cd legal-data-pipeline

# uv를 사용한 의존성 설치
uv sync
```

### 2. 환경 설정

```bash
# 환경 변수 파일 생성
cp .env.example .env

# 환경 변수 수정
vim .env
```

### 3. 데이터베이스 설정

```bash
# MySQL 데이터베이스 생성 및 스키마 설정
uv run python scripts/create_database.py
```

### 4. 배치 작업 실행

```bash
# 전체 데이터 동기화
uv run python scripts/run_batch_job.py --type full

# 증분 업데이트
uv run python scripts/run_batch_job.py --type incremental
```

## 개발

### 테스트 실행

```bash
# 전체 테스트 실행
uv run pytest

# 커버리지 포함 테스트
uv run pytest --cov=src/legal_data_pipeline
```

### 코드 포맷팅

```bash
# 코드 포맷팅
uv run black src/ tests/

# 린팅
uv run flake8 src/ tests/
```

## API 엔드포인트

이 파이프라인은 법제처의 다음 API를 사용합니다:

1. **현행법령 목록 조회**: 법령 기본 정보 수집
2. **현행법령 본문 조회**: 법령 전문 수집  
3. **현행법령 본문 조항호목 조회**: 조항 상세 정보 수집

## 라이선스

MIT License