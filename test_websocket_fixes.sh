#!/bin/bash

# Test script for WebSocket synchronization and cancellation fixes

echo "========================================="
echo "Testing WebSocket Fixes"
echo "========================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "Step 1: Rebuild services with fixes..."
echo "----------------------------------------"
docker-compose build java-websocket-server python-ai-service

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build successful${NC}"

echo ""
echo "Step 2: Restart services..."
echo "----------------------------------------"
docker-compose down
docker-compose up -d redis java-websocket-server python-ai-service

# Wait for services to start
echo "Waiting for services to be ready..."
sleep 10

echo ""
echo "Step 3: Check service health..."
echo "----------------------------------------"

# Check Java WebSocket Server
echo -n "Checking Java WebSocket Server... "
if curl -s http://localhost:8080/health | grep -q "UP"; then
    echo -e "${GREEN}✅ Healthy${NC}"
else
    echo -e "${RED}❌ Not healthy${NC}"
fi

# Check Python AI Service
echo -n "Checking Python AI Service... "
if curl -s http://localhost:5001/health | grep -q "healthy"; then
    echo -e "${GREEN}✅ Healthy${NC}"
else
    echo -e "${RED}❌ Not healthy${NC}"
fi

# Check Redis
echo -n "Checking Redis... "
if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✅ Running${NC}"
else
    echo -e "${RED}❌ Not running${NC}"
fi

echo ""
echo "========================================="
echo "Manual Testing Instructions"
echo "========================================="
echo ""
echo "Test 1: TEXT_PARTIAL_WRITING Fix"
echo "--------------------------------"
echo "1. Open frontend: http://localhost:3000"
echo "2. Send multiple messages rapidly (5-10 messages)"
echo "3. While AI is responding, send more messages"
echo "4. ${GREEN}Expected: No 'TEXT_PARTIAL_WRITING' errors in logs${NC}"
echo ""
echo "   Check logs with:"
echo "   docker-compose logs -f java-websocket-server | grep -i 'partial'"
echo ""

echo "Test 2: Message Already Completed Fix"
echo "------------------------------------"
echo "1. Open frontend: http://localhost:3000"
echo "2. Send a message (AI will stream response)"
echo "3. Click the 'Cancel' or 'Stop' button multiple times rapidly"
echo "4. ${GREEN}Expected: No 'Message already completed' error${NC}"
echo "5. ${GREEN}Expected: Message cancels gracefully on first click${NC}"
echo ""
echo "   Check logs with:"
echo "   docker-compose logs -f python-ai-service | grep -i 'cancel'"
echo ""

echo "Test 3: Concurrent Operations"
echo "----------------------------"
echo "1. Open 2-3 browser tabs with frontend"
echo "2. Send messages from all tabs simultaneously"
echo "3. Try cancelling messages from different tabs"
echo "4. ${GREEN}Expected: All operations work without errors${NC}"
echo ""

echo "========================================="
echo "Monitoring Commands"
echo "========================================="
echo ""
echo "# Watch all logs:"
echo "docker-compose logs -f"
echo ""
echo "# Watch for WebSocket errors:"
echo "docker-compose logs -f java-websocket-server | grep -i 'error\\|exception\\|partial'"
echo ""
echo "# Watch for cancellation handling:"
echo "docker-compose logs -f python-ai-service | grep -i 'cancel\\|completed'"
echo ""
echo "# Check Redis PubSub activity:"
echo "docker-compose exec redis redis-cli PUBSUB CHANNELS"
echo ""

echo "========================================="
echo "Quick Verification Tests"
echo "========================================="
echo ""

SESSION_ID="test-$(date +%s)"
USER_ID="test-user"

echo "Test 4: Send a test message..."
echo "------------------------------"
RESPONSE=$(curl -s -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"${SESSION_ID}\", \"user_id\": \"${USER_ID}\", \"message\": \"Test streaming\"}")

if echo "$RESPONSE" | grep -q "streaming"; then
    echo -e "${GREEN}✅ Chat endpoint working${NC}"
    MESSAGE_ID=$(echo "$RESPONSE" | grep -o '"message_id":"[^"]*"' | cut -d'"' -f4)
    echo "Message ID: $MESSAGE_ID"
    
    # Wait a bit for streaming to start
    sleep 2
    
    echo ""
    echo "Test 5: Cancel the message..."
    echo "---------------------------"
    CANCEL_RESPONSE=$(curl -s -X POST http://localhost:5001/cancel \
      -H "Content-Type: application/json" \
      -d "{\"session_id\": \"${SESSION_ID}\", \"message_id\": \"${MESSAGE_ID}\"}")
    
    echo "Cancel response: $CANCEL_RESPONSE"
    
    # Try cancelling again (should not error)
    sleep 1
    echo ""
    echo "Test 6: Cancel again (should handle gracefully)..."
    echo "------------------------------------------------"
    CANCEL_RESPONSE2=$(curl -s -X POST http://localhost:5001/cancel \
      -H "Content-Type: application/json" \
      -d "{\"session_id\": \"${SESSION_ID}\", \"message_id\": \"${MESSAGE_ID}\"}")
    
    echo "Second cancel response: $CANCEL_RESPONSE2"
    
    if echo "$CANCEL_RESPONSE2" | grep -q '"status":"not_found"'; then
        echo -e "${YELLOW}⚠️  Old behavior: Message not found${NC}"
    elif echo "$CANCEL_RESPONSE2" | grep -q '"status":"cancelled"'; then
        echo -e "${GREEN}✅ New behavior: Gracefully handled${NC}"
    fi
else
    echo -e "${RED}❌ Chat endpoint not working${NC}"
    echo "Response: $RESPONSE"
fi

echo ""
echo "========================================="
echo "Summary"
echo "========================================="
echo ""
echo "Fixes Applied:"
echo "1. ✅ Added per-session locks for WebSocket writes"
echo "2. ✅ Synchronized all WebSocket sendMessage() calls"
echo "3. ✅ Track completed messages for 30 seconds"
echo "4. ✅ Enhanced cancellation logic"
echo ""
echo "Next Steps:"
echo "- Test manually using the frontend"
echo "- Monitor logs for any errors"
echo "- Verify concurrent operations work correctly"
echo ""
echo "Frontend URL: http://localhost:3000"
echo "Java API: http://localhost:8080"
echo "Python API: http://localhost:5001"
echo ""
