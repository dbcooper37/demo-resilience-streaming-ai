# Multi-Node Deployment with Sticky Sessions

Triển khai hệ thống AI Streaming Chat trên multi-node với sticky sessions và shared state.

## 🎯 Tổng quan

Branch này (`dev_sticky_session`) triển khai kiến trúc multi-node với các tính năng:

### ✅ Sticky Sessions
- **Load Balancer**: Nginx với `ip_hash` directive
- **WebSocket**: Đảm bảo client luôn kết nối về cùng một backend node
- **Failover**: Tự động chuyển sang node khác khi node hiện tại down

### ✅ Shared State
- **Redis**: Distributed session registry và cache
- **Redisson**: Distributed locks cho chunk ordering
- **PubSub**: Inter-node communication qua Redis PubSub

### ✅ High Availability
- **3 WebSocket Nodes**: Auto-restart, health checks
- **3 AI Service Nodes**: Load balanced với `least_conn`
- **Monitoring**: Health endpoints, metrics, logs

---

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│                   localhost:3000                     │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket + HTTP
                       ↓
┌─────────────────────────────────────────────────────┐
│            Nginx Load Balancer (ip_hash)            │
│                   localhost:8080                     │
│  • Sticky sessions cho WebSocket                    │
│  • Health checks                                     │
│  • Metrics endpoint (:8090)                         │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ WS Node 1   │ │ WS Node 2   │ │ WS Node 3   │
│ :8081       │ │ :8082       │ │ :8083       │
│ ws-node-1   │ │ ws-node-2   │ │ ws-node-3   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┼───────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│           Redis (Shared State & PubSub)             │
│                 localhost:6379                       │
│  • Session registry (distributed)                   │
│  • Stream chunks cache                              │
│  • Distributed locks (Redisson)                     │
│  • Inter-node communication                         │
└──────────────────────┬──────────────────────────────┘
                       ↑
         ┌─────────────┼─────────────┐
         │             │             │
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ AI Node 1   │ │ AI Node 2   │ │ AI Node 3   │
│ :8001       │ │ :8002       │ │ :8003       │
└─────────────┘ └─────────────┘ └─────────────┘
```

---

## 🚀 Quick Start

### 1. Deploy toàn bộ hệ thống

```bash
# Build và start tất cả services
./DEPLOY_STICKY_SESSION.sh
```

Script sẽ:
- Build Docker images
- Start all services
- Wait for health checks
- Display service URLs

### 2. Kiểm tra deployment

```bash
# Run test suite
./TEST_STICKY_SESSION.sh
```

Test suite kiểm tra:
- Service health
- Load balancing distribution
- WebSocket connectivity
- Redis connectivity
- Sticky session verification

### 3. Truy cập ứng dụng

- **Frontend**: http://localhost:3000
- **Load Balancer**: http://localhost:8080
- **WebSocket**: ws://localhost:8080/ws/chat
- **API**: http://localhost:8080/api

---

## 📊 Monitoring

### Service Health

```bash
# Check all services
docker-compose -f docker-compose.sticky-session.yml ps

# Check specific service health
curl http://localhost:8081/actuator/health  # WS Node 1
curl http://localhost:8082/actuator/health  # WS Node 2
curl http://localhost:8083/actuator/health  # WS Node 3
```

### Nginx Stats

```bash
# Nginx stub status
curl http://localhost:8090/nginx-status

# View access logs with upstream info
docker exec sticky-nginx-lb tail -f /var/log/nginx/access.log
```

### Redis Monitoring

```bash
# Redis CLI
docker exec -it sticky-redis redis-cli

# Check active sessions
redis-cli HGETALL sessions:active

# Check connected clients
redis-cli CLIENT LIST

# Redis info
redis-cli INFO
```

### Application Logs

```bash
# All services
docker-compose -f docker-compose.sticky-session.yml logs -f

# Specific service
docker logs -f sticky-java-ws-1
docker logs -f sticky-python-ai-1
docker logs -f sticky-nginx-lb

