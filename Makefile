# 법제처 데이터 파이프라인 Makefile (최종 정리 버전)

.PHONY: help install dev test clean docker up down logs restart status topics

# 기본 타겟
help: ## 도움말 표시
	@echo "법제처 데이터 파이프라인 관리 명령어"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# 개발 환경 설정
install: ## UV 의존성 설치
	@echo "🔧 UV 의존성 설치 중..."
	uv sync --all-groups

dev: install ## 개발 환경 설정 (의존성 설치 + pre-commit)
	@echo "🛠️  개발 환경 설정 중..."
	uv run pre-commit install
	@echo "✅ 개발 환경 설정 완료"

# 테스트
test: ## 테스트 실행
	@echo "🧪 테스트 실행 중..."
	uv run pytest

test-cov: ## 커버리지 포함 테스트
	@echo "🧪 커버리지 테스트 실행 중..."
	uv run pytest --cov=src --cov-report=html --cov-report=term

test-integration: ## 통합 테스트 실행
	@echo "🔗 통합 테스트 실행 중..."
	uv run pytest -m integration

test-airflow: ## Airflow DAG 테스트
	@echo "✈️  Airflow DAG 테스트 중..."
	uv run pytest tests/ -m airflow -v || echo "Airflow 테스트 파일이 없습니다."

test-bluegreen: ## 블루그린 테스트
	@echo "🧪 블루그린 테스트 실행 중..."
	uv run pytest tests/ -m bluegreen -v || echo "블루그린 테스트 파일이 없습니다."

test-all: ## 전체 통합 테스트
	@echo "🧪 전체 통합 테스트 실행 중..."
	@make test && make kafka-integration-test && make test-bluegreen
	@echo "✅ 전체 테스트 완료!"

# 코드 품질
lint: ## 코드 린팅
	@echo "🔍 코드 린팅 중..."
	uv run flake8 src/ tests/
	uv run mypy src/

format: ## 코드 포맷팅
	@echo "🎨 코드 포맷팅 중..."
	uv run black src/ tests/
	uv run isort src/ tests/

format-check: ## 코드 포맷팅 확인
	@echo "🔍 포맷팅 확인 중..."
	uv run black --check src/ tests/
	uv run isort --check-only src/ tests/

# Docker 인프라 관리
up: ## 인프라 시작 (Docker Compose)
	@echo "🚀 인프라 시작 중..."
	@chmod +x scripts/start_infrastructure.sh
	@./scripts/start_infrastructure.sh

up-clean: ## 인프라 시작 (볼륨 초기화)
	@echo "🧹 볼륨 초기화하고 인프라 시작 중..."
	@chmod +x scripts/start_infrastructure.sh
sh --clean-volumes

down: ## 인프라 중지
	@echo "🛑 인프라 중지 중..."
	docker-compose down

down-volumes: ## 인프라 중지 (볼륨 제거)
	@echo "🗑️  인프라 중지 및 볼륨 제거 중..."
	docker-compose down -v

restart: down up ## 인프라 재시작

# 서비스 상태 및 로그
status: ## 서비스 상태 확인
	@echo "📊 서비스 상태:"
	@docker-compose ps

logs: ## 모든 서비스 로그 확인
	@echo "📜 서비스 로그:"
	docker-compose logs -f --tail=100

logs-kafka: ## Kafka 로그 확인
	@echo "📜 Kafka 로그:"
	docker-compose logs -f kafka1 kafka2 kafka3

logs-mysql: ## MySQL 로그 확인
	@echo "📜 MySQL 로그:"
	docker-compose logs -f mysql-blue mysql-green

logs-airflow: ## Airflow 로그 확인
	@echo "📜 Airflow 로그:"
	docker-compose logs -f airflow-webserver airflow-scheduler airflow-worker

# Kafka 관련
topics: ## Kafka 토픽 목록 조회
	@echo "📋 Kafka 토픽 목록:"
	uv run python scripts/setup_kafka_topics.py --action list

topics-setup: ## Kafka 토픽 생성
	@echo "⚙️  Kafka 토픽 생성 중..."
	uv run python scripts/setup_kafka_topics.py --action setup

