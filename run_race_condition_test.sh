#!/bin/bash
set -e

echo "=================================="
echo "Race Condition Test Runner"
echo "=================================="
echo ""

# Check if Redis is running
echo "1. Checking Redis connection..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running!"
    echo "   Please start Redis: docker-compose up -d redis"
    exit 1
fi
echo "✓ Redis is running"
echo ""

# Check if Java WebSocket server is running
echo "2. Checking Java WebSocket server..."
if ! curl -s http://localhost:8080/actuator/health > /dev/null 2>&1; then
    echo "❌ Java WebSocket server is not running!"
    echo "   Please start it: docker-compose up -d java-websocket-1"
    exit 1
fi
echo "✓ Java WebSocket server is running"
echo ""

# Install Python dependencies if needed
echo "3. Checking Python dependencies..."
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "Installing websockets..."
    pip3 install websockets redis
fi
echo "✓ Dependencies ready"
echo ""

# Run the simple simulation test first
echo "=================================="
echo "Running Simple Simulation Test"
echo "=================================="
echo ""
python3 test_race_condition.py
echo ""

# Wait a bit
sleep 2

# Run the integrated test with real WebSocket
echo "=================================="
echo "Running Integrated WebSocket Test"
echo "=================================="
echo ""
python3 test_integrated_race_condition.py

echo ""
echo "=================================="
echo "All tests completed!"
echo "=================================="