# Filter by level
docker logs sticky-java-ws-1 2>&1 | grep ERROR
```

---

## 🔧 Configuration

### Sticky Sessions

File: `nginx-sticky-session.conf`

```nginx
upstream websocket_backend {
    # ip_hash ensures same client IP -> same backend
    ip_hash;
    
    server java-websocket-1:8080 max_fails=3 fail_timeout=30s;
    server java-websocket-2:8080 max_fails=3 fail_timeout=30s;
    server java-websocket-3:8080 max_fails=3 fail_timeout=30s;
}
```

**Cách hoạt động:**
- Nginx sử dụng client IP để hash
- Cùng IP luôn được route tới cùng backend
- Nếu backend fail, tự động chuyển sang backend khác

### Shared State (Redis)

**Session Registry:**
```
sessions:active -> Map<sessionId, userId>
sessions:user:{userId} -> Set<sessionId>
```

**Stream Cache:**
```
stream:chunks:{messageId} -> List<StreamChunk>
stream:session:{sessionId} -> Hash (metadata)
stream:metadata:{messageId} -> Metadata
```

**Distributed Locks:**
```
stream:lock:{messageId} -> RLock (Redisson)
```

### Environment Variables

Xem file `docker-compose.sticky-session.yml` để tùy chỉnh:

```yaml
# JVM Settings
JAVA_OPTS: -Xms384m -Xmx768m -XX:+UseG1GC

# Cache Settings
CACHE_L1_MAX_SIZE: 5000
CACHE_L2_TTL: 5

# Stream Settings
STREAM_MAX_PENDING_CHUNKS: 1000
```

---

## 🧪 Testing

### Test 1: Sticky Session

```bash
# Make multiple requests from same IP
for i in {1..10}; do
    curl -s http://localhost:8080/health
done

# Check nginx logs - should all go to same backend
docker exec sticky-nginx-lb tail -10 /var/log/nginx/access.log | grep "upstream:"
```

### Test 2: Load Distribution

```bash
# Test with different source IPs (requires multiple machines or IP spoofing)
# Same IP -> Same backend
# Different IPs -> Distributed across backends
```

### Test 3: Node Failover

```bash
# 1. Connect WebSocket client
wscat -c "ws://localhost:8080/ws/chat?session_id=test&user_id=testuser&token=dev-token"

# 2. Check which node it connected to (from logs)
docker-compose -f docker-compose.sticky-session.yml logs | grep "WebSocket connected"

# 3. Stop that node
docker stop sticky-java-ws-1

# 4. Reconnect - should connect to another node
# 5. Recovery should work (missing chunks retrieved from Redis)
```

### Test 4: Concurrent Users

```bash
# Install dependencies
npm install -g wscat

# Open multiple terminals and connect
# Terminal 1
wscat -c "ws://localhost:8080/ws/chat?session_id=user1&user_id=user1&token=dev-token"

# Terminal 2
wscat -c "ws://localhost:8080/ws/chat?session_id=user2&user_id=user2&token=dev-token"

# Terminal 3
wscat -c "ws://localhost:8080/ws/chat?session_id=user3&user_id=user3&token=dev-token"

# Check distribution
docker logs sticky-nginx-lb 2>&1 | tail -20 | grep "upstream:"
```

---

## 🔍 Troubleshooting

### Problem: WebSocket not connecting

**Solution:**
```bash
# 1. Check Nginx
curl http://localhost:8080/

# 2. Check backend nodes
curl http://localhost:8081/actuator/health
curl http://localhost:8082/actuator/health
curl http://localhost:8083/actuator/health

# 3. Check logs
docker logs sticky-nginx-lb
docker logs sticky-java-ws-1
```

### Problem: Sticky session not working

**Solution:**
```bash
# 1. Verify nginx config
docker exec sticky-nginx-lb nginx -t

# 2. Check ip_hash is enabled
docker exec sticky-nginx-lb cat /etc/nginx/nginx.conf | grep ip_hash

# 3. Test from same IP multiple times
for i in {1..5}; do curl -s http://localhost:8080/health; done
docker logs sticky-nginx-lb 2>&1 | tail -5 | grep "upstream:"
```

### Problem: Redis connection errors

**Solution:**
```bash
# 1. Check Redis
docker exec sticky-redis redis-cli ping