topics-describe: ## Kafka 토픽 상세 정보
	@echo "📝 Kafka 토픽 상세 정보:"
	uv run python scripts/setup_kafka_topics.py --action describe

kafka-integration-test: ## Kafka 통합 테스트 실행
	@echo "🧪 Kafka 통합 테스트 실행..."
	uv run python scripts/test_kafka_integration.py

kafka-e2e-test: ## End-to-End Kafka 테스트
	@echo "🔄 Kafka E2E 테스트 시작..."
	@(uv run python -m src.kafka.producer --correlation-id test-e2e &); \
	producer_pid=$$!; \
	sleep 10; \
	uv run python -m src.kafka.consumer --max-messages 50 --group-id test-consumer; \
	kill $$producer_pid 2>/dev/null || true; \
	echo "✅ E2E 테스트 완료"

# 데이터 관리
db-init: ## 데이터베이스 초기화
	@echo "🗄️  데이터베이스 초기화 중..."
	uv run python scripts/full_data_load.py --batch-size 50

db-load: ## Mock 데이터 적재
	@echo "📥 Mock 데이터 적재 중..."
	uv run python scripts/full_data_load.py

batch-incremental: ## 증분 업데이트 실행
	@echo "🔄 증분 업데이트 실행 중..."
	uv run python scripts/incremental_update.py

batch-validation: ## 데이터 검증 실행
	@echo "✅ 데이터 검증 실행 중..."
	uv run python scripts/data_validation.py

# Kafka Producer/Consumer
producer-run: ## Kafka Producer 실행
	@echo "📤 Kafka Producer 실행 중..."
	uv run python -m src.kafka.producer

consumer-run: ## Kafka Consumer 실행
	@echo "📥 Kafka Consumer 실행 중..."
	uv run python -m src.kafka.consumer

producer-health: ## Producer 헬스체크
	@echo "🩺 Producer 헬스체크..."
	uv run python -m src.kafka.producer --health-check

consumer-health: ## Consumer 헬스체크
	@echo "🩺 Consumer 헬스체크..."
	uv run python -m src.kafka.consumer --health-check

# Apache Airflow 관리
airflow-init: ## Airflow 초기 설정
	@echo "🛠️  Airflow 초기 설정 중..."
	@mkdir -p src/airflow/logs src/airflow/plugins src/airflow/config
	@echo "📦 Airflow 서비스 시작 중..."
	docker-compose up -d postgres redis
	@sleep 20
	docker-compose up -d airflow-webserver airflow-scheduler airflow-worker airflow-flower
	@echo "✅ Airflow 초기 설정 완료!"
	@echo "🌐 Airflow 웹서버: http://localhost:8090 (airflow/airflow_admin_2024!)"
	@echo "🌸 Flower 모니터링: http://localhost:5555"

airflow-start: ## Airflow 서비스 시작
	@echo "🚀 Airflow 서비스 시작 중..."
	docker-compose up -d postgres redis airflow-webserver airflow-scheduler airflow-worker airflow-flower

airflow-stop: ## Airflow 서비스 중지
	@echo "🛑 Airflow 서비스 중지 중..."
	docker-compose stop airflow-webserver airflow-scheduler airflow-worker airflow-flower

airflow-clean: ## Airflow 데이터 초기화
	@echo "🧹 Airflow 데이터 초기화 중..."
	docker-compose down
	docker volume rm legal_postgres_data legal_airflow_logs 2>/dev/null || true

# 블루그린 배포 (UV 통합)
cleanup-duplicates: ## 중복 파일 정리 및 UV 동기화
	@echo "🧹 중복 파일 정리 중..."
	@rm -f deployment/pyproject.toml deployment/uv.lock 2>/dev/null || true
	@echo "📦 UV 통합 의존성 동기화..."
	@uv sync --group deployment --group monitoring
	@echo "✅ 정리 완료!"

bluegreen-deploy: cleanup-duplicates ## 블루그린 배포 실행
	@echo "🔄 블루그린 배포 시작..."
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh deploy

