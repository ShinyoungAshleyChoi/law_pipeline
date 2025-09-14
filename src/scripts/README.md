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

### 0. ⚡ Kafka 파이프라인 직접 실행기 (`run_kafka_dag.py`) **NEW!**

Airflow 없이 Kafka 파이프라인 DAG를 직접 실행할 수 있는 스크립트입니다. MOCK 데이터를 사용하여 실제 Producer/Consumer 워크플로우를 테스트할 수 있습니다.

```bash
# 전체 파이프라인 실행 (기본 파라미터)
uv run python src/scripts/run_kafka_dag.py --action full

# 커스텀 파라미터로 전체 파이프라인 실행
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 50 --timeout 600 --batch-size 40

# 특정 태스크만 실행
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_produce_mock_data
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_consume_and_store

# 실패 시뮬레이션과 함께 실행
uv run python src/scripts/run_kafka_dag.py --action full --simulate-failure --no-notification

# 사용 가능한 태스크 목록 조회
uv run python src/scripts/run_kafka_dag.py --action list

# 테스트 환경에서 실행
uv run python src/scripts/run_kafka_dag.py --action full --environment testing
```

**주요 기능:**
- **완전한 Kafka 워크플로우**: Producer → Consumer → DB 저장 → 알림 전송
- **MOCK 데이터 사용**: MockDataGenerator로 현실적인 법령 데이터 생성
- **실제 Kafka 스트리밍**: 진짜 Kafka Producer/Consumer 사용
- **상세한 통계 및 모니터링**: 실행 시간, 성공률, 처리량 등 상세 메트릭
- **유연한 실행 옵션**: 전체 파이프라인 또는 개별 태스크 실행
- **실패 시뮬레이션**: Producer/Consumer 오류 상황 테스트

**실행 옵션:**
- `--mock-count`: 생성할 MOCK 법령 데이터 수 (기본값: 25)
- `--timeout`: Consumer 타임아웃 초 (기본값: 300)
- `--batch-size`: 배치 크기 (기본값: 30)
- `--simulate-failure`: Producer 실패 시뮬레이션 활성화
- `--no-notification`: 슬랙 알림 비활성화

**실행 결과 예시:**
```
🚀 Kafka 기반 법제처 데이터 파이프라인 전체 실행 시작
   시작 시간: 2025-01-14 15:30:25

🔍 1. Kafka 헬스 체크 실행 중...
✅ Kafka 헬스 체크 완료 (2.1초)
   상태: healthy

📤 2. Kafka Producer (MOCK 데이터) 실행 중...
✅ Producer 완료 (12.3초)
   전송 성공: 25개
   전송 실패: 0개
   총 생성: 25개

📥 3. Kafka Consumer & DB 저장 실행 중...
✅ Consumer 완료 (8.7초)
   수신 메시지: 25개
   저장 성공: 25개
   저장 실패: 0개

📢 4. 완료 알림 전송 실행 중...
✅ 알림 전송 완료 (1.2초)

============================================================
📊 Kafka 파이프라인 실행 결과 요약
============================================================
시작 시간: 2025-01-14 15:30:25
종료 시간: 2025-01-14 15:30:49
실행 시간: 24.3초
완료 태스크: 4/4개
✅ 전체 상태: 성공

📤 Producer 통계:
   생성된 MOCK 데이터: 25개
   Kafka 전송 성공: 25개
   Kafka 전송 실패: 0개

📥 Consumer 통계:
   Kafka 메시지 수신: 25개
   데이터베이스 저장: 25개
   저장 실패: 0개

🎯 전체 성공률: 100.0% (25/25)
============================================================

🎉 전체 파이프라인 실행 성공!
```

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

### 0. ⚡ 새로운 Kafka 파이프라인 바로 실행하기 (권장)

가장 빠르고 쉬운 방법입니다!

```bash
# 1. 인프라 시작 (Docker Compose)
./src/scripts/start_infrastructure.sh

# 2. Kafka 파이프라인 전체 실행 (MOCK 데이터 사용)
uv run python src/scripts/run_kafka_dag.py --action full

# 3. 더 많은 데이터로 테스트
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 100 --timeout 600

# 4. 개별 태스크 테스트
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_produce_mock_data

# 5. 인프라 중지
./src/scripts/stop_infrastructure.sh
```

