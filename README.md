# 법제처 API 데이터 파이프라인 🏛️

> Kafka 기반 무중단 데이터 파이프라인으로 법제처 API에서 법령 및 조항 데이터를 수집하고 관리하는 시스템

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Kafka](https://img.shields.io/badge/Apache_Kafka-2.8+-orange.svg)](https://kafka.apache.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-blue.svg)](https://mysql.com)
[![Docker](https://img.shields.io/badge/Docker-20.10+-blue.svg)](https://docker.com)
[![uv](https://img.shields.io/badge/uv-package_manager-green.svg)](https://github.com/astral-sh/uv)

## 🎯 프로젝트 개요

이 프로젝트는 법제처에서 제공하는 Open API를 통해 법령 및 조항 데이터를 수집하고, Kafka를 활용한 무중단 데이터 파이프라인으로 MySQL 데이터베이스에 저장하는 시스템입니다.

### ✨ 주요 특징

- **무중단 서비스**: Kafka + Blue-Green 배포를 통한 서비스 중단 없는 데이터 업데이트
- **높은 신뢰성**: 메시지 영속성, 재처리 가능, 오류 복구 메커니즘
- **확장성**: 마이크로서비스 아키텍처와 수평 확장 가능한 구조
- **모니터링**: Prometheus + Grafana 기반 실시간 모니터링
- **알림 시스템**: Slack 기반 실시간 알림 및 오류 추적

## 🏗️ 시스템 아키텍처

```mermaid
graph TB
    subgraph "External"
        API[법제처 API]
    end
    
    subgraph "Data Pipeline"
        Producer[Producer<br/>API Fetcher]
        Kafka[Kafka Cluster<br/>3 Brokers]
        Consumer[Consumer<br/>DB Writer]
    end
    
    subgraph "Storage Layer"
        Blue[(MySQL Blue)]
        Green[(MySQL Green)]
        Redis[(Redis Cache)]
    end
    
    subgraph "Application Layer"
        APIServer[API Server]
        Airflow[Airflow<br/>Scheduler]
    end
    
    subgraph "Monitoring"
        Prometheus[Prometheus]
        Grafana[Grafana]
        AlertManager[Alert Manager]
    end
    
    API --> Producer
    Producer --> Kafka
    Kafka --> Consumer
    Consumer --> Blue
    Consumer --> Green
    APIServer --> Blue
    APIServer --> Green
    APIServer --> Redis
    Airflow --> Producer
    
    Consumer --> Prometheus
    Producer --> Prometheus
    Prometheus --> Grafana
    Prometheus --> AlertManager
```

## 🚀 빠른 시작

### 사전 요구사항

- **Docker & Docker Compose**: 20.10+
- **Python**: 3.12+
- **uv**: [설치 가이드](https://github.com/astral-sh/uv)
- **Make**: 빌드 도구

### 1. 저장소 클론

```bash
git clone <repository-url>
cd legal-data-pipeline
```

### 2. 전체 환경 설정 (원클릭 설치)

```bash
make setup
```

이 명령어는 다음을 자동으로 실행합니다:
- 의존성 설치 (`make dev`)
- 인프라 시작 (`make up`) 
- Kafka 토픽 생성 (`make topics-setup`)

### 3. 데이터 초기화 및 Kafka 파이프라인 테스트

```bash
# 기본 데이터베이스 초기화
make db-init

# Kafka Producer 실행 (데이터 수집 및 전송)
make producer-run

# 새 터미널에서 Consumer 실행 (메시지 처리)
make consumer-run

# End-to-End 테스트
make kafka-e2e-test
```

### 4. 서비스 접속

```bash
make monitor
```

- 🔗 **Kafka UI**: http://localhost:8080
- 📊 **Grafana**: http://localhost:3000 (admin/legal_grafana_2024!)
- 📈 **Prometheus**: http://localhost:9090
- 🔄 **Schema Registry**: http://localhost:8081

## 📋 주요 명령어

### 인프라 관리

```bash
# 인프라 시작
make up                    # 일반 시작
make up-clean             # 볼륨 초기화하고 시작

# 인프라 중지
make down                 # 컨테이너 중지
make down-volumes        # 볼륨까지 제거

# 상태 확인
make status              # 서비스 상태
make logs               # 전체 로그
make logs-kafka         # Kafka 로그만
```

### 개발 및 테스트

```bash
# 개발 환경 구성
make dev                # 의존성 설치 + pre-commit
make install           # 의존성만 설치

# 코드 품질
make test              # 테스트 실행
make test-cov         # 커버리지 테스트
make lint             # 린팅
make format           # 코드 포맷팅

# Kafka Producer/Consumer
make producer-run      # Producer 실행 (데이터 수집)
make consumer-run      # Consumer 실행 (메시지 처리)
make producer-health   # Producer 헬스체크
make consumer-health   # Consumer 헬스체크
make kafka-e2e-test   # End-to-End 테스트

# 기존 배치 작업 (호환성 유지)
make db-init          # DB 초기화
make db-load          # Mock 데이터 적재
make batch-incremental # 증분 업데이트
```

### Kafka 관리

```bash
make topics            # 토픽 목록 조회
make topics-setup      # 토픽 생성
make topics-describe   # 토픽 상세 정보
```

## 🔧 설정

### 환경 변수

주요 환경 변수는 `.env` 파일에서 관리됩니다:

```bash
# 데이터베이스
ACTIVE_DB_ENV=blue                    # 현재 활성 DB (blue/green)
DB_USER=legal_user
DB_PASSWORD=legal_pass_2024!

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092,localhost:9093,localhost:9094

# API
LEGAL_API_BASE_URL=https://open.law.go.kr/LSO/openApi
LEGAL_API_TIMEOUT=30

# 알림
SLACK_BOT_TOKEN=xoxb-your-token       # 실제 토큰으로 교체 필요
SLACK_CHANNEL=#legal-data-alerts
```

### Kafka 토픽 구성

| 토픽명 | 파티션 | 복제 | 용도 |
|--------|--------|------|------|
| `legal-law-events` | 6 | 3 | 법령 이벤트 스트림 |
| `legal-content-events` | 4 | 3 | 법령 본문 이벤트 |
| `legal-article-events` | 8 | 3 | 조항 이벤트 |
| `legal-batch-status` | 1 | 3 | 배치 작업 상태 |
| `legal-cdc-*` | 3-4 | 3 | Change Data Capture |
| `legal-dlq` | 3 | 3 | Dead Letter Queue |

## 🔄 데이터 플로우

### 1. 데이터 수집 (Producer)

```python
API 호출 → 데이터 검증 → Kafka Topic 발송 → 배치 완료 알림
```

- 법제처 API에서 법령/조항 데이터 수집
- 데이터 검증 및 중복 제거
- Kafka 토픽으로 이벤트 발송

### 2. 데이터 처리 (Consumer)

```python
Topic 구독 → 데이터 변환 → 중복 제거 → 순서 보장 → DB 적재
```

- Kafka 메시지 구독 및 처리
- 데이터 변환 및 정규화
- Blue-Green DB에 적재

### 3. 무중단 배포 (Blue-Green)

```python
Current DB (Blue) → 신규 데이터 적재 중 → New DB (Green) → 트래픽 전환
```

- 현재 서비스는 Blue DB에서 계속 제공
- Green DB에 새로운 데이터 적재
- 검증 완료 후 트래픽 전환

## 📊 모니터링

### 주요 메트릭

- **Kafka**: Consumer Lag, 처리량, 파티션 상태
- **MySQL**: 연결 상태, 쿼리 성능, 복제 지연
- **Application**: 처리된 법령 수, 오류율, 응답 시간

### 알림 설정

- **성공**: 배치 작업 완료, 데이터 동기화 성공
- **경고**: Consumer Lag 증가, DB 연결 지연
- **오류**: API 호출 실패, 데이터 검증 오류, 시스템 장애

## 🧪 테스트

### 단위 테스트

```bash
make test                    # 기본 테스트
make test-cov               # 커버리지 포함
pytest -m "not integration" # 단위 테스트만
```

### 통합 테스트

```bash
make test-integration       # Kafka + MySQL 포함
pytest -m kafka            # Kafka 테스트만
pytest -m mysql           # MySQL 테스트만
```

### 성능 테스트

```bash
# Kafka 처리량 테스트
uv run python tests/performance/kafka_throughput.py

# DB 적재 성능 테스트  
uv run python tests/performance/db_load_test.py
```

## 🚀 배포

### 개발 환경

```bash
make setup        # 전체 환경 구성
make db-load      # Mock 데이터 적재
make test         # 테스트 실행
```

### 프로덕션 환경

```bash
# Docker 이미지 빌드
make build

# 프로덕션 배포 (구현 예정)
make deploy
```

## 🛠️ 개발 가이드

### 코드 스타일

- **포매터**: Black (88자 라인 길이)
- **Import 정렬**: isort
- **린터**: flake8, mypy
- **커밋 훅**: pre-commit

### 브랜치 전략

- `main`: 프로덕션 브랜치
- `develop`: 개발 브랜치  
- `feature/*`: 기능 브랜치
- `hotfix/*`: 핫픽스 브랜치

### 커밋 메시지

```
feat: Kafka 기반 Producer 구현
fix: MySQL 연결 오류 수정
docs: README 업데이트
test: Consumer 단위 테스트 추가
```

## 📁 프로젝트 구조

```
legal-data-pipeline/
├── src/                          # 소스 코드
│   ├── api/                     # 법제처 API 클라이언트
│   ├── kafka/                   # Kafka Producer/Consumer
│   ├── database/                # 데이터베이스 모델/저장소
│   ├── notifications/           # 알림 시스템
│   └── airflow/                # Airflow DAG
├── scripts/                     # 실행 스크립트
│   ├── start_infrastructure.sh  # 인프라 시작
│   ├── setup_kafka_topics.py   # Kafka 토픽 설정
│   └── full_data_load.py       # 데이터 적재
├── docker/                      # Docker 설정
│   ├── mysql/                  # MySQL 초기화 스크립트
│   ├── prometheus/             # Prometheus 설정
│   └── grafana/               # Grafana 대시보드
├── tests/                       # 테스트 코드
├── config/                      # 설정 파일
├── docker-compose.yml          # 인프라 정의
├── Makefile                    # 빌드 스크립트
└── pyproject.toml             # Python 프로젝트 설정
```

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 문의 및 지원

- 이슈: [GitHub Issues](https://github.com/your-org/legal-data-pipeline/issues)
- 문서: [Wiki](https://github.com/your-org/legal-data-pipeline/wiki)
- 슬랙: #legal-data-pipeline

---

**Made with ❤️ for legal data management**
