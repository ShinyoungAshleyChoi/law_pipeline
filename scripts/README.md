# Scripts 디렉토리

법제처 데이터 파이프라인의 실행 스크립트들이 포함된 디렉토리입니다.

## 📁 스크립트 목록

### 🏗️ 인프라 관리

#### `start_infrastructure.sh`
- **용도**: 전체 인프라 시작 (Docker Compose 기반)
- **설명**: Zookeeper, Kafka 클러스터, MySQL Blue-Green, Redis, Airflow, 모니터링 시스템을 순차적으로 시작
- **사용법**:
  ```bash
  # 기본 실행
  ./scripts/start_infrastructure.sh
  
  # 볼륨 초기화 후 실행
  ./scripts/start_infrastructure.sh --clean-volumes
  
  # 토픽 설정 건너뛰기
  ./scripts/start_infrastructure.sh --skip-setup
  ```

### 🔄 배치 작업 관리

#### `batch_monitor.py`
- **용도**: 배치 작업 통합 관리 도구
- **설명**: 전체 데이터 적재, 증분 업데이트, 데이터 검증 작업을 관리하고 모니터링
- **사용법**:
  ```bash
  # 전체 데이터 적재
  uv run python scripts/batch_monitor.py run full_load --use-api --batch-size 100
  
  # 증분 업데이트
  uv run python scripts/batch_monitor.py run incremental_update --use-api
  
  # 데이터 검증
  uv run python scripts/batch_monitor.py run validation --fix
  
  # 실행 중인 작업 모니터링
  uv run python scripts/batch_monitor.py monitor
  
  # 작업 이력 조회
  uv run python scripts/batch_monitor.py history --days 7
  
  # 실패한 작업 조회
  uv run python scripts/batch_monitor.py failed --days 3
  
  # 시스템 상태 조회
  uv run python scripts/batch_monitor.py status
  ```

#### `full_data_load.py`
- **용도**: 전체 초기 데이터 적재 (독립 실행 가능)
- **설명**: 법제처 API에서 전체 법령 데이터를 적재
- **사용법**:
  ```bash
  # Mock 데이터로 테스트
  uv run python scripts/full_data_load.py --batch-size 50
  
  # 실제 API 사용
  uv run python scripts/full_data_load.py --use-api --batch-size 100 --verbose
  ```

#### `incremental_update.py`
- **용도**: 증분 업데이트 (독립 실행 가능)
- **설명**: 마지막 동기화 이후 변경된 데이터만 업데이트
- **사용법**:
  ```bash
  # 기본 증분 업데이트
  uv run python scripts/incremental_update.py
  
  # 특정 날짜 기준 업데이트
  uv run python scripts/incremental_update.py --target-date 2024-12-31 --use-api
  ```

### ✈️ Airflow 관리 (Docker 연동)

#### `run_airflow_dag.py`
- **용도**: Docker Compose로 실행된 Airflow DAG 관리
- **설명**: DAG 실행, 상태 조회, 시스템 헬스체크 등 Airflow 작업 관리
- **특징**: 
  - Docker Airflow와 HTTP API 연동
  - DAG가 없으면 자동 생성
  - Airflow UI 연동 (`http://localhost:8090`)
- **사용법**:
  ```bash
  # 증분 업데이트 DAG 실행
  uv run python scripts/run_airflow_dag.py incremental --date 2024-12-31 --force
  
  # DAG 상태 조회
  uv run python scripts/run_airflow_dag.py status --dag-id legal_data_pipeline
  
  # 최근 실행 목록
  uv run python scripts/run_airflow_dag.py list --limit 5
  
  # 시스템 상태 확인
  uv run python scripts/run_airflow_dag.py health
  
  # 수동 DAG 트리거
  uv run python scripts/run_airflow_dag.py trigger --dag-id legal_data_pipeline
  ```

### 🔧 설정 관리

