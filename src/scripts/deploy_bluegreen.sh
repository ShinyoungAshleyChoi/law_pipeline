#!/bin/bash

# Blue-Green Deployment Script for Legal Data Pipeline
# Usage: ./deploy_bluegreen.sh [deploy|rollback|status] [options]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
BLUEGREEN_COMPOSE_FILE="$PROJECT_DIR/deployment/docker-compose.bluegreen.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose is not installed."
        exit 1
    fi
    
    # Check if UV is available for deployment management
    if ! command -v uv >/dev/null 2>&1; then
        log_error "UV is not installed. Please install UV first: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Setup infrastructure
setup_infrastructure() {
    log_info "Setting up infrastructure..."
    
    cd "$PROJECT_DIR"
    
    # Create network if it doesn't exist
    if ! docker network ls | grep -q "legal-network"; then
        log_info "Creating Docker network..."
        docker network create legal-network
    fi
    
    # Start base infrastructure (MySQL, Redis, Kafka, etc.)
    log_info "Starting base infrastructure..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up -d zookeeper kafka1 kafka2 kafka3 mysql-blue mysql-green redis prometheus grafana
    
    # Wait for services to be healthy
    log_info "Waiting for infrastructure to be ready..."
    sleep 30
    
    # Check MySQL connections
    for env in blue green; do
        port=$([[ $env == "blue" ]] && echo "3306" || echo "3307")
        log_info "Checking MySQL $env connection..."
        
        max_attempts=30
        attempt=1
        while ! docker exec legal-mysql-$env mysqladmin ping -h localhost -u legal_user -plegal_pass_2024! --silent 2>/dev/null; do
            if [ $attempt -eq $max_attempts ]; then
                log_error "MySQL $env did not become ready in time"
                exit 1
            fi
            log_info "Waiting for MySQL $env... (attempt $attempt/$max_attempts)"
            sleep 2
            ((attempt++))
        done
        log_success "MySQL $env is ready"
    done
    
    log_success "Infrastructure setup completed"
}

# Deploy application
deploy() {
    local version=${1:-"latest"}
    local skip_sync=${2:-false}
    
    log_info "Starting Blue-Green deployment (version: $version)..."
    
    cd "$PROJECT_DIR"
    
    # Setup infrastructure first
    setup_infrastructure
    
    # Start blue-green deployment services
    log_info "Starting Blue-Green deployment services..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" -f "$BLUEGREEN_COMPOSE_FILE" up -d
    
    # Wait for applications to start
    log_info "Waiting for applications to start..."
    sleep 15
    
    # Run deployment script with UV
    log_info "Executing deployment logic..."
    
    cd "$PROJECT_DIR/deployment"
    
    # Ensure UV environment is set up
    if [ ! -f "uv.lock" ]; then
        log_info "Setting up UV environment..."
        uv sync
    fi
    
    if [ "$skip_sync" = "true" ]; then
        uv run python blue_green_deploy.py deploy --version "$version" --skip-sync
    else
        uv run python blue_green_deploy.py deploy --version "$version"
    fi
    
    deployment_exit_code=$?
    
    if [ $deployment_exit_code -eq 0 ]; then
        log_success "Blue-Green deployment completed successfully!"
        
        # Show status
        get_status
        
        # Show access information
        log_info "Application is now accessible at:"
        log_info "  - Main API: http://localhost:80"
        log_info "  - Health check: http://localhost:80/health"
        log_info "  - Blue environment: http://localhost:8001"
        log_info "  - Green environment: http://localhost:8002"
        log_info "  - Deployment API: http://localhost:9000"
        
    else
        log_error "Blue-Green deployment failed!"
        exit $deployment_exit_code
    fi
}

# Rollback deployment
rollback() {
    log_info "Starting rollback process..."
    
    cd "$PROJECT_DIR/deployment"
    
    # Execute rollback with UV
    uv run python blue_green_deploy.py rollback
    
    rollback_exit_code=$?
    
    if [ $rollback_exit_code -eq 0 ]; then
        log_success "Rollback completed successfully!"
        get_status
    else
        log_error "Rollback failed!"
        exit $rollback_exit_code
    fi
}

