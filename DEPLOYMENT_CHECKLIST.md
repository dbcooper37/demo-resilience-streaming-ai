# 📋 Deployment Checklist - Sticky Session Multi-Node

## ✅ Pre-Deployment

### Environment
- [ ] Docker installed (version 20.10+)
- [ ] Docker Compose installed (version 2.0+)
- [ ] Sufficient resources (4GB+ RAM, 20GB+ disk)
- [ ] Ports available: 3000, 6379, 8080, 8090, 9092, 9093

### Repository
- [ ] Code pulled from `dev_sticky_session` branch
- [ ] All files present:
  - [ ] `docker-compose.sticky-session.yml`
  - [ ] `nginx-sticky-session.conf`
  - [ ] `DEPLOY_STICKY_SESSION.sh`
  - [ ] `TEST_STICKY_SESSION.sh`
  - [ ] `README.sticky-session.md`
  - [ ] `.env.sticky-session.example`

### Configuration
- [ ] Review `.env.sticky-session.example`
- [ ] Copy to `.env` if using custom settings
- [ ] Update JWT_SECRET for production
- [ ] Configure Redis password if needed
- [ ] Review resource limits in docker-compose

---

## 🚀 Deployment Steps

### Step 1: Pre-flight Check
```bash
# Check Docker
docker --version
docker-compose --version

# Check available ports
lsof -i :3000  # Should be free
lsof -i :8080  # Should be free
lsof -i :6379  # Should be free

# Check disk space
df -h
```

**Status**: [ ] Completed

### Step 2: Build Images
```bash
# Option A: Automated
./DEPLOY_STICKY_SESSION.sh

# Option B: Manual
docker-compose -f docker-compose.sticky-session.yml build --no-cache
```

**Status**: [ ] Completed

### Step 3: Start Services
```bash
# If using automated script, this is included in Step 2
# Otherwise:
docker-compose -f docker-compose.sticky-session.yml up -d
```

**Status**: [ ] Completed

### Step 4: Wait for Services
```bash
# Wait 30-60 seconds for all services to be ready
# Check status
docker-compose -f docker-compose.sticky-session.yml ps
```

Expected output: All services should be "Up (healthy)"

**Status**: [ ] Completed

### Step 5: Verify Deployment
```bash
# Run test suite
./TEST_STICKY_SESSION.sh
```

**Status**: [ ] Completed

---

## ✅ Post-Deployment Verification

### Infrastructure Services
- [ ] Redis is running and responding
  ```bash
  docker exec sticky-redis redis-cli ping
  # Expected: PONG
  ```

- [ ] Kafka is running
  ```bash
  docker exec sticky-kafka kafka-broker-api-versions.sh --bootstrap-server localhost:9092
  # Expected: List of API versions
  ```

- [ ] Nginx Load Balancer is running
  ```bash
  curl http://localhost:8080/
  # Expected: {"status":"ok",...}
  ```

### WebSocket Nodes
- [ ] Node 1 is healthy
  ```bash
  docker exec sticky-java-ws-1 curl -sf http://localhost:8080/actuator/health
  ```

- [ ] Node 2 is healthy
  ```bash
  docker exec sticky-java-ws-2 curl -sf http://localhost:8080/actuator/health
  ```

- [ ] Node 3 is healthy
  ```bash
  docker exec sticky-java-ws-3 curl -sf http://localhost:8080/actuator/health
  ```

### AI Service Nodes
- [ ] AI Node 1 is healthy
  ```bash
  docker exec sticky-python-ai-1 curl -sf http://localhost:8000/health
  ```

- [ ] AI Node 2 is healthy
  ```bash
  docker exec sticky-python-ai-2 curl -sf http://localhost:8000/health
  ```

- [ ] AI Node 3 is healthy
  ```bash
  docker exec sticky-python-ai-3 curl -sf http://localhost:8000/health
  ```

### Frontend
- [ ] Frontend is accessible
  ```bash
  curl http://localhost:3000
  # Expected: HTML page
  ```

- [ ] Frontend can connect to backend
  - Open browser to http://localhost:3000
  - Open browser console
  - Should see WebSocket connection established

---

## 🧪 Functional Tests

### Test 1: Sticky Session Verification
```bash
# Make multiple requests
for i in {1..10}; do curl -s http://localhost:8080/health > /dev/null; done

# Check distribution (should all go to same backend)
docker exec sticky-nginx-lb tail -10 /var/log/nginx/access.log | grep -oP 'upstream: \K[^:]+' | sort | uniq -c
```

**Expected**: All 10 requests to same upstream (e.g., "10 java-websocket-1")

**Status**: [ ] Passed

### Test 2: WebSocket Connection
```bash
# Install wscat if not installed
npm install -g wscat

# Connect
wscat -c "ws://localhost:8080/ws/chat?session_id=test-$(date +%s)&user_id=test-user&token=dev-token"
```

**Expected**: 
- Connection established
- Welcome message received
- Can send ping/pong

**Status**: [ ] Passed

### Test 3: Redis Shared State
```bash
# Check active sessions
docker exec sticky-redis redis-cli HLEN "sessions:active"

# After connecting WebSocket, this should increment
```

**Expected**: Session count increases when clients connect

**Status**: [ ] Passed