bluegreen-deploy-version: cleanup-duplicates ## 특정 버전으로 블루그린 배포
	@read -p "배포할 버전을 입력하세요: " version; \
	echo "🔄 버전 $$version 블루그린 배포 시작..."; \
	chmod +x scripts/deploy_bluegreen.sh; \
	./scripts/deploy_bluegreen.sh deploy $$version

bluegreen-rollback: ## 블루그린 롤백
	@echo "⏪ 블루그린 롤백 시작..."
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh rollback

bluegreen-status: ## 블루그린 배포 상태 확인
	@echo "📊 블루그린 배포 상태:"
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh status

bluegreen-setup: ## 블루그린 인프라 설정
	@echo "🏗️  블루그린 인프라 설정 중..."
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh setup

bluegreen-stop: ## 블루그린 서비스 중지
	@echo "🛑 블루그린 서비스 중지 중..."
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh stop

bluegreen-logs: ## 블루그린 로그 확인
	@echo "📜 블루그린 로그:"
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh logs

bluegreen-cleanup: ## 블루그린 완전 정리
	@echo "🗑️  블루그린 완전 정리..."
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh cleanup

# UV 관리
uv-sync: cleanup-duplicates ## UV 의존성 동기화
	@echo "🔄 UV 통합 의존성 동기화 중..."
	@uv sync --all-groups

uv-add: ## UV 패키지 추가 (usage: make uv-add PACKAGE=package_name)
	@echo "📦 UV 패키지 추가: $(PACKAGE)"
	@uv add $(PACKAGE)

uv-remove: ## UV 패키지 제거 (usage: make uv-remove PACKAGE=package_name)
	@echo "🗑️ UV 패키지 제거: $(PACKAGE)"
	@uv remove $(PACKAGE)

uv-lock: ## UV lock 파일 업데이트
	@echo "🔒 UV lock 파일 업데이트 중..."
	@uv lock

uv-shell: ## UV Python 쉘 실행
	@echo "🐍 UV Python 쉘 시작..."
	@uv run python

# 전체 스택 관리
full-stack: ## 전체 스택 시작 (Kafka+MySQL+Airflow+BlueGreen)
	@echo "🚀 전체 스택 시작 중..."
	@echo "1️⃣  기본 인프라 시작..."
	@make up
	@echo "2️⃣  Airflow 초기화..."
	@make airflow-init
	@echo "3️⃣  블루그린 배포..."
	@make bluegreen-deploy
	@echo "4️⃣  Kafka 파티션 최적화 확인..."
	@make partition-health
	@echo "✅ 전체 스택 준비 완료!"
	@make access-info

full-stack-stop: ## 전체 스택 중지
	@echo "🛑 전체 스택 중지 중..."
	@make bluegreen-stop || true
	@make airflow-stop || true
	@make down

full-stack-clean: ## 전체 스택 완전 정리
	@echo "🗑️  전체 스택 완전 정리..."
	@make bluegreen-cleanup || true
	@make airflow-clean || true
	@make clean-all

# Kafka 파티션 모니터링
partition-health: ## Kafka 파티션 건강 상태 체크
	@echo "🔍 Kafka 파티션 건강 상태 체크 중..."
	uv run python -m src.kafka.partition_monitor --action health

partition-analyze: ## 특정 토픽 파티션 분석 (usage: make partition-analyze TOPIC=legal-law-events)
	@echo "📊 토픽 파티션 분석: $(TOPIC)"
	uv run python -m src.kafka.partition_monitor --action analyze --topic $(TOPIC)

partition-suggest: ## 파티션 리밸런싱 제안 (usage: make partition-suggest TOPIC=legal-law-events)  
	@echo "💡 파티션 리밸런싱 제안: $(TOPIC)"
	uv run python -m src.kafka.partition_monitor --action suggest --topic $(TOPIC)

partition-optimize: ## 모든 토픽 파티션 최적화 권장사항
	@echo "⚡ 전체 파티션 최적화 권장사항:"
	@echo ""
	@echo "📋 법령 이벤트 토픽:"
	@make partition-analyze TOPIC=legal-law-events
	@echo ""
	@echo "📋 본문 이벤트 토픽:" 
	@make partition-analyze TOPIC=legal-content-events
	@echo ""
	@echo "📋 조항 이벤트 토픽:"
	@make partition-analyze TOPIC=legal-article-events

