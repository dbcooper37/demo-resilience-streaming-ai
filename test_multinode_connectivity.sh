#!/bin/bash

# Script to verify multi-node connectivity between services
# Tests: Java WebSocket -> NGINX LB -> AI Services

set -e

echo "=========================================="
echo "Multi-Node Service Connectivity Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if service is healthy
check_service() {
    local service_name=$1
    local health_url=$2
    local max_retries=30
    local retry_count=0
    
    echo -n "Checking $service_name... "
    
    while [ $retry_count -lt $max_retries ]; do
        if curl -f -s "$health_url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Healthy${NC}"
            return 0
        fi
        retry_count=$((retry_count + 1))
        sleep 2
    done
    
    echo -e "${RED}✗ Unhealthy${NC}"
    return 1
}

# Function to test AI service directly
test_ai_service() {
    local service_name=$1
    local port=$2
    
    echo -n "Testing $service_name (localhost:$port)... "
    
    response=$(curl -s -X POST "http://localhost:$port/chat" \
        -H "Content-Type: application/json" \
        -d '{"message":"test","session_id":"test-session"}' 2>&1)
    
    if echo "$response" | grep -q "session_id"; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed${NC}"
        echo "Response: $response"
        return 1
    fi
}

# Function to test AI services via NGINX load balancer
test_nginx_ai_lb() {
    echo -n "Testing NGINX AI Load Balancer (localhost:8080/ai/)... "
    
    response=$(curl -s -X POST "http://localhost:8080/ai/chat" \
        -H "Content-Type: application/json" \
        -d '{"message":"test via nginx","session_id":"test-nginx"}' 2>&1)
    
    if echo "$response" | grep -q "session_id"; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed${NC}"
        echo "Response: $response"
        return 1
    fi
}

# Function to test Java WebSocket -> AI via NGINX
test_java_to_ai() {
    local java_port=$1
    local node_name=$2
    
    echo -n "Testing Java $node_name -> NGINX -> AI (localhost:$java_port)... "
    
    # First authenticate to get JWT token
    auth_response=$(curl -s -X POST "http://localhost:$java_port/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username":"testuser","password":"testpass"}' 2>&1)
    
    if ! echo "$auth_response" | grep -q "token"; then
        echo -e "${YELLOW}! Auth failed, trying chat without token${NC}"
        # Try direct chat endpoint if auth fails
        response=$(curl -s -X POST "http://localhost:$java_port/api/chat" \
            -H "Content-Type: application/json" \
            -d '{"message":"test from java","sessionId":"test-java-'$node_name'"}' 2>&1)
    else
        token=$(echo "$auth_response" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
        response=$(curl -s -X POST "http://localhost:$java_port/api/chat" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $token" \
            -d '{"message":"test from java","sessionId":"test-java-'$node_name'"}' 2>&1)
    fi
    
    if echo "$response" | grep -q -E "(response|session_id|message)"; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed${NC}"
        echo "Response: $response"
        return 1
    fi
}

echo "Step 1: Checking Core Services Health"
echo "--------------------------------------"
check_service "Redis" "http://localhost:6379"
check_service "NGINX Load Balancer" "http://localhost:8080/health"
echo ""

echo "Step 2: Checking AI Services Health"
echo "------------------------------------"
check_service "Python AI Service 1" "http://localhost:8001/health"
check_service "Python AI Service 2" "http://localhost:8002/health"
check_service "Python AI Service 3" "http://localhost:8003/health"
echo ""

echo "Step 3: Checking Java WebSocket Services Health"
echo "-----------------------------------------------"
check_service "Java WebSocket 1" "http://localhost:8081/actuator/health"
check_service "Java WebSocket 2" "http://localhost:8082/actuator/health"
check_service "Java WebSocket 3" "http://localhost:8083/actuator/health"
echo ""

echo "Step 4: Testing Direct AI Service Access"
echo "-----------------------------------------"
test_ai_service "Python AI 1" 8001
test_ai_service "Python AI 2" 8002
test_ai_service "Python AI 3" 8003
echo ""

echo "Step 5: Testing NGINX AI Load Balancer"
echo "---------------------------------------"
test_nginx_ai_lb
echo ""

echo "Step 6: Testing Java -> NGINX -> AI Connectivity"
echo "-------------------------------------------------"
test_java_to_ai 8081 "Node-1"
test_java_to_ai 8082 "Node-2"
test_java_to_ai 8083 "Node-3"
echo ""

echo "=========================================="
echo "Step 7: Checking Environment Variables"
echo "=========================================="
echo "Checking AI_SERVICE_URL in Java containers..."

for i in 1 2 3; do
    echo -n "Java WebSocket Node $i: "
    ai_url=$(docker exec demo-java-websocket-$i printenv AI_SERVICE_URL 2>/dev/null || echo "NOT SET")
    if [ "$ai_url" = "http://nginx-lb:80/ai" ]; then
        echo -e "${GREEN}✓ $ai_url${NC}"
    else
        echo -e "${RED}✗ $ai_url${NC}"
    fi
done
echo ""

echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo -e "${YELLOW}Notes:${NC}"
echo "- If authentication fails, the script tries to test chat endpoint directly"
echo "- Java services should connect to AI via: http://nginx-lb:80/ai"
echo "- NGINX load balances requests across all 3 AI service instances"
echo ""
echo "To view logs:"
echo "  docker-compose -f docker-compose.multi-node.yml logs -f java-websocket-1"
echo "  docker-compose -f docker-compose.multi-node.yml logs -f nginx-lb"
echo "  docker-compose -f docker-compose.multi-node.yml logs -f python-ai-1"
