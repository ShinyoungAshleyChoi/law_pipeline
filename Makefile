# 법제처 데이터 파이프라인 Makefile

.PHONY: help install dev test clean docker up down logs restart status topics

# 기본 타겟
help: ## 도움말 표시
	@echo "법제처 데이터 파이프라인 관리 명령어"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# 개발 환경 설정
install: ## 의존성 설치
	@echo "🔧 의존성 설치 중..."
	uv sync --all-extras

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

test-integration: ## 통합 테스트 (Kafka, MySQL 포함)
	@echo "🔗 통합 테스트 실행 중..."
	uv run pytest -m integration

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
	@./scripts/start_infrastructure.sh --clean-volumes

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

logs-app: ## 애플리케이션 로그 확인 (구현 후 추가)
	@echo "📜 애플리케이션 로그:"
	# docker-compose logs -f legal-api legal-producer legal-consumer

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

# 데이터 관리
db-init: ## 데이터베이스 초기화
	@echo "🗄️  데이터베이스 초기화 중..."
	uv run python scripts/full_data_load.py --batch-size 50

db-load: ## Mock 데이터 적재
	@echo "📥 Mock 데이터 적재 중..."
	uv run python scripts/full_data_load.py

db-migrate: ## 스키마 마이그레이션 (구현 예정)
	@echo "🔄 데이터베이스 마이그레이션..."
	# uv run alembic upgrade head

# 배치 작업
batch-incremental: ## 증분 업데이트 실행
	@echo "🔄 증분 업데이트 실행 중..."
	uv run python scripts/incremental_update.py

batch-validation: ## 데이터 검증 실행
	@echo "✅ 데이터 검증 실행 중..."
	uv run python scripts/data_validation.py

# Kafka Producer/Consumer
producer-run: ## Kafka Producer 실행 (데이터 수집 및 전송)
	@echo "📤 Kafka Producer 실행 중..."
	uv run python -m src.kafka.producer

producer-health: ## Producer 헬스체크
	@echo "🩺 Producer 헬스체크..."
	uv run python -m src.kafka.producer --health-check

producer-sync: ## 특정 날짜 기준 증분 동기화
	@echo "🔄 증분 동기화 실행 중..."
	@read -p "동기화 기준 날짜 (YYYY-MM-DD, 엔터 시 오늘): " sync_date; \
	if [ -n "$$sync_date" ]; then \
		uv run python -m src.kafka.producer --last-sync-date $$sync_date; \
	else \
		uv run python -m src.kafka.producer; \
	fi

consumer-run: ## Kafka Consumer 실행 (메시지 처리)
	@echo "📥 Kafka Consumer 실행 중..."
	uv run python -m src.kafka.consumer

consumer-test: ## Consumer 테스트 (10개 메시지만 처리)
	@echo "🧪 Consumer 테스트 중..."
	uv run python -m src.kafka.consumer --max-messages 10

consumer-health: ## Consumer 헬스체크
	@echo "🩺 Consumer 헬스체크..."
	uv run python -m src.kafka.consumer --health-check

# Kafka 통합 테스트
kafka-e2e-test: ## End-to-End Kafka 테스트
	@echo "🔄 Kafka E2E 테스트 시작..."
	@echo "1. Producer 실행하여 테스트 데이터 전송..."
	@(uv run python -m src.kafka.producer --correlation-id test-e2e &); \
	producer_pid=$$!; \
	sleep 10; \
	echo "2. Consumer 실행하여 메시지 처리..."; \
	uv run python -m src.kafka.consumer --max-messages 50 --group-id test-consumer; \
	kill $$producer_pid 2>/dev/null || true; \
	echo "✅ E2E 테스트 완료"

kafka-integration-test: ## Kafka 통합 테스트 실행
	@echo "🧪 Kafka 통합 테스트 실행..."
	uv run python scripts/test_kafka_integration.py

kafka-monitor: ## Kafka 메시지 모니터링
	@echo "👀 Kafka 메시지 모니터링..."
	@echo "실행 중인 Consumer들:"
	@ps aux | grep "kafka.consumer" | grep -v grep || echo "실행 중인 Consumer 없음"
	@echo ""
	@echo "Kafka 토픽 상태:"
	@make topics-describe

# 모니터링 및 알림
monitor: ## 모니터링 대시보드 열기
	@echo "📊 모니터링 대시보드:"
	@echo "   🔗 Kafka UI:    http://localhost:8080"
	@echo "   📊 Grafana:     http://localhost:3000"
	@echo "   📈 Prometheus:  http://localhost:9090"

notify-test: ## 알림 테스트
	@echo "📢 알림 테스트 중..."
	uv run python scripts/test_notifications.py

# 정리 작업
clean: ## 캐시 및 임시 파일 정리
	@echo "🧹 정리 작업 중..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	@echo "✅ 정리 완료"

clean-all: clean down-volumes ## 모든 데이터 및 캐시 정리
	@echo "🗑️  전체 정리 완료"

