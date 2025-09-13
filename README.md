# 법제처 데이터 파이프라인

## 🚀 빠른 시작

### 1. 인프라 시작
```bash
./scripts/start_infrastructure.sh
```

### 2. 목 데이터로 Airflow 실행
```bash
uv run python scripts/run_mock_airflow_dag.py
```

### 3. 인프라 중지
```bash
./scripts/stop_infrastructure.sh
```

## 🔧 추가 기능

### 블루그린 배포 테스트
```bash
# 현재 활성 DB 확인
uv run python scripts/test_blue_green_deployment.py --action status

# Blue → Green 스위치
uv run python scripts/test_blue_green_deployment.py --action switch

# 배포 테스트 실행
uv run python scripts/test_blue_green_deployment.py --action test
```

### 파티션 테스트
```bash
# 파티션 생성 및 테스트
uv run python scripts/test_kafka_partitions.py --action create

# 파티션 성능 테스트
uv run python scripts/test_kafka_partitions.py --action performance

# 파티션 상태 확인
uv run python scripts/test_kafka_partitions.py --action status
```

## 📋 서비스 접속 정보

- **Kafka UI**: http://localhost:8080
- **Grafana**: http://localhost:3000 (admin/legal_grafana_2024!)
- **Airflow**: http://localhost:8090 (airflow/airflow_admin_2024!)
- **MySQL Blue**: localhost:3306 (legal_user/legal_pass_2024!)
- **MySQL Green**: localhost:3307 (legal_user/legal_pass_2024!)

## 💡 유용한 명령어

```bash
# 서비스 상태 확인
docker-compose ps

# 로그 확인
docker-compose logs -f [서비스명]

# Kafka 토픽 목록
uv run python scripts/setup_kafka_topics.py --action list
```
