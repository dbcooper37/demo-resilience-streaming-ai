#!/bin/bash

# ==============================================
# Deploy Multi-Node with Sticky Sessions
# ==============================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ==============================================
# Pre-flight Checks
# ==============================================

print_info "Starting deployment checks..."

# Check Docker
if ! command_exists docker; then
    print_error "Docker is not installed!"
    exit 1
fi

# Check Docker Compose
if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
    print_error "Docker Compose is not installed!"
    exit 1
fi

# Determine docker-compose command
if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

print_success "Docker and Docker Compose are available"

# ==============================================
# Clean up existing deployment
# ==============================================

print_info "Cleaning up existing containers..."
$DOCKER_COMPOSE -f docker-compose.sticky-session.yml down -v 2>/dev/null || true
print_success "Cleanup completed"

# ==============================================
# Build Images
# ==============================================

print_info "Building Docker images..."
$DOCKER_COMPOSE -f docker-compose.sticky-session.yml build --no-cache

if [ $? -eq 0 ]; then
    print_success "Images built successfully"
else
    print_error "Image build failed!"
    exit 1
fi

# ==============================================
# Start Services
# ==============================================

print_info "Starting services..."
$DOCKER_COMPOSE -f docker-compose.sticky-session.yml up -d

if [ $? -eq 0 ]; then
    print_success "Services started successfully"
else
    print_error "Failed to start services!"
    exit 1
fi

# ==============================================
# Wait for Services to be Healthy
# ==============================================

print_info "Waiting for services to be healthy..."

# Wait for Redis
print_info "Checking Redis..."
for i in {1..30}; do
    if docker exec sticky-redis redis-cli ping >/dev/null 2>&1; then
        print_success "Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Redis failed to start"
        exit 1
    fi
    sleep 2
done

# Wait for Kafka
print_info "Checking Kafka..."
sleep 10  # Kafka needs more time to initialize
for i in {1..60}; do
    if docker exec sticky-kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092 >/dev/null 2>&1; then
        print_success "Kafka is ready"
        break
    fi
    if [ $i -eq 60 ]; then
        print_warning "Kafka check timed out, but continuing..."
        break
    fi
    sleep 2
done

# Wait for WebSocket servers
print_info "Checking WebSocket servers..."
sleep 15  # Give Java apps time to start

for node in 1 2 3; do
    print_info "Checking WebSocket Node $node..."
    for i in {1..60}; do
        if docker exec sticky-java-ws-$node curl -f http://localhost:8080/actuator/health >/dev/null 2>&1; then
            print_success "WebSocket Node $node is ready"
            break
        fi
        if [ $i -eq 60 ]; then
            print_warning "WebSocket Node $node health check timed out"
        fi
        sleep 2
    done
done

# Wait for Nginx
print_info "Checking Nginx Load Balancer..."
for i in {1..30}; do
    if curl -f http://localhost:8080/ >/dev/null 2>&1; then
        print_success "Nginx Load Balancer is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "Nginx failed to start"
        exit 1
    fi
    sleep 2
done

# ==============================================
# Deployment Summary
# ==============================================

echo ""
echo "=========================================="
print_success "DEPLOYMENT COMPLETED SUCCESSFULLY"
echo "=========================================="
echo ""
print_info "Service URLs:"
echo "  - Frontend:          http://localhost:3000"
echo "  - Load Balancer:     http://localhost:8080"
echo "  - WebSocket:         ws://localhost:8080/ws/chat"
echo "  - API:               http://localhost:8080/api"
echo "  - Nginx Status:      http://localhost:8090/nginx-status"
echo ""
print_info "Backend Nodes (Direct Access):"
echo "  - WebSocket Node 1:  http://localhost:8081 (container: sticky-java-ws-1)"
echo "  - WebSocket Node 2:  http://localhost:8082 (container: sticky-java-ws-2)"
echo "  - WebSocket Node 3:  http://localhost:8083 (container: sticky-java-ws-3)"
echo "  - AI Service 1:      http://localhost:8001 (container: sticky-python-ai-1)"
echo "  - AI Service 2:      http://localhost:8002 (container: sticky-python-ai-2)"
echo "  - AI Service 3:      http://localhost:8003 (container: sticky-python-ai-3)"
echo ""
print_info "Infrastructure:"
echo "  - Redis:             localhost:6379"
echo "  - Kafka:             localhost:9092"
echo ""
print_info "Useful Commands:"
echo "  - View logs:         $DOCKER_COMPOSE -f docker-compose.sticky-session.yml logs -f"
echo "  - Stop services:     $DOCKER_COMPOSE -f docker-compose.sticky-session.yml down"
echo "  - Restart service:   $DOCKER_COMPOSE -f docker-compose.sticky-session.yml restart <service>"
echo "  - Check status:      $DOCKER_COMPOSE -f docker-compose.sticky-session.yml ps"
echo ""
print_info "Test sticky sessions:"
echo "  - Run:               ./TEST_STICKY_SESSION.sh"
echo ""

# ==============================================
# Optional: Show container status
# ==============================================

print_info "Container Status:"
$DOCKER_COMPOSE -f docker-compose.sticky-session.yml ps

echo ""
print_success "Deployment script completed!"