# Get deployment status
get_status() {
    log_info "Getting deployment status..."
    
    cd "$PROJECT_DIR/deployment"
    
    # Get status from deployment manager with UV
    uv run python blue_green_deploy.py status
    
    # Show Docker container status
    echo ""
    log_info "Docker containers status:"
    docker-compose -f "$DOCKER_COMPOSE_FILE" -f "$BLUEGREEN_COMPOSE_FILE" ps
    
    # Show health checks
    echo ""
    log_info "Application health checks:"
    
    check_url() {
        local url=$1
        local name=$2
        if curl -s -f "$url" > /dev/null 2>&1; then
            log_success "$name: ✅ Healthy"
        else
            log_error "$name: ❌ Unhealthy"
        fi
    }
    
    check_url "http://localhost:8001/health" "Blue Environment"
    check_url "http://localhost:8002/health" "Green Environment"
    check_url "http://localhost:80/health" "Load Balancer"
}

# Stop all services
stop() {
    log_info "Stopping all Blue-Green deployment services..."
    
    cd "$PROJECT_DIR"
    
    # Stop blue-green services
    docker-compose -f "$DOCKER_COMPOSE_FILE" -f "$BLUEGREEN_COMPOSE_FILE" down
    
    # Stop base infrastructure
    docker-compose -f "$DOCKER_COMPOSE_FILE" down
    
    log_success "All services stopped"
}

# Clean up everything
cleanup() {
    log_warning "This will remove all containers, volumes, and networks!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleaning up..."
        
        cd "$PROJECT_DIR"
        
        # Stop and remove everything
        docker-compose -f "$DOCKER_COMPOSE_FILE" -f "$BLUEGREEN_COMPOSE_FILE" down -v --remove-orphans
        
        # Remove network
        docker network rm legal-network 2>/dev/null || true
        
        # Remove volumes
        docker volume prune -f
        
        log_success "Cleanup completed"
    else
        log_info "Cleanup cancelled"
    fi
}

# Show logs
show_logs() {
    local service=${1:-""}
    
    cd "$PROJECT_DIR"
    
    if [ -z "$service" ]; then
        log_info "Showing logs for all services..."
        docker-compose -f "$DOCKER_COMPOSE_FILE" -f "$BLUEGREEN_COMPOSE_FILE" logs -f --tail=50
    else
        log_info "Showing logs for service: $service"
        docker-compose -f "$DOCKER_COMPOSE_FILE" -f "$BLUEGREEN_COMPOSE_FILE" logs -f --tail=50 "$service"
    fi
}

# Main script logic
main() {
    local command=${1:-"help"}
    
    case $command in
        "deploy")
            check_prerequisites
            deploy "${2:-latest}" "${3:-false}"
            ;;
        "rollback") 
            check_prerequisites
            rollback
            ;;
        "status")
            get_status
            ;;
        "stop")
            stop
            ;;
        "cleanup")
            cleanup
            ;;
        "logs")
            show_logs "$2"
            ;;
        "setup")
            check_prerequisites
            setup_infrastructure
            ;;
        "help"|*)
            echo ""
            echo "Legal Data Pipeline - Blue-Green Deployment Script"
            echo ""
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  deploy [version] [skip-sync]  Deploy application (default version: latest)"
            echo "  rollback                      Rollback to previous environment"
            echo "  status                        Show deployment status"
            echo "  setup                         Setup infrastructure only"
            echo "  stop                          Stop all services"
            echo "  cleanup                       Remove all containers and volumes"
            echo "  logs [service]               Show logs (all services or specific service)"
            echo "  help                         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 deploy v1.2.0             Deploy version 1.2.0"
            echo "  $0 deploy latest true         Deploy latest version, skip DB sync"
            echo "  $0 rollback                   Rollback deployment"
            echo "  $0 status                     Check deployment status"
            echo "  $0 logs app-blue              Show logs for blue app"
            echo ""
            ;;
    esac
}

# Run main function with all arguments
main "$@"
