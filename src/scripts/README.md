# Scripts 디렉토리

법제처 데이터 파이프라인을 위한 유틸리티 스크립트들을 포함합니다.

## 📁 디렉토리 구조

```
src/scripts/
├── __init__.py                        # Python 패키지 초기화
├── README.md                          # 이 파일
├── logs/                              # 스크립트 실행 로그
│
├── deploy_bluegreen.sh               # 🔄 블루-그린 배포 스크립트
├── test_partition_optimization.py    # 🧪 Kafka 파티션 최적화 테스트
├── run_mock_airflow_dag.py           # 🚀 Mock 환경 Airflow DAG 실행기
│
├── setup_kafka_topics.py             # ⚙️ Kafka 토픽 설정
├── setup_mock_environment.py         # 🎭 Mock 환경 설정
├── start_infrastructure.sh           # 🏗️ 인프라 시작 스크립트
└── stop_infrastructure.sh            # 🛑 인프라 중지 스크립트
```

## 🔧 주요 스크립트

### 1. 블루-그린 배포 (`deploy_bluegreen.sh`)

무중단 배포를 위한 블루-그린 배포 스크립트입니다.

```bash
# 기본 배포
.src/scripts/deploy_bluegreen.sh deploy

# 특정 버전 배포
.src/scripts/deploy_bluegreen.sh deploy v1.2.0

# 롤백
.src/scripts/deploy_bluegreen.sh rollback

# 상태 확인
.src/scripts/deploy_bluegreen.sh status

# 도움말
.src/scripts/deploy_bluegreen.sh help
```

**주요 기능:**
- 무중단 배포 (Zero-downtime deployment)
- 자동 롤백 지원
- 헬스 체크 및 상태 모니터링
- MySQL Blue/Green 환경 관리
- Load balancer 자동 전환

### 2. Kafka 파티션 최적화 테스트 (`test_partition_optimization.py`)

Kafka 파티션 전략의 효과를 시뮬레이션하고 검증하는 스크립트입니다.

```bash
# 파티션 최적화 테스트 실행
uv run python src/scripts/test_partition_optimization.py

# 또는 직접 실행
python src/scripts/test_partition_optimization.py
```

**테스트 항목:**
- 기존 vs 최적화된 파티션 전략 비교
- Hot Partition 시나리오 테스트
- 분산 점수 및 성능 지표 계산
- 부처별 데이터 분포 시뮬레이션

**출력 파일:**
- `partition_optimization_results.json`: 상세 테스트 결과

### 3. Mock 환경 Airflow DAG 실행기 (`run_mock_airflow_dag.py`)

Mock 데이터를 사용하여 Airflow DAG를 테스트하는 스크립트입니다.

```bash
# Airflow 초기화
uv run python src/scripts/run_mock_airflow_dag.py --action init

# DAG 목록 조회
uv run python src/scripts/run_mock_airflow_dag.py --action list

# 특정 DAG 실행
uv run python src/scripts/run_mock_airflow_dag.py --action trigger --dag-id kafka_legal_data_pipeline

# DAG 테스트
uv run python src/scripts/run_mock_airflow_dag.py --action test --dag-id kafka_legal_data_pipeline

# 특정 태스크 테스트
uv run python src/scripts/run_mock_airflow_dag.py --action test --dag-id kafka_legal_data_pipeline --task-id kafka_produce_legal_data

# 백필 실행
uv run python src/scripts/run_mock_airflow_dag.py --action backfill --dag-id kafka_legal_data_pipeline --start-date 2024-01-01 --end-date 2024-01-07

# 상태 조회
uv run python src/scripts/run_mock_airflow_dag.py --action status --dag-id kafka_legal_data_pipeline
```

**주요 기능:**
- Mock 환경에서 Airflow DAG 실행 및 테스트
- 개발/테스트/데모 환경 지원
- DAG 및 태스크별 개별 테스트
- 백필 및 상태 모니터링
- 실제 API 호출 없이 파이프라인 검증