**이 방법의 장점:**
- ✅ Airflow 설치/설정 불필요
- ✅ 즉시 실행 가능
- ✅ 상세한 실행 결과 확인
- ✅ 실제 Kafka Producer/Consumer 사용
- ✅ 완전한 워크플로우 테스트

### 1. Mock 환경에서 파이프라인 테스트 (Airflow 사용)

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

## 📋 스크립트별 상세 사용법

### ⚡ Kafka 파이프라인 직접 실행기 상세 가이드

#### 기본 사용법
```bash
# 기본 실행 (25개 MOCK 데이터, 5분 타임아웃)
uv run python src/scripts/run_kafka_dag.py --action full

# 도움말 확인
uv run python src/scripts/run_kafka_dag.py --help
```

#### 고급 사용법
```bash
# 대용량 데이터 테스트 (100개 데이터, 10분 타임아웃)
uv run python src/scripts/run_kafka_dag.py \
  --action full \
  --mock-count 100 \
  --timeout 600 \
  --batch-size 50

# 실패 시나리오 테스트
uv run python src/scripts/run_kafka_dag.py \
  --action full \
  --simulate-failure \
  --mock-count 30

# 프로덕션 환경 시뮬레이션 (알림 포함)
uv run python src/scripts/run_kafka_dag.py \
  --action full \
  --environment production \
  --mock-count 200 \
  --timeout 900

# Consumer만 별도 테스트 (Producer가 이미 실행된 경우)
uv run python src/scripts/run_kafka_dag.py \
  --action task \
  --task-name kafka_consume_and_store \
  --timeout 300
```

#### 태스크별 실행
```bash
# 1. Kafka 헬스 체크만
uv run python src/scripts/run_kafka_dag.py --action task --task-name check_kafka_health

# 2. Producer만 (데이터 생성 및 전송)
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_produce_mock_data --mock-count 50

# 3. Consumer만 (메시지 수신 및 저장) 
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_consume_and_store

# 4. 알림만 (이전 태스크 결과 필요)
uv run python src/scripts/run_kafka_dag.py --action task --task-name send_completion_notification
```

#### 디버깅 및 문제 해결
```bash
# 상세 로그와 함께 실행
PYTHONPATH=src python src/scripts/run_kafka_dag.py --action full --mock-count 10

# 특정 환경에서 실행
uv run python src/scripts/run_kafka_dag.py --action full --environment testing

# 알림 없이 실행 (빠른 테스트용)
uv run python src/scripts/run_kafka_dag.py --action full --no-notification --mock-count 10
```

#### 성능 테스트
```bash
# 소규모 테스트 (빠른 검증)
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 10 --timeout 60

# 중간 규모 테스트 (일반적인 배치)
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 50 --timeout 300

# 대규모 테스트 (부하 테스트)
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 500 --timeout 1800

# 초대규모 테스트 (스트레스 테스트)
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 1000 --timeout 3600
```

## 🔄 실행 시나리오별 가이드

### 시나리오 1: 개발 환경 첫 실행
```bash
# 1. 인프라 준비
./src/scripts/start_infrastructure.sh

# 2. 기본 파이프라인 테스트
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 20

# 3. 개별 컴포넌트 검증
uv run python src/scripts/run_kafka_dag.py --action task --task-name check_kafka_health
```

### 시나리오 2: 성능 검증
```bash
# 1. 소량 데이터로 예열
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 10

# 2. 정상 배치 크기로 성능 측정
time uv run python src/scripts/run_kafka_dag.py --action full --mock-count 100

# 3. 대용량 부하 테스트
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 500 --timeout 1800
```

### 시나리오 3: 오류 처리 검증
```bash
# 1. Producer 실패 시뮬레이션
uv run python src/scripts/run_kafka_dag.py --action full --simulate-failure

# 2. Consumer 타임아웃 테스트
uv run python src/scripts/run_kafka_dag.py --action full --timeout 30 --mock-count 100

# 3. 네트워크 지연 시뮬레이션 (별도 설정 필요)
# Docker 네트워크 지연 설정 후 실행
```

### 시나리오 4: CI/CD 파이프라인 통합
```bash
#!/bin/bash
# ci_test.sh

set -e  # 오류 시 중단

echo "🔧 인프라 시작..."
./src/scripts/start_infrastructure.sh

echo "🧪 Kafka 파이프라인 테스트..."
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 50 --no-notification

echo "🧹 인프라 정리..."
./src/scripts/stop_infrastructure.sh --remove-volumes

echo "✅ CI 테스트 완료!"
```
