#!/bin/bash

# 법제처 데이터 파이프라인 인프라 시작 스크립트
set -e

echo "🚀 법제처 데이터 파이프라인 인프라 시작"

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 로그 함수
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 사전 요구사항 확인
check_requirements() {
    log_info "사전 요구사항 확인 중..."
    
    # Docker 확인
    if ! command -v docker &> /dev/null; then
        log_error "Docker가 설치되어 있지 않습니다."
        exit 1
    fi
    
    # Docker Compose 확인
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose가 설치되어 있지 않습니다."
        exit 1
    fi
    
    # Python 확인
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3가 설치되어 있지 않습니다."
        exit 1
    fi
    
    # uv 확인
    if ! command -v uv &> /dev/null; then
        log_warn "uv가 설치되어 있지 않습니다. pip로 대체합니다."
    fi
    
    log_info "사전 요구사항 확인 완료"
}

# Docker 볼륨 정리
cleanup_volumes() {
    log_info "기존 Docker 볼륨 정리 중..."
    
    # 컨테이너 중지 및 제거
    docker-compose down --remove-orphans 2>/dev/null || true
    
    # 사용하지 않는 볼륨 제거 (선택적)
    if [ "$1" == "--clean-volumes" ]; then
        log_warn "모든 데이터 볼륨을 삭제합니다..."
        docker volume prune -f
        
        # 프로젝트별 볼륨 제거
        docker volume rm legal_zookeeper_data legal_zookeeper_logs \
                        legal_kafka1_data legal_kafka2_data legal_kafka3_data \
                        legal_mysql_blue_data legal_mysql_blue_logs \
                        legal_mysql_green_data legal_mysql_green_logs \
                        legal_redis_data legal_prometheus_data legal_grafana_data \
                        2>/dev/null || true
    fi
    
    log_info "볼륨 정리 완료"
}

# 네트워크 생성
create_network() {
    log_info "Docker 네트워크 생성 중..."
    
    # 기존 네트워크가 있으면 제거
    docker network rm legal-network 2>/dev/null || true
    
    # 새 네트워크 생성
    docker network create legal-network 2>/dev/null || true
    
    log_info "네트워크 생성 완료"
}

# 환경 변수 파일 생성
create_env_files() {
    log_info "환경 변수 파일 생성 중..."
    
    # .env 파일이 없으면 생성
    if [ ! -f .env ]; then
        log_info ".env 파일 생성 중..."
        cat > .env << EOF
# 법제처 데이터 파이프라인 환경 변수

# 환경 설정
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# 데이터베이스 설정 (Blue-Green)
DB_BLUE_HOST=mysql-blue
DB_BLUE_PORT=3306
DB_GREEN_HOST=mysql-green
DB_GREEN_PORT=3306
DB_NAME=legal_db
DB_USER=legal_user
DB_PASSWORD=legal_pass_2024!
DB_ROOT_PASSWORD=legal_root_2024!

# 현재 활성 DB 환경 (blue 또는 green)
ACTIVE_DB_ENV=blue

# Kafka 설정
KAFKA_BOOTSTRAP_SERVERS=kafka1:29092,kafka2:29093,kafka3:29094
KAFKA_BOOTSTRAP_SERVERS_EXTERNAL=localhost:9092,localhost:9093,localhost:9094

# Redis 설정
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=legal_redis_2024!

# 법제처 API 설정
LEGAL_API_BASE_URL=https://open.law.go.kr/LSO/openApi
LEGAL_API_TIMEOUT=30
LEGAL_API_MAX_RETRIES=3
LEGAL_API_RETRY_DELAY=1

# Slack 알림 설정 (실제 토큰으로 교체 필요)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_CHANNEL=#legal-data-alerts
SLACK_ERROR_CHANNEL=#legal-data-errors

# 모니터링 설정
PROMETHEUS_URL=http://prometheus:9090
GRAFANA_ADMIN_PASSWORD=legal_grafana_2024!

# 배치 작업 설정
BATCH_SIZE=100
MAX_CONCURRENT_JOBS=3
JOB_TIMEOUT=3600

# 보안 설정
SECRET_KEY=legal-pipeline-secret-key-change-in-production
JWT_SECRET=jwt-secret-key-change-in-production

EOF
        log_info ".env 파일 생성 완료"
    else
        log_info ".env 파일이 이미 존재합니다"
    fi
}

