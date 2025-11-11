#!/bin/bash

# Quick Start Script for Multi-Node Deployment
# This script handles the proper startup sequence to avoid circular dependencies

set -e

echo "=========================================="
echo "Multi-Node Deployment - Quick Start"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Stop any running containers
echo -e "${YELLOW}Step 1: Stopping existing containers...${NC}"
docker-compose -f docker-compose.multi-node.yml down
echo ""

# Step 2: Start core infrastructure first
echo -e "${YELLOW}Step 2: Starting core infrastructure (Redis, Kafka)...${NC}"
docker-compose -f docker-compose.multi-node.yml up -d redis kafka
echo "Waiting for services to be healthy..."
sleep 10
echo ""

# Step 3: Start AI services
echo -e "${YELLOW}Step 3: Starting AI services (python-ai-1, python-ai-2, python-ai-3)...${NC}"
docker-compose -f docker-compose.multi-node.yml up -d python-ai-1 python-ai-2 python-ai-3
echo "Waiting for AI services to be ready..."
sleep 15
echo ""

# Step 4: Start NGINX Load Balancer
echo -e "${YELLOW}Step 4: Starting NGINX Load Balancer...${NC}"
docker-compose -f docker-compose.multi-node.yml up -d nginx-lb
echo "Waiting for NGINX to be ready..."
sleep 5
echo ""

# Step 5: Start Java WebSocket services
echo -e "${YELLOW}Step 5: Starting Java WebSocket services...${NC}"
docker-compose -f docker-compose.multi-node.yml up -d java-websocket-1 java-websocket-2 java-websocket-3
echo "Waiting for Java services to be ready..."
sleep 20
echo ""

# Step 6: Start frontend
echo -e "${YELLOW}Step 6: Starting frontend...${NC}"
docker-compose -f docker-compose.multi-node.yml up -d frontend
echo ""

# Step 7: Check status
echo -e "${YELLOW}Step 7: Checking service status...${NC}"
docker-compose -f docker-compose.multi-node.yml ps
echo ""

echo "=========================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "=========================================="
echo ""
echo "Services are starting up. Wait a few moments then run:"
echo ""
echo "  ./test_multinode_connectivity.sh"
echo ""
echo "To check the status and test connectivity."
echo ""
echo "Access points:"
echo "  - Frontend:     http://localhost:3000"
echo "  - NGINX LB:     http://localhost:8080"
echo "  - Java Node 1:  http://localhost:8081"
echo "  - Java Node 2:  http://localhost:8082"
echo "  - Java Node 3:  http://localhost:8083"
echo "  - AI Service 1: http://localhost:8001"
echo "  - AI Service 2: http://localhost:8002"
echo "  - AI Service 3: http://localhost:8003"
echo ""
echo "View logs:"
echo "  docker-compose -f docker-compose.multi-node.yml logs -f [service-name]"
echo ""
