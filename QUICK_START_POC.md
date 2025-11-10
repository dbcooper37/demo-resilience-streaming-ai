# 🚀 Quick Start - PoC Mode

Guide nhanh để chạy hệ thống ở chế độ PoC (Proof of Concept).

---

## 🎯 PoC Mode Features

- ✅ **Kafka KRaft** - Không cần Zookeeper (bản mới nhất)
- ✅ **Simple Logging** - Metrics chỉ log ra console (không cần Prometheus/Grafana)
- ✅ **Lightweight** - Cấu hình tối ưu cho development
- ✅ **Fast Startup** - Chỉ 4 services chính

---

## 📋 Prerequisites

- Docker & Docker Compose
- 2GB RAM available
- Ports: 3000, 8000, 8080, 6379, 9092, 8090

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Create .env file
cat > .env << 'EOF'
# PoC Configuration
JWT_SECRET=poc-secret-key-for-development-only-minimum-256-bits-long
KAFKA_ENABLED=true
LOG_LEVEL=INFO
NODE_ID=node-1
EOF
```

### 2. Start Services

```bash
# Start all services with Kafka KRaft
docker-compose -f docker-compose.poc.yml up --build
```

**Wait 1-2 minutes** for services to start:
- ✅ Redis is healthy
- ✅ Kafka is healthy (KRaft mode, no Zookeeper!)
- ✅ Python AI service
- ✅ Java WebSocket server

### 3. Verify Services

```bash
# Check all services are running
docker-compose -f docker-compose.poc.yml ps

# Should show all services "Up (healthy)"
```

---

## 🔍 Access Services

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:3000 | Main UI |
| **Python API** | http://localhost:8000 | AI service |
| **WebSocket** | ws://localhost:8080/ws/chat | Real-time chat |
| **Health Check** | http://localhost:8080/actuator/health | Service health |
| **Kafka UI** | http://localhost:8090 | Browse Kafka topics |

---

## 🧪 Test the System

### Test 1: Basic Chat

1. Open http://localhost:3000
2. Send a message: "Hello"
3. Watch AI streaming response

### Test 2: View Kafka Events

1. Open http://localhost:8090
2. Navigate to **Topics**
3. Find `stream-events` and `chat-events`
4. See events in real-time

### Test 3: Check Logs

```bash
# View Java server logs
docker logs demo-java-websocket -f

# Look for [METRIC] logs:
[METRIC] Counter: websocket.connections = 1
[METRIC] Timer: stream.duration = 1234ms
[METRIC] Gauge: stream.active_sessions = 1
```

### Test 4: Kafka KRaft (No Zookeeper!)

```bash
# Verify Kafka is in KRaft mode
docker exec demo-kafka-kraft kafka-metadata.sh --snapshot /tmp/kraft-combined-logs/__cluster_metadata-0/00000000000000000000.log --print

# Should show KRaft metadata, not Zookeeper
```

---

## 📊 Metrics (Log-only Mode)

Tất cả metrics được log ra với prefix `[METRIC]`:

```log
[METRIC] Counter: websocket.connections = 5
[METRIC] Gauge: stream.active_sessions = 2
[METRIC] Timer: stream.duration = 1523ms
[METRIC] Distribution: stream.chunks = 45
```

**Xem logs:**
```bash
docker logs demo-java-websocket | grep "\[METRIC\]"
```

---

## 🔧 Configuration

### Minimal PoC Settings

```yaml
# In docker-compose.poc.yml
java-websocket:
  environment:
    # Light JVM settings
    - JAVA_OPTS=-Xms256m -Xmx512m
    
    # Small cache
    - CACHE_L1_MAX_SIZE=1000
    
    # Simple logging
    - LOG_LEVEL=INFO
```

### Enable/Disable Kafka

```bash
# Disable Kafka
KAFKA_ENABLED=false docker-compose -f docker-compose.poc.yml up

# Enable Kafka (default)
KAFKA_ENABLED=true docker-compose -f docker-compose.poc.yml up
```

---

## 🐛 Troubleshooting

### Issue: Kafka not starting

```bash
# Check Kafka logs
docker logs demo-kafka-kraft

# Restart Kafka
docker-compose -f docker-compose.poc.yml restart kafka
```

### Issue: Services slow to start

```bash
# Check service health
docker-compose -f docker-compose.poc.yml ps

# View specific service logs
docker logs demo-java-websocket --tail 50
```

### Issue: Out of memory

```bash
# Reduce Java heap in docker-compose.poc.yml
JAVA_OPTS=-Xms128m -Xmx256m
```

---

## 🛑 Stop Services

```bash
# Stop all services
docker-compose -f docker-compose.poc.yml down

# Stop and remove volumes (fresh start)
docker-compose -f docker-compose.poc.yml down -v
```

---

## 📝 Key Differences from Full Setup

| Feature | PoC Mode | Full Mode |
|---------|----------|-----------|
| **Kafka** | KRaft (no Zookeeper) | KRaft (same) |
| **Metrics** | Log only | Prometheus + Grafana |
| **Monitoring** | Console logs | Grafana dashboards |
| **Cache Size** | 1,000 entries | 10,000+ entries |
| **JVM Memory** | 256-512MB | 1-4GB |
| **Services** | 6 | 9+ |
| **Startup Time** | 1-2 min | 3-5 min |

---

## 🎯 What's Logged

### Connection Events
```log
INFO  WebSocket connected: wsId=abc123, sessionId=session_1, userId=user1
[METRIC] Counter: websocket.connections = 1
[METRIC] Gauge: websocket.active_connections = 1
```

### Stream Events
```log
INFO  Started streaming session: sessionId=session_1, messageId=msg_123
[METRIC] Counter: stream.started = 1
[METRIC] Gauge: stream.active_sessions = 1
[METRIC] Timer: stream.duration = 2345ms
[METRIC] Distribution: stream.chunks = 56
```

### Cache Events
```log
DEBUG L1 cache hit: sessionId=session_1
[METRIC] Counter: cache.hits = 1
DEBUG L2 cache miss: sessionId=session_2
[METRIC] Counter: cache.misses = 1
```

### Recovery Events
```log
INFO  Recovery requested: sessionId=session_1, lastChunk=10
INFO  Retrieved 5 missing chunks
[METRIC] Counter: recovery.streaming.success = 1
```

---

## 🔄 Kafka KRaft Benefits

**So với Zookeeper:**
- ✅ Đơn giản hơn - không cần service riêng
- ✅ Nhanh hơn - ít overhead
- ✅ Modern - Kafka 3.3+
- ✅ Ít tài nguyên hơn
- ✅ Easier to manage

**Verify KRaft mode:**
```bash
# Check if no Zookeeper
docker ps | grep zookeeper
# Should return nothing

# Kafka logs should show "KRaft"
docker logs demo-kafka-kraft | grep -i kraft
```

---

## 📈 Next Steps

### For Development
1. Use this PoC setup
2. Watch logs for debugging
3. Use Kafka UI to see events

### For Production
1. Switch to `docker-compose.full.yml`
2. Enable Prometheus/Grafana
3. Increase cache sizes
4. Add proper monitoring

---

## 🎉 Summary

**PoC Mode có:**
- ✅ Kafka KRaft (modern, no Zookeeper)
- ✅ Log-based metrics (simple)
- ✅ All core features (JWT, cache, recovery, events)
- ✅ Fast startup
- ✅ Low resource usage

**Perfect for:**
- Development
- Testing
- Demos
- Learning

**Chạy ngay:**
```bash
docker-compose -f docker-compose.poc.yml up --build
```

🚀 **Enjoy your PoC!**