# Docker 컨테이너 시작
start_containers() {
    log_info "Docker 컨테이너 시작 중..."
    
    # 인프라 서비스 순서대로 시작
    log_info "1. Zookeeper 시작..."
    docker-compose up -d zookeeper
    
    # Zookeeper 헬스체크 대기
    log_info "Zookeeper 준비 대기 중..."
    timeout=60
    counter=0
    while ! docker-compose exec -T zookeeper sh -c 'echo "ruok" | nc localhost 2181' | grep -q "imok"; do
        sleep 2
        counter=$((counter + 2))
        if [ $counter -ge $timeout ]; then
            log_error "Zookeeper 시작 대기 시간 초과"
            exit 1
        fi
        echo -n "."
    done
    echo ""
    log_info "Zookeeper 시작 완료"
    
    # Kafka 클러스터 시작
    log_info "2. Kafka 클러스터 시작..."
    docker-compose up -d kafka1 kafka2 kafka3
    
    # Kafka 헬스체크 대기
    log_info "Kafka 클러스터 준비 대기 중..."
    timeout=120
    counter=0
    while ! docker-compose exec -T kafka1 kafka-topics --bootstrap-server localhost:9092 --list >/dev/null 2>&1; do
        sleep 5
        counter=$((counter + 5))
        if [ $counter -ge $timeout ]; then
            log_error "Kafka 시작 대기 시간 초과"
            exit 1
        fi
        echo -n "."
    done
    echo ""
    log_info "Kafka 클러스터 시작 완료"
    
    # Schema Registry 시작
    log_info "3. Schema Registry 시작..."
    docker-compose up -d schema-registry
    
    # MySQL Blue-Green 시작
    log_info "4. MySQL Blue-Green 시작..."
    docker-compose up -d mysql-blue mysql-green
    
    # MySQL 헬스체크 대기
    log_info "MySQL 준비 대기 중..."
    timeout=60
    counter=0
    while ! docker-compose exec -T mysql-blue mysqladmin ping -h localhost -u legal_user -plegal_pass_2024! --silent; do
        sleep 3
        counter=$((counter + 3))
        if [ $counter -ge $timeout ]; then
            log_error "MySQL Blue 시작 대기 시간 초과"
            exit 1
        fi
        echo -n "."
    done
    echo ""
    log_info "MySQL Blue 시작 완료"
    
    timeout=60
    counter=0
    while ! docker-compose exec -T mysql-green mysqladmin ping -h localhost -u legal_user -plegal_pass_2024! --silent; do
        sleep 3
        counter=$((counter + 3))
        if [ $counter -ge $timeout ]; then
            log_error "MySQL Green 시작 대기 시간 초과"
            exit 1
        fi
        echo -n "."
    done
    echo ""
    log_info "MySQL Green 시작 완료"
    
    # 나머지 서비스 시작
    log_info "5. 나머지 서비스 시작..."
    docker-compose up -d redis kafka-ui prometheus grafana
    
    log_info "모든 컨테이너 시작 완료"
}

# Kafka 토픽 설정
setup_kafka_topics() {
    log_info "Kafka 토픽 설정 중..."
    
    # Python 가상환경에서 실행
    if command -v uv &> /dev/null; then
        uv run python scripts/setup_kafka_topics.py --action setup
    else
        python3 scripts/setup_kafka_topics.py --action setup
    fi
    
    if [ $? -eq 0 ]; then
        log_info "Kafka 토픽 설정 완료"
    else
        log_error "Kafka 토픽 설정 실패"
        exit 1
    fi
}