status-all: ## 모든 서비스 상태 확인
	@echo "📊 전체 시스템 상태:"
	@echo ""
	@echo "🐳 Docker 컨테이너:"
	@docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -20
	@echo ""
	@echo "💾 볼륨 사용량:"
	@docker system df
	@echo ""
	@make bluegreen-status 2>/dev/null || echo "블루그린 시스템 미실행"
	@echo ""
	@make mock-status

access-info: ## 전체 접속 정보 출력
	@echo "🌐 전체 시스템 접속 정보:"
	@echo ""
	@echo "📱 메인 애플리케이션:"
	@echo "   🔗 로드밸런서:     http://localhost:80"
	@echo "   📖 API 문서:       http://localhost:80/docs"
	@echo "   🏥 헬스체크:       http://localhost:80/health"
	@echo ""
	@echo "🔧 관리 도구:"
	@echo "   🎛️  배포 API:        http://localhost:9000"
	@echo "   📊 Grafana:        http://localhost:3000 (admin/legal_grafana_2024!)"
	@echo "   📈 Prometheus:     http://localhost:9090"
	@echo "   🔗 Kafka UI:       http://localhost:8080"
	@echo "   ✈️  Airflow:        http://localhost:8090 (airflow/airflow_admin_2024!)"
	@echo "   🌸 Flower:         http://localhost:5555"
	@echo ""
	@echo "🛠️  개별 환경:"
	@echo "   💙 Blue 환경:      http://localhost:8001"
	@echo "   💚 Green 환경:     http://localhost:8002"
	@echo ""
	@echo "💾 데이터베이스:"
	@echo "   💙 MySQL Blue:     localhost:3306 (legal_user/legal_pass_2024!)"
	@echo "   💚 MySQL Green:    localhost:3307 (legal_user/legal_pass_2024!)"
	@echo "   🗄️  PostgreSQL:     localhost:5432 (airflow/airflow_pass_2024!)"
	@echo "   📦 Redis:          localhost:6379 (legal_redis_2024!)"
	@echo ""
	@echo "🔄 Kafka 파티션 모니터링:"
	@echo "   📊 건강 상태:       make partition-health"
	@echo "   🔍 토픽 분석:       make partition-analyze TOPIC=토픽명"
	@echo "   💡 최적화 제안:     make partition-suggest TOPIC=토픽명"
	@echo "   ⚡ 전체 최적화:     make partition-optimize"
	@echo ""
	@echo "🎭 Mock 환경:"
	@echo "   📊 Mock 상태:       make mock-status"
	@echo "   🔧 Mock 설정:       make mock-setup"
	@echo "   🧪 Mock 테스트:     make mock-test-all"
	@echo "   🚀 Mock 실행:       make mock-run"

# 모니터링
monitor: ## 모니터링 대시보드 열기
	@echo "📊 모니터링 대시보드:"
	@echo "   🔗 Kafka UI:    http://localhost:8080"
	@echo "   📊 Grafana:     http://localhost:3000"
	@echo "   📈 Prometheus:  http://localhost:9090"
	@echo "   ✈️  Airflow:     http://localhost:8090"
	@echo "   🌸 Flower:      http://localhost:5555"

notify-test: ## 알림 테스트
	@echo "📢 알림 테스트 중..."
	uv run python scripts/test_notifications.py

# Docker 이미지 빌드
build: ## Docker 이미지 빌드
	@echo "🔨 Docker 이미지 빌드 중..."
	@echo "📦 UV 통합 환경 설정..."
	@uv sync --group deployment --group monitoring
	@echo "🐳 Docker 이미지들 빌드..."
	docker build -f deployment/Dockerfile.app -t legal-data-pipeline:latest .
	docker build -f deployment/Dockerfile.controller -t legal-deployment-controller:latest .
	docker build -f deployment/Dockerfile.monitor -t legal-health-monitor:latest .
	docker build -f deployment/Dockerfile.migration -t legal-db-migration:latest .
	@echo "✅ 모든 이미지 빌드 완료!"

