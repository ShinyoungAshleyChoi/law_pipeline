#!/bin/bash

# 법제처 데이터 파이프라인 인프라 중지 스크립트
set -e

echo "🛑 법제처 데이터 파이프라인 인프라 중지"

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

# 인프라 중지
stop_infrastructure() {
    log_info "Docker Compose 서비스 중지 중..."
    
    # 순서대로 중지 (애플리케이션 → 데이터 서비스 → 인프라)
    log_info "1. 애플리케이션 서비스 중지..."
    # docker-compose stop legal-api legal-producer legal-consumer 2>/dev/null || true
    
    log_info "2. 모니터링 서비스 중지..."
    docker-compose stop grafana prometheus 2>/dev/null || true
    
    log_info "3. UI 및 관리 도구 중지..."
    docker-compose stop kafka-ui schema-registry 2>/dev/null || true
    
    log_info "4. 데이터 서비스 중지..."
    docker-compose stop mysql-blue mysql-green redis 2>/dev/null || true
    
    log_info "5. Kafka 클러스터 중지..."
    docker-compose stop kafka1 kafka2 kafka3 2>/dev/null || true
    
    log_info "6. Zookeeper 중지..."
    docker-compose stop zookeeper 2>/dev/null || true
    
    log_info "모든 서비스 중지 완료"
}

# 컨테이너 제거
remove_containers() {
    log_info "컨테이너 제거 중..."
    docker-compose down --remove-orphans
    log_info "컨테이너 제거 완료"
}

# 볼륨 제거
remove_volumes() {
    log_warn "데이터 볼륨 제거 중... (데이터가 영구 삭제됩니다)"
    
    # 사용자 확인
    read -p "정말로 모든 데이터를 삭제하시겠습니까? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "볼륨 제거가 취소되었습니다."
        return
    fi
    
    # 볼륨 제거
    docker-compose down -v
    
    # 프로젝트별 볼륨 직접 제거
    volumes=(
        "legal_zookeeper_data"
        "legal_zookeeper_logs"
        "legal_kafka1_data"
        "legal_kafka2_data"
        "legal_kafka3_data"
        "legal_mysql_blue_data"
        "legal_mysql_blue_logs"
        "legal_mysql_green_data"
        "legal_mysql_green_logs"
        "legal_redis_data"
        "legal_prometheus_data"
        "legal_grafana_data"
    )
    
    for volume in "${volumes[@]}"; do
        if docker volume inspect "$volume" >/dev/null 2>&1; then
            docker volume rm "$volume" 2>/dev/null || log_warn "볼륨 $volume 제거 실패"
            log_info "볼륨 $volume 제거 완료"
        fi
    done
    
    log_info "볼륨 제거 완료"
}

# 네트워크 제거
remove_networks() {
    log_info "네트워크 제거 중..."
    
    if docker network inspect legal-network >/dev/null 2>&1; then
        docker network rm legal-network 2>/dev/null || log_warn "네트워크 legal-network 제거 실패"
        log_info "네트워크 legal-network 제거 완료"
    fi
}

# 사용하지 않는 Docker 리소스 정리
cleanup_docker() {
    log_info "사용하지 않는 Docker 리소스 정리 중..."
    
    # 사용자 확인
    read -p "사용하지 않는 Docker 리소스를 정리하시겠습니까? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Docker 리소스 정리가 취소되었습니다."
        return
    fi
    
    # 정리 실행
    docker system prune -f
    docker volume prune -f
    docker network prune -f
    
    log_info "Docker 리소스 정리 완료"
}

# 상태 확인
check_status() {
    log_info "인프라 중지 상태 확인 중..."
    
    # 실행 중인 컨테이너 확인
    running_containers=$(docker-compose ps -q 2>/dev/null | wc -l)
    
    if [ "$running_containers" -eq 0 ]; then
        log_info "✅ 모든 컨테이너가 중지되었습니다."
    else
        log_warn "⚠️  일부 컨테이너가 여전히 실행 중입니다."
        docker-compose ps
    fi
    
    # 포트 사용 확인
    ports=("2181" "9092" "9093" "9094" "3306" "3307" "6379" "8080" "8081" "9090" "3000")
    
    for port in "${ports[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            log_warn "⚠️  포트 $port가 여전히 사용 중입니다."
        fi
    done
}

# 메인 실행 함수
main() {
    local remove_volumes_flag=false
    local remove_all=false
    local cleanup_flag=false
    
    # 인자 처리
    while [[ $# -gt 0 ]]; do
        case $1 in
            --remove-volumes)
                remove_volumes_flag=true
                shift
                ;;
            --remove-all)
                remove_all=true
                shift
                ;;
            --cleanup)
                cleanup_flag=true
                shift
                ;;
            --help|-h)
                echo "사용법: $0 [옵션]"
                echo ""
                echo "옵션:"
                echo "  --remove-volumes  데이터 볼륨도 함께 제거"
                echo "  --remove-all      볼륨, 네트워크 모두 제거"
                echo "  --cleanup         사용하지 않는 Docker 리소스 정리"
                echo "  --help, -h        도움말 표시"
                echo ""
                echo "예시:"
                echo "  $0                 # 컨테이너만 중지"
                echo "  $0 --remove-all    # 모든 리소스 제거"
                echo "  $0 --cleanup       # Docker 시스템 정리까지"
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
    
    # 실행 단계 표시
    echo "🔧 인프라 중지 설정:"
    echo "   • 볼륨 제거: $([ "$remove_volumes_flag" == true ] || [ "$remove_all" == true ] && echo "예" || echo "아니오")"
    echo "   • 네트워크 제거: $([ "$remove_all" == true ] && echo "예" || echo "아니오")"
    echo "   • Docker 정리: $([ "$cleanup_flag" == true ] && echo "예" || echo "아니오")"
    echo ""
    
    # 실행
    stop_infrastructure
    remove_containers
    
    if [ "$remove_volumes_flag" == true ] || [ "$remove_all" == true ]; then
        remove_volumes
    fi
    
    if [ "$remove_all" == true ]; then
        remove_networks
    fi
    
    if [ "$cleanup_flag" == true ]; then
        cleanup_docker
    fi
    
    check_status
    
    echo ""
    echo "🎉 인프라 중지 완료!"
    echo ""
    
    if [ "$remove_volumes_flag" == true ] || [ "$remove_all" == true ]; then
        echo "⚠️  데이터가 모두 삭제되었습니다."
    else
        echo "💾 데이터가 보존되었습니다."
    fi
    echo ""
}

# 인터럽트 핸들러
cleanup_on_exit() {
    echo ""
    log_warn "스크립트가 중단되었습니다."
    exit 1
}

# 시그널 핸들러 등록
trap cleanup_on_exit SIGINT SIGTERM

# 스크립트 실행
main "$@"