#### `setup_kafka_topics.py`
- **용도**: Kafka 토픽 관리
- **사용법**:
  ```bash
  # 토픽 생성
  uv run python scripts/setup_kafka_topics.py --action setup
  
  # 토픽 목록 조회
  uv run python scripts/setup_kafka_topics.py --action list
  
  # 토픽 삭제
  uv run python scripts/setup_kafka_topics.py --action delete
  ```

## 🚀 빠른 시작 가이드

### 1. 인프라 시작
```bash
# 전체 인프라 시작 (볼륨 초기화)
make up-clean

# 또는 스크립트 직접 실행
./scripts/start_infrastructure.sh --clean-volumes
```

### 2. 서비스 접속 정보 확인
```bash
# 인프라 시작 완료 후 다음 서비스들이 제공됩니다:
✈️  Airflow UI:      http://localhost:8090 (airflow/airflow_admin_2024!)
🔗 Kafka UI:        http://localhost:8080
📊 Grafana:         http://localhost:3000 (admin/legal_grafana_2024!)
📈 Prometheus:      http://localhost:9090
🔄 Schema Registry: http://localhost:8081
🌸 Flower (Celery): http://localhost:5555
```

### 3. 데이터 적재
```bash
# Mock 데이터로 테스트
uv run python scripts/batch_monitor.py run full_load

# 실제 API 사용 (권장)
uv run python scripts/batch_monitor.py run full_load --use-api
```

### 4. Airflow DAG 실행
```bash
# 증분 업데이트 DAG 실행
uv run python scripts/run_airflow_dag.py incremental

# Airflow UI에서 확인: http://localhost:8090
```

### 5. 모니터링
```bash
# 시스템 상태 확인
uv run python scripts/batch_monitor.py status

# 실행 중인 작업 모니터링
uv run python scripts/batch_monitor.py monitor

# Airflow DAG 상태 확인
uv run python scripts/run_airflow_dag.py status
```

## 📊 데이터베이스 연결 정보

- **MySQL Blue**: `localhost:3306` (legal_user/legal_pass_2024!)
- **MySQL Green**: `localhost:3307` (legal_user/legal_pass_2024!) [기본 사용]
- **PostgreSQL (Airflow)**: `localhost:5432` (airflow/airflow_pass_2024!)
- **Redis**: `localhost:6379` (legal_redis_2024!)

## 🔧 환경 변수

주요 설정은 `.env` 파일에서 관리됩니다:
- `ACTIVE_DB_ENV`: 활성 DB 환경 (blue/green)
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka 브로커 주소
- `LEGAL_API_BASE_URL`: 법제처 API URL
- `BATCH_SIZE`: 기본 배치 크기

## ⚠️ 주의사항

1. **Docker 요구사항**: Docker와 Docker Compose가 설치되어 있어야 합니다
2. **포트 충돌**: 8080, 8090, 3000, 3306, 3307, 5432, 6379 포트가 사용됩니다
3. **메모리**: Airflow와 Kafka 클러스터를 위해 최소 8GB RAM 권장
4. **uv 사용**: Python 패키지 관리를 위해 `uv` 사용을 권장합니다

## 🐛 문제 해결

### 서비스가 시작되지 않는 경우
```bash
# 컨테이너 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f [서비스명]

# 전체 재시작
make down && make up-clean
```

### Airflow 연결 문제
```bash
# Airflow 웹서버 상태 확인
curl -f http://localhost:8090/health

# DAG 자동 생성 확인
uv run python scripts/run_airflow_dag.py status
```

### 데이터베이스 연결 문제
```bash
# MySQL 연결 테스트
mysql -h localhost -P 3307 -u legal_user -p

# 시스템 상태 확인
uv run python scripts/batch_monitor.py status
```

## 📝 로그 위치

- **Application 로그**: `logs/legal_pipeline.log`
- **Docker 로그**: `docker-compose logs -f [서비스명]`
- **Airflow 로그**: `src/airflow/logs/`

## 🔄 업데이트

스크립트를 업데이트한 후에는:
```bash
# 인프라 재시작
make down && make up

# DAG 파일 새로고침 (필요시)
rm -rf src/airflow/dags/*.py
uv run python scripts/run_airflow_dag.py status
```