**환경 옵션:**
- `development`: 개발 환경 (기본값)
- `testing`: 테스트 환경
- `demo`: 데모 환경

### 4. 인프라 관리 스크립트

#### 시작 (`start_infrastructure.sh`)
```bash
# 기본 인프라 시작
./src/scripts/start_infrastructure.sh

# 토픽 설정 건너뛰기
./src/scripts/start_infrastructure.sh --skip-setup

# 볼륨 정리하고 시작
./src/scripts/start_infrastructure.sh --clean-volumes
```

#### 중지 (`stop_infrastructure.sh`)
```bash
# 인프라 중지
./src/scripts/stop_infrastructure.sh

# 볼륨까지 삭제
./src/scripts/stop_infrastructure.sh --remove-volumes
```

### 5. 설정 및 유틸리티

#### Kafka 토픽 설정 (`setup_kafka_topics.py`)
```bash
# Kafka 토픽 설정
uv run python src/scripts/setup_kafka_topics.py
```

#### Mock 환경 설정 (`setup_mock_environment.py`)
```bash
# Mock 환경 설정
uv run python src/scripts/setup_mock_environment.py --environment development
```

## 🚀 빠른 시작 가이드

### 1. Mock 환경에서 파이프라인 테스트

```bash
# 1. 인프라 시작
./src/scripts/start_infrastructure.sh

# 2. Airflow 환경 초기화
uv run python src/scripts/run_mock_airflow_dag.py --action init --environment development

# 3. DAG 목록 확인
uv run python src/scripts/run_mock_airflow_dag.py --action list

# 4. DAG 테스트 실행
uv run python src/scripts/run_mock_airflow_dag.py --action test --dag-id kafka_legal_data_pipeline

# 5. 인프라 중지
./src/scripts/stop_infrastructure.sh
```

### 2. 블루-그린 배포 테스트

```bash
# 1. 배포 실행
./src/scripts/deploy_bluegreen.sh deploy

# 2. 상태 확인
./src/scripts/deploy_bluegreen.sh status

# 3. 문제 발생 시 롤백
./src/scripts/deploy_bluegreen.sh rollback
```

### 3. Kafka 파티션 최적화 검증

```bash
# 파티션 최적화 효과 분석
uv run python src/scripts/test_partition_optimization.py

# 결과 확인
cat partition_optimization_results.json
```

## 📊 로그 및 모니터링

### 로그 파일 위치
- `src/scripts/logs/`: 스크립트 실행 로그
- `logs/`: 애플리케이션 로그
- `.airflow/logs/`: Airflow 실행 로그

### 모니터링 대상
- **Airflow DAG 실행 상태**: Task 성공/실패, 실행 시간
- **Kafka 파티션 분산**: 메시지 분포, Hot Partition 감지
- **배포 상태**: Blue/Green 환경 상태, 롤백 필요성
- **Mock 데이터 품질**: 생성된 데이터의 일관성 및 정확성

## 🛠️ 개발자를 위한 팁

### Mock 환경 디버깅
```bash
# 상세 로그와 함께 실행
PYTHONPATH=. python src/scripts/run_mock_airflow_dag.py --action test --dag-id kafka_legal_data_pipeline

# Mock 데이터 생성 확인
uv run python -c "from mock.mock_config import setup_mock_environment; env = setup_mock_environment('development'); print(env.get_statistics())"
```

### 파티션 전략 커스터마이징
```python
# src/scripts/test_partition_optimization.py에서
# OptimizedPartitionStrategy 클래스를 수정하여
# 새로운 파티셔닝 전략을 테스트할 수 있습니다.
```

### 배포 스크립트 커스터마이징
```bash
# deployment/ 폴더의 Python 스크립트를 수정하여
# 배포 로직을 커스터마이징할 수 있습니다.
./src/scripts/deploy_bluegreen.sh deploy --version custom-build
```