# 블루그린 배포
# 블루그린 배포 개발 환경
bluegreen-dev-setup: ## 블루그린 개발 환경 설정 (UV 사용)
	@echo "🔧 블루그린 개발 환경 설정 중..."
	@cd deployment && echo "📦 UV 환경 설정..." && uv sync --dev
	@echo "✅ 블루그린 개발 환경 설정 완료!"

bluegreen-uv-sync: ## UV 의존성 동기화
	@echo "🔄 UV 의존성 동기화 중..."
	@cd deployment && uv sync
	@echo "✅ UV 의존성 동기화 완료!"

bluegreen-uv-add: ## UV 패키지 추가 (usage: make bluegreen-uv-add PACKAGE=package_name)
	@echo "📦 UV 패키지 추가: $(PACKAGE)"
	@cd deployment && uv add $(PACKAGE)

bluegreen-uv-remove: ## UV 패키지 제거 (usage: make bluegreen-uv-remove PACKAGE=package_name)
	@echo "🗑️ UV 패키지 제거: $(PACKAGE)"
	@cd deployment && uv remove $(PACKAGE)

bluegreen-uv-lock: ## UV lock 파일 업데이트
	@echo "🔒 UV lock 파일 업데이트 중..."
	@cd deployment && uv lock
	@echo "✅ UV lock 파일 업데이트 완료!"

bluegreen-shell: ## 블루그린 UV Python 쉘 실행
	@echo "🐍 블루그린 UV Python 쉘 시작..."
	@cd deployment && uv run python

bluegreen-test: ## 블루그린 테스트 실행 (UV 환경)
	@echo "🧪 블루그린 테스트 실행 중..."
	@cd deployment && uv run pytest tests/ -v || echo "테스트 디렉토리가 없습니다."

bluegreen-lint: ## 블루그린 코드 린팅 (UV 환경)
	@echo "🔍 블루그린 코드 린팅 중..."
	@cd deployment && uv run black --check . && uv run isort --check-only . && uv run flake8 .

bluegreen-format: ## 블루그린 코드 포맷팅 (UV 환경)
	@echo "🎨 블루그린 코드 포맷팅 중..."
	@cd deployment && uv run black . && uv run isort .

bluegreen-deploy: bluegreen-uv-sync ## 블루그린 배포 실행
	@echo "🔄 블루그린 배포 시작..."
	@chmod +x scripts/deploy_bluegreen.sh
	@./scripts/deploy_bluegreen.sh deploy

bluegreen-deploy-version: ## 특정 버전으로 블루그린 배포
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

bluegreen-access: ## 블루그린 접속 정보 출력
	@echo "🌐 블루그린 배포 접속 정보:"
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
	@echo ""
	@echo "🛠️  개별 환경:"
	@echo "   💙 Blue 환경:      http://localhost:8001"
	@echo "   💚 Green 환경:     http://localhost:8002"

# 프로덕션 배포
build: ## Docker 이미지 빌드
	@echo "🔨 Docker 이미지 빌드 중..."
	@echo "📦 UV 환경 설정..."
	@cd deployment && uv sync
	@echo "🐳 Docker 이미지들 빌드..."
	docker build -f deployment/Dockerfile.app -t legal-data-pipeline:latest .
	docker build -f deployment/Dockerfile.controller -t legal-deployment-controller:latest .
	docker build -f deployment/Dockerfile.monitor -t legal-health-monitor:latest .
	docker build -f deployment/Dockerfile.migration -t legal-db-migration:latest .
	@echo "✅ 모든 이미지 빌드 완료!"

build-dev: ## 개발용 이미지 빌드 (캐시 없이)
	@echo "🔨 개발용 Docker 이미지 빌드 중..."
	@cd deployment && uv sync --dev
	docker build --no-cache -f deployment/Dockerfile.app -t legal-data-pipeline:dev .
	docker build --no-cache -f deployment/Dockerfile.controller -t legal-deployment-controller:dev .

deploy: bluegreen-deploy ## 프로덕션 배포 (블루그린)

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

# 전체 워크플로우
setup: dev up topics-setup ## 전체 개발 환경 설정
	@echo "🎉 개발 환경 설정 완료!"
	@echo ""
	@echo "다음 단계:"
	@echo "  1. make db-init          # 데이터베이스 초기화"
	@echo "  2. make db-load          # Mock 데이터 적재"
	@echo "  3. make test             # 테스트 실행"
	@echo "  4. make monitor          # 모니터링 대시보드 확인"
	@echo ""
	@echo "🔄 블루그린 배포 명령어:"
	@echo "  - make bluegreen-deploy  # 블루그린 배포"
	@echo "  - make bluegreen-status  # 배포 상태 확인"
	@echo "  - make bluegreen-access  # 접속 정보 확인"

setup-bluegreen: bluegreen-setup bluegreen-deploy ## 블루그린 환경 완전 설정
	@echo "🎉 블루그린 환경 설정 완료!"
	@make bluegreen-access

# 기본값
.DEFAULT_GOAL := help