# 서비스 상태 확인
check_services() {
    log_info "서비스 상태 확인 중..."
    
    services=(
        "zookeeper:2181"
        "kafka1:9092"
        "kafka2:9093"
        "kafka3:9094"
        "mysql-blue:3306"
        "mysql-green:3307"
        "redis:6379"
        "kafka-ui:8080"
        "schema-registry:8081"
        "prometheus:9090"
        "grafana:3000"
    )
    
    for service in "${services[@]}"; do
        IFS=':' read -ra ADDR <<< "$service"
        host=${ADDR[0]}
        port=${ADDR[1]}
        
        if timeout 5 bash -c "</dev/tcp/localhost/$port" 2>/dev/null; then
            log_info "✅ $host ($port) - 정상"
        else
            log_warn "⚠️  $host ($port) - 연결 실패"
        fi
    done
}

# 접속 정보 출력
print_access_info() {
    echo ""
    echo "🎉 법제처 데이터 파이프라인 인프라 시작 완료!"
    echo ""
    echo "📋 서비스 접속 정보:"
    echo "   🔗 Kafka UI:        http://localhost:8080"
    echo "   📊 Grafana:         http://localhost:3000 (admin/legal_grafana_2024!)"
    echo "   📈 Prometheus:      http://localhost:9090"
    echo "   🔄 Schema Registry: http://localhost:8081"
    echo ""
    echo "🔌 데이터베이스 연결 정보:"
    echo "   💙 MySQL Blue:      localhost:3306 (legal_user/legal_pass_2024!)"
    echo "   💚 MySQL Green:     localhost:3307 (legal_user/legal_pass_2024!)"
    echo "   🔴 Redis:           localhost:6379 (legal_redis_2024!)"
    echo ""
    echo "📡 Kafka 브로커:"
    echo "   🟢 Kafka1:         localhost:9092"
    echo "   🟢 Kafka2:         localhost:9093" 
    echo "   🟢 Kafka3:         localhost:9094"
    echo ""
    echo "💡 유용한 명령어:"
    echo "   • 로그 확인:       docker-compose logs -f [서비스명]"
    echo "   • 상태 확인:       docker-compose ps"
    echo "   • 토픽 목록:       uv run python scripts/setup_kafka_topics.py --action list"
    echo "   • 서비스 중지:     docker-compose down"
    echo ""
}

# 메인 실행 함수
main() {
    local clean_volumes=false
    local skip_setup=false
    
    # 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean-volumes)
                clean_volumes=true
                shift
                ;;
            --skip-setup)
                skip_setup=true
                shift
                ;;
            --help|-h)
                echo "사용법: $0 [옵션]"
                echo ""
                echo "옵션:"
                echo "  --clean-volumes  기존 볼륨 데이터 모두 삭제"
                echo "  --skip-setup     Kafka 토픽 설정 건너뛰기"
                echo "  --help, -h       도움말 표시"
                echo ""
                exit 0
                ;;
            *)
                log_error "알 수 없는 옵션: $1"
                echo "도움말을 보려면 $0 --help를 사용하세요."
                exit 1
                ;;
        esac
    done
    
    # 실행 단계
    echo "🔧 인프라 시작 설정:"
    echo "   • 볼륨 정리: $([ "$clean_volumes" == true ] && echo "예" || echo "아니오")"
    echo "   • 토픽 설정 건너뛰기: $([ "$skip_setup" == true ] && echo "예" || echo "아니오")"
    echo ""
    
    check_requirements
    
    if [ "$clean_volumes" == true ]; then
        cleanup_volumes --clean-volumes
    else
        cleanup_volumes
    fi
    
    create_network
    create_env_files
    start_containers
    
    if [ "$skip_setup" != true ]; then
        setup_kafka_topics
    fi
    
    check_services
    print_access_info
}

# 스크립트 실행
main "$@"
