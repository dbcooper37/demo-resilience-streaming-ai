#!/bin/bash

echo "================================================"
echo "   WebSocket Fixes - Quick Apply Script"
echo "================================================"
echo ""
echo "Fixes to apply:"
echo "1. ✅ TEXT_PARTIAL_WRITING error (Java)"
echo "2. ✅ Message already completed error (Python)"
echo ""
echo "Files modified:"
echo "  - java-websocket-server/.../ChatWebSocketHandler.java"
echo "  - python-ai-service/ai_service.py"
echo ""
echo "================================================"
echo ""

read -p "Proceed with rebuild? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Step 1: Building Java WebSocket Server..."
echo "-------------------------------------------"
docker-compose build java-websocket-server

if [ $? -ne 0 ]; then
    echo "❌ Java build failed!"
    exit 1
fi
echo "✅ Java build successful"

echo ""
echo "Step 2: Building Python AI Service..."
echo "-------------------------------------------"
docker-compose build python-ai-service

if [ $? -ne 0 ]; then
    echo "❌ Python build failed!"
    exit 1
fi
echo "✅ Python build successful"

echo ""
echo "Step 3: Restarting services..."
echo "-------------------------------------------"
docker-compose down
sleep 2
docker-compose up -d redis java-websocket-server python-ai-service

echo ""
echo "Waiting for services to start..."
sleep 10

echo ""
echo "Step 4: Health checks..."
echo "-------------------------------------------"

# Java
if curl -s http://localhost:8080/health | grep -q "UP"; then
    echo "✅ Java WebSocket Server: Healthy"
else
    echo "⚠️  Java WebSocket Server: Check logs"
    docker-compose logs --tail=20 java-websocket-server
fi

# Python
if curl -s http://localhost:5001/health | grep -q "healthy"; then
    echo "✅ Python AI Service: Healthy"
else
    echo "⚠️  Python AI Service: Check logs"
    docker-compose logs --tail=20 python-ai-service
fi

echo ""
echo "================================================"
echo "   ✅ Deployment Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Open frontend: http://localhost:3000"
echo "2. Test sending multiple messages rapidly"
echo "3. Test cancelling messages multiple times"
echo "4. Check logs for errors:"
echo "   docker-compose logs -f java-websocket-server python-ai-service"
echo ""
echo "Documentation:"
echo "  - Quick Guide: ./QUICK_FIX_GUIDE.md"
echo "  - Summary: ./FIX_SUMMARY.md"
echo "  - Details: ./WEBSOCKET_SYNC_FIX.md"
echo ""
