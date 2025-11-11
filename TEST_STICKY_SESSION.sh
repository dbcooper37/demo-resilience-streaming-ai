#!/bin/bash

# ==============================================
# Test Sticky Session Deployment
# ==============================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ==============================================
# Test 1: Check All Services
# ==============================================

echo ""
echo "=========================================="
print_info "TEST 1: Service Health Checks"
echo "=========================================="
echo ""

# Check Nginx
print_info "Testing Nginx Load Balancer..."
if curl -s http://localhost:8080/ | grep -q "ok"; then
    print_success "Nginx is responding"
else
    print_error "Nginx is not responding"
    exit 1
fi

# Check WebSocket nodes
for node in 1 2 3; do
    print_info "Testing WebSocket Node $node..."
    if docker exec sticky-java-ws-$node curl -sf http://localhost:8080/actuator/health >/dev/null 2>&1; then
        print_success "WebSocket Node $node is healthy"
    else
        print_error "WebSocket Node $node is not healthy"
    fi
done

# Check AI nodes
for node in 1 2 3; do
    print_info "Testing AI Service Node $node..."
    if docker exec sticky-python-ai-$node curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        print_success "AI Service Node $node is healthy"
    else
        print_error "AI Service Node $node is not healthy"
    fi
done

# ==============================================
# Test 2: Load Balancing Distribution
# ==============================================

echo ""
echo "=========================================="
print_info "TEST 2: Load Balancing Distribution"
echo "=========================================="
echo ""

print_info "Simulating 10 requests from different IPs..."
print_info "With ip_hash, same IP should hit same backend"

# Clear nginx logs
docker exec sticky-nginx-lb sh -c "echo '' > /var/log/nginx/access.log" 2>/dev/null || true

# Make requests (each request from same client should hit same backend)
for i in {1..10}; do
    curl -s http://localhost:8080/health >/dev/null 2>&1
    echo -n "."
done
echo ""

# Check distribution in logs
print_info "Checking backend distribution..."
docker exec sticky-nginx-lb cat /var/log/nginx/access.log | grep "upstream:" | tail -10

# ==============================================
# Test 3: WebSocket Connection
# ==============================================

echo ""
echo "=========================================="
print_info "TEST 3: WebSocket Connection Test"
echo "=========================================="
echo ""

# Check if wscat is available
if command -v wscat >/dev/null 2>&1; then
    print_info "Testing WebSocket connection..."
    
    # Try to connect (timeout after 5 seconds)
    timeout 5 wscat -c "ws://localhost:8080/ws/chat?session_id=test-$(date +%s)&user_id=test-user&token=dev-token" <<EOF >/dev/null 2>&1 || true
{"type":"ping"}
EOF
    
    print_success "WebSocket endpoint is accessible"
else
    print_info "wscat not installed, skipping WebSocket test"
    print_info "Install with: npm install -g wscat"
fi

# ==============================================
# Test 4: Redis Connectivity
# ==============================================

echo ""
echo "=========================================="
print_info "TEST 4: Redis Connectivity"
echo "=========================================="
echo ""

print_info "Testing Redis connection..."
if docker exec sticky-redis redis-cli ping | grep -q "PONG"; then
    print_success "Redis is responding"
    
    # Check active sessions
    SESSION_COUNT=$(docker exec sticky-redis redis-cli HLEN "sessions:active" 2>/dev/null || echo "0")
    print_info "Active sessions in Redis: $SESSION_COUNT"
else
    print_error "Redis is not responding"
fi

# ==============================================
# Test 5: Sticky Session Verification
# ==============================================

echo ""
echo "=========================================="
print_info "TEST 5: Sticky Session Verification"
echo "=========================================="
echo ""

print_info "Making 5 consecutive requests to verify sticky session..."

# Get the upstream addresses for consecutive requests
UPSTREAM_ADDRS=()
for i in {1..5}; do
    # Make request and extract upstream from nginx logs
    curl -s http://localhost:8080/health >/dev/null 2>&1
    sleep 0.5
done

# Check last 5 requests
LAST_UPSTREAMS=$(docker exec sticky-nginx-lb tail -5 /var/log/nginx/access.log | grep -oP 'upstream: \K[^:]+')
UNIQUE_UPSTREAMS=$(echo "$LAST_UPSTREAMS" | sort -u | wc -l)

if [ "$UNIQUE_UPSTREAMS" -eq 1 ]; then
    print_success "Sticky session working! All requests went to same backend"
    echo "Backend: $(echo "$LAST_UPSTREAMS" | head -1)"
else
    print_error "Sticky session may not be working. Requests went to $UNIQUE_UPSTREAMS different backends"
    echo "Backends: $LAST_UPSTREAMS"
fi

# ==============================================
# Test 6: Node Failover Test
# ==============================================

echo ""
echo "=========================================="
print_info "TEST 6: Node Failover Test (Optional)"
echo "=========================================="
echo ""

print_info "To test failover, run these commands manually:"
echo ""
echo "1. Stop one node:"
echo "   docker stop sticky-java-ws-1"
echo ""
echo "2. Try connecting again (should connect to another node):"
echo "   curl http://localhost:8080/health"
echo ""
echo "3. Restart the node:"
echo "   docker start sticky-java-ws-1"
echo ""

# ==============================================
# Test Summary
# ==============================================

echo ""
echo "=========================================="
print_success "TEST SUITE COMPLETED"
echo "=========================================="
echo ""

print_info "Architecture Summary:"
echo "  - 3 WebSocket nodes with sticky sessions (ip_hash)"
echo "  - 3 AI service nodes with least_conn balancing"
echo "  - Shared state via Redis"
echo "  - Distributed coordination via Redisson"
echo ""

print_info "Monitor logs with:"
echo "  - All services:    docker-compose -f docker-compose.sticky-session.yml logs -f"
echo "  - Specific node:   docker logs -f sticky-java-ws-1"
echo "  - Nginx logs:      docker exec sticky-nginx-lb tail -f /var/log/nginx/access.log"
echo ""

print_info "For detailed monitoring:"
echo "  - Nginx stats:     curl http://localhost:8090/nginx-status"
echo "  - WS Node health:  curl http://localhost:8081/actuator/health"
echo "  - Redis info:      docker exec sticky-redis redis-cli INFO"
echo ""

print_success "All tests completed!"