### Test 4: Node Failover
```bash
# 1. Connect WebSocket client
# 2. Note which node it connected to (check logs)
# 3. Stop that node
docker stop sticky-java-ws-1

# 4. Client should reconnect to another node
# 5. Verify recovery mechanism works
```

**Expected**: Client reconnects successfully, no data loss

**Status**: [ ] Passed

### Test 5: Load Distribution
```bash
# Connect multiple clients from different IPs
# (In production, or simulate with different source IPs)
# Verify they distribute across different nodes
```

**Expected**: Clients distributed across all 3 backend nodes

**Status**: [ ] Passed

---

## 📊 Monitoring Setup

### Basic Monitoring
- [ ] Set up log aggregation
  ```bash
  docker-compose -f docker-compose.sticky-session.yml logs -f > app.log &
  ```

- [ ] Monitor Nginx stats
  ```bash
  watch -n 5 "curl -s http://localhost:8090/nginx-status"
  ```

- [ ] Monitor Redis
  ```bash
  docker exec sticky-redis redis-cli INFO | grep -E "connected_clients|used_memory_human|total_commands_processed"
  ```

- [ ] Monitor Docker stats
  ```bash
  docker stats
  ```

### Advanced Monitoring (Optional)
- [ ] Set up Prometheus + Grafana
- [ ] Configure alerting
- [ ] Set up APM (Application Performance Monitoring)
- [ ] Configure distributed tracing

---

## 🔐 Security Checklist

### Pre-Production
- [ ] Change default JWT_SECRET
- [ ] Enable Redis password authentication
- [ ] Review and update CORS settings
- [ ] Disable unnecessary ports
- [ ] Review Docker image security
- [ ] Set up network isolation

### Production
- [ ] Enable SSL/TLS (wss:// for WebSocket)
- [ ] Configure firewall rules
- [ ] Set up rate limiting
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Implement intrusion detection
- [ ] Set up backup and recovery

---

## 📈 Performance Tuning

### Initial Settings
- [ ] Review JVM memory settings
  ```yaml
  JAVA_OPTS: -Xms384m -Xmx768m
  ```

- [ ] Review Redis maxmemory
  ```yaml
  maxmemory 512mb
  maxmemory-policy allkeys-lru
  ```

- [ ] Review Nginx worker processes
  ```nginx
  worker_processes auto;
  worker_connections 2048;
  ```

### Load Testing
- [ ] Run load tests
  ```bash
  wrk -t4 -c100 -d30s http://localhost:8080/health
  ```

- [ ] Monitor resource usage during load
- [ ] Identify bottlenecks
- [ ] Adjust settings accordingly

### Optimization
- [ ] Tune cache sizes
- [ ] Adjust connection pools
- [ ] Optimize database queries (if applicable)
- [ ] Enable compression
- [ ] Configure CDN (if applicable)

---

## 🐛 Troubleshooting

### Common Issues

#### Issue: Services not starting
**Check**:
```bash
docker-compose -f docker-compose.sticky-session.yml logs
docker ps -a
```

**Solution**: Check logs for specific errors

#### Issue: Out of memory
**Check**:
```bash
docker stats
free -h
```

**Solution**: Reduce JVM memory or add more RAM

#### Issue: Port conflicts
**Check**:
```bash
lsof -i :8080
lsof -i :3000
```

**Solution**: Stop conflicting services or change ports

#### Issue: Sticky sessions not working
**Check**:
```bash
docker exec sticky-nginx-lb nginx -t
docker exec sticky-nginx-lb cat /etc/nginx/nginx.conf | grep ip_hash
```

**Solution**: Verify nginx config has ip_hash directive

---

## 📝 Rollback Plan

### If deployment fails:

1. **Stop all services**
   ```bash
   docker-compose -f docker-compose.sticky-session.yml down
   ```

2. **Check what went wrong**
   ```bash
   docker-compose -f docker-compose.sticky-session.yml logs
   ```

3. **Clean up (if needed)**
   ```bash
   docker-compose -f docker-compose.sticky-session.yml down -v
   docker system prune -a
   ```

4. **Roll back to previous branch**
   ```bash
   git checkout main  # or previous working branch
   ```

5. **Redeploy previous version**
   ```bash
   docker-compose up -d
   ```

---

## ✅ Sign-off

### Deployment Sign-off
- [ ] All services running
- [ ] All health checks passing
- [ ] Functional tests passed
- [ ] Performance acceptable
- [ ] Monitoring in place
- [ ] Documentation reviewed
- [ ] Team notified

**Deployed by**: _______________

**Date**: _______________

**Version**: _______________

**Notes**:
```
[Add any deployment notes here]
```

---

## 📞 Support Contacts

### Escalation
1. Check documentation: `README.sticky-session.md`
2. Review logs: `docker-compose logs`
3. Run diagnostics: `./TEST_STICKY_SESSION.sh`
4. Contact: [Your support contact]

### Useful Commands
```bash
# Quick health check
curl http://localhost:8080/health

# View recent errors
docker-compose -f docker-compose.sticky-session.yml logs --tail=100 | grep ERROR

# Restart all services
docker-compose -f docker-compose.sticky-session.yml restart

# Scale a service (example)
docker-compose -f docker-compose.sticky-session.yml up -d --scale java-websocket-1=2
```

---

**Status**: 
- [ ] Not Started
- [ ] In Progress
- [ ] Completed
- [ ] Verified

**Deployment Date**: _______________

**Next Review**: _______________