# 2. Check Redis connections from Java
docker exec sticky-java-ws-1 curl -s http://localhost:8080/actuator/health | grep redis

# 3. Check Redis logs
docker logs sticky-redis
```

### Problem: High memory usage

**Solution:**
```bash
# 1. Check container stats
docker stats

# 2. Adjust JVM settings in docker-compose.sticky-session.yml
JAVA_OPTS: -Xms256m -Xmx512m

# 3. Adjust Redis maxmemory
# In docker-compose.sticky-session.yml:
command: redis-server --maxmemory 256mb

# 4. Restart services
docker-compose -f docker-compose.sticky-session.yml restart
```

---

## 📈 Scaling

### Horizontal Scaling

**Add more WebSocket nodes:**

```yaml
# In docker-compose.sticky-session.yml
java-websocket-4:
    build:
      context: ./java-websocket-server
    container_name: sticky-java-ws-4
    environment:
      - NODE_ID=ws-node-4
      # ... other env vars
```

**Update Nginx config:**

```nginx
upstream websocket_backend {
    ip_hash;
    server java-websocket-1:8080;
    server java-websocket-2:8080;
    server java-websocket-3:8080;
    server java-websocket-4:8080;  # New node
}
```

### Vertical Scaling

**Increase resources:**

```yaml
# In docker-compose.sticky-session.yml
java-websocket-1:
    environment:
      - JAVA_OPTS=-Xms1g -Xmx2g -XX:+UseG1GC
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

---

## 🔐 Security Notes

**Production Checklist:**

- [ ] Enable SSL/TLS (wss:// instead of ws://)
- [ ] Configure CORS properly (not `*`)
- [ ] Enable Redis authentication
- [ ] Use strong JWT secrets
- [ ] Implement rate limiting
- [ ] Enable network isolation
- [ ] Configure firewall rules
- [ ] Enable audit logging
- [ ] Regular security updates

**Example SSL configuration:**

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    # ... rest of config
}
```

---

## 📝 Key Features

### ✅ Sticky Sessions (ip_hash)
- Client IP-based routing
- Persistent connections to same backend
- Automatic failover on node failure

### ✅ Shared State (Redis)
- Distributed session registry
- Stream chunks caching
- Inter-node communication
- TTL-based cleanup

### ✅ Distributed Coordination (Redisson)
- Distributed locks for chunk ordering
- Atomic operations
- Connection pooling
- Automatic reconnection

### ✅ High Availability
- Multiple instances per service
- Health checks
- Auto-restart on failure
- Graceful degradation

### ✅ Monitoring & Observability
- Health endpoints
- Metrics collection
- Centralized logging
- Nginx access logs with upstream info

---

## 🤝 Contributing

Để thêm tính năng hoặc fix bugs:

1. Checkout branch này: `git checkout dev_sticky_session`
2. Tạo feature branch: `git checkout -b feature/your-feature`
3. Test thoroughly với `./TEST_STICKY_SESSION.sh`
4. Submit pull request

---

## 📚 Related Documentation

- [Architecture Overview](./docs/README.md)
- [Multi-Node Guide](./README.multi-node.md)
- [Kafka Usage Guide](./docs/KAFKA_USAGE_GUIDE.md)
- [API Documentation](./docs/API.md)

---

## 🎓 Learn More

### Sticky Sessions
- [Nginx Load Balancing](https://nginx.org/en/docs/http/load_balancing.html)
- [ip_hash directive](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#ip_hash)

### Redis & Redisson
- [Redis Documentation](https://redis.io/documentation)
- [Redisson Documentation](https://github.com/redisson/redisson/wiki)
- [Distributed Locks](https://redis.io/topics/distlock)

### WebSocket
- [WebSocket Protocol](https://datatracker.ietf.org/doc/html/rfc6455)
- [Spring WebSocket](https://docs.spring.io/spring-framework/reference/web/websocket.html)

---

## 📄 License

MIT License

---

**Happy Deploying! 🚀**
