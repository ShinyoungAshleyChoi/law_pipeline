# 법제처 데이터 파이프라인

실제 API를 호출하지 않고도 완전한 Kafka 기반 데이터 파이프라인을 테스트할 수 있는 프로젝트입니다.

## 🚀 빠른 시작

### ⚡ 새로운 방법: Kafka 파이프라인 바로 실행 (권장)

가장 빠르고 쉬운 방법입니다!

```bash
# 1. 인프라 시작
./src/scripts/start_infrastructure.sh

# 2. Kafka 파이프라인 전체 실행 (MOCK 데이터 사용)
uv run python src/scripts/run_kafka_dag.py --action full

# 3. 인프라 중지
./src/scripts/stop_infrastructure.sh
```

**이 방법의 장점:**
- ✅ Airflow 설치/설정 불필요
- ✅ 즉시 실행 가능
- ✅ 상세한 실행 결과 확인
- ✅ 실제 Kafka Producer/Consumer 사용
- ✅ 완전한 워크플로우 테스트

### 🎯 고급 실행 옵션

```bash
# 더 많은 MOCK 데이터로 테스트
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 100 --timeout 600

# 실패 시나리오 테스트
uv run python src/scripts/run_kafka_dag.py --action full --simulate-failure

# 개별 태스크만 실행
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_produce_mock_data

# 사용 가능한 태스크 목록 확인
uv run python src/scripts/run_kafka_dag.py --action list
```

### 📊 실행 결과 예시

```
🚀 Kafka 기반 법제처 데이터 파이프라인 전체 실행 시작

🔍 1. Kafka 헬스 체크 실행 중...
✅ Kafka 헬스 체크 완료 (2.1초)

📤 2. Kafka Producer (MOCK 데이터) 실행 중...
✅ Producer 완료 (12.3초)
   전송 성공: 25개, 전송 실패: 0개

📥 3. Kafka Consumer & DB 저장 실행 중...
✅ Consumer 완료 (8.7초)
   수신 메시지: 25개, 저장 성공: 25개

📢 4. 완료 알림 전송 실행 중...
✅ 알림 전송 완료 (1.2초)

🎯 전체 성공률: 100.0% (25/25)
🎉 전체 파이프라인 실행 성공!
```

---

### 🔄 기존 방법: Airflow DAG 실행

```bash
# 1. 인프라 시작
./src/scripts/start_infrastructure.sh

# 2. Airflow 환경 초기화
uv run python src/scripts/run_mock_airflow_dag.py --action init

# 3. DAG 목록 확인
uv run python src/scripts/run_mock_airflow_dag.py --action list

# 4. DAG 실행
uv run python src/scripts/run_mock_airflow_dag.py --action trigger --dag-id kafka_legal_data_pipeline_mock

# 5. 인프라 중지
./src/scripts/stop_infrastructure.sh
```

## 🏗️ 프로젝트 구조

```
법제처 데이터 파이프라인/
├── 📁 src/                          # 소스 코드
│   ├── 📁 api/                      # 법제처 API 클라이언트
│   ├── 📁 streaming/                # Kafka Producer/Consumer
│   ├── 📁 database/                 # 데이터베이스 모델 및 Repository
│   ├── 📁 mock/                     # MOCK 데이터 생성기
│   ├── 📁 notifications/            # 슬랙 알림 서비스
│   └── 📁 scripts/                  # 실행 스크립트들
│       ├── 🚀 run_kafka_dag.py      # Kafka 파이프라인 직접 실행기 (NEW!)
│       ├── run_mock_airflow_dag.py  # Airflow DAG 실행기
│       └── ...
├── 📁 dags/                         # Airflow DAG 파일들
└── 📁 deployment/                   # Docker 배포 설정
```

## 🔧 추가 기능

### 블루-그린 배포 테스트
```bash
# 배포 실행
./src/scripts/deploy_bluegreen.sh deploy

# 상태 확인
./src/scripts/deploy_bluegreen.sh status

# 롤백
./src/scripts/deploy_bluegreen.sh rollback
```

### Kafka 파티션 최적화 테스트
```bash
# 파티션 최적화 효과 분석
uv run python src/scripts/test_partition_optimization.py

# 결과 확인
cat partition_optimization_results.json
```

## 📋 서비스 접속 정보

- **Kafka UI**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/legal_grafana_2024!)
- **Airflow**: http://localhost:8090 (airflow/airflow_admin_2024!)
- **MySQL Blue**: localhost:3306 (legal_user/legal_pass_2024!)
- **MySQL Green**: localhost:3307 (legal_user/legal_pass_2024!)

## 🎯 주요 특징

### ✨ 새로운 Kafka 파이프라인 직접 실행기
- **Airflow 불필요**: 복잡한 설정 없이 바로 실행
- **MOCK 데이터**: MockDataGenerator로 현실적인 법령 데이터 생성
- **완전한 워크플로우**: Producer → Consumer → DB 저장 → 알림까지
- **실제 Kafka 사용**: 진정한 스트리밍 환경 테스트
- **상세한 모니터링**: 실시간 진행상황 및 상세 통계

### 🔄 기존 기능들
- **블루-그린 배포**: 무중단 배포 및 롤백 지원
- **Mock 환경**: 실제 API 호출 없이 전체 파이프라인 테스트
- **Kafka 최적화**: 파티션 전략 최적화 및 성능 테스트
- **모니터링**: Grafana 대시보드와 슬랙 알림

## 💡 실행 시나리오별 가이드

### 🧪 개발 및 테스트
```bash
# 빠른 검증 (소량 데이터)
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 10

# 일반적인 배치 크기 테스트
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 50

# 대용량 부하 테스트
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 500 --timeout 1800
```

### 🔍 디버깅
```bash
# 개별 컴포넌트 테스트
uv run python src/scripts/run_kafka_dag.py --action task --task-name check_kafka_health
uv run python src/scripts/run_kafka_dag.py --action task --task-name kafka_produce_mock_data

# 실패 시나리오 테스트
uv run python src/scripts/run_kafka_dag.py --action full --simulate-failure

# 알림 없이 빠른 테스트
uv run python src/scripts/run_kafka_dag.py --action full --no-notification --mock-count 10
```

### 🚀 CI/CD 통합
```bash
#!/bin/bash
# 자동화된 테스트 스크립트

set -e
./src/scripts/start_infrastructure.sh
uv run python src/scripts/run_kafka_dag.py --action full --mock-count 50 --no-notification
./src/scripts/stop_infrastructure.sh --remove-volumes
echo "✅ CI 테스트 완료!"
```

## 💡 유용한 명령어

```bash
# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f kafka
docker-compose logs -f mysql-blue

# 실행 중인 Kafka Consumer 그룹 확인
docker exec -it kafka kafka-consumer-groups --bootstrap-server localhost:9092 --list

# Kafka 토픽 메시지 확인
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic law_events --from-beginning
```

## 📚 자세한 사용법

- [스크립트 상세 사용법](src/scripts/README.md)
- [Kafka 파이프라인 직접 실행기 가이드](src/scripts/README.md#-kafka-파이프라인-직접-실행기-상세-가이드)
- [배포 및 운영 가이드](deployment/README_COMPLETE.md)

---

**🎉 이제 복잡한 설정 없이도 완전한 Kafka 기반 데이터 파이프라인을 바로 체험할 수 있습니다!**