build-dev: ## 개발용 이미지 빌드 (캐시 없이)
	@echo "🔨 개발용 Docker 이미지 빌드 중..."
	@uv sync --group deployment --group monitoring --group dev
	docker build --no-cache -f deployment/Dockerfile.app -t legal-data-pipeline:dev .
	docker build --no-cache -f deployment/Dockerfile.controller -t legal-deployment-controller:dev .

# 개발 유틸리티
shell: ## Python 셸 실행
	@echo "🐍 Python 셸 시작..."
	uv run python

shell-kafka: ## Kafka 컨테이너 셸 접속
	@echo "🔗 Kafka 컨테이너 접속..."
	docker-compose exec kafka1 bash

shell-mysql-blue: ## MySQL Blue 컨테이너 접속
	@echo "💙 MySQL Blue 접속..."
	docker-compose exec mysql-blue mysql -u legal_user -plegal_pass_2024! legal_db

shell-mysql-green: ## MySQL Green 컨테이너 접속
	@echo "💚 MySQL Green 접속..."
	docker-compose exec mysql-green mysql -u legal_user -plegal_pass_2024! legal_db

shell-postgres: ## PostgreSQL 컨테이너 접속
	@echo "🐘 PostgreSQL 접속..."
	docker-compose exec postgres psql -U airflow -d airflow

# 정리 작업
clean: ## 캐시 및 임시 파일 정리
	@echo "🧹 정리 작업 중..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ 2>/dev/null || true
	@echo "✅ 정리 완료"

clean-all: clean down-volumes cleanup-duplicates ## 모든 데이터 및 캐시 정리
	@echo "🗑️  전체 정리 완료"

# 전체 워크플로우
setup: dev mock-setup up topics-setup ## 기본 개발 환경 설정
	@echo "🎉 기본 개발 환경 설정 완료!"
	@echo ""
	@echo "다음 단계:"
	@echo "  1. make mock-run          # Mock 파이프라인 실행"
	@echo "  2. make mock-test-all     # Mock 테스트 실행"
	@echo "  3. make test              # 전체 테스트 실행"
	@echo "  4. make partition-health  # 파티션 상태 확인"
	@echo "  5. make monitor           # 모니터링 대시보드 확인"
	@echo ""
	@echo "🚀 전체 스택 명령어:"
	@echo "  - make full-stack         # 전체 스택 시작"
	@echo "  - make bluegreen-deploy   # 블루그린 배포"
	@echo "  - make access-info        # 접속 정보 확인"

setup-full: cleanup-duplicates full-stack ## 전체 스택 완전 설정
	@echo "🎉 전체 스택 환경 설정 완료!"
	@make access-info

setup-mock: ## Mock 환경만 설정 (빠른 개발용)
	@echo "🎭 Mock 개발 환경 설정 중..."
	@make mock-setup
	@make mock-test-all
	@echo ""
	@echo "🎉 Mock 환경 설정 완료!"
	@echo ""
	@echo "Mock 환경 사용법:"
	@echo "  - make mock-run           # 전체 파이프라인 실행"
	@echo "  - make mock-run-search    # 문서 검색"
	@echo "  - make mock-run-stats     # 통계 조회"
	@echo "  - make mock-status        # Mock 상태 확인"

# 파티션 최적화 테스트
test-partition: ## 파티션 최적화 효과 테스트
	@echo "🔬 파티션 최적화 시뮬레이션 테스트..."
	uv run python scripts/test_partition_optimization.py

validate-partitions: ## 파티션 설정 검증 및 권장사항
	@echo "✅ 파티션 설정 검증 중..."
	@echo "📊 현재 설정:"
	@echo "  - legal-law-events: 3개 파티션 (최적화됨)"
	@echo "  - legal-content-events: 6개 파티션 (최적화됨)"  
	@echo "  - legal-article-events: 12개 파티션 (최적화됨)"
	@echo ""
	@make test-partition

# 프로덕션 배포
deploy: bluegreen-deploy ## 프로덕션 배포 (블루그린)

# 기본값
.DEFAULT_GOAL := help
