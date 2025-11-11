# Fix: I/O Error khi Backend gọi AI Service trong Multi-Node

## Vấn đề

Khi triển khai với `docker-compose.multi-node.yml`, backend Java gặp lỗi:
```
I/O error on POST request for "http://python-ai:8000/chat": python-ai
```

## Nguyên nhân

Trong môi trường multi-node:
- AI services có tên: `python-ai-1`, `python-ai-2`, `python-ai-3`
- Java backend được cấu hình kết nối đến: `http://python-ai:8000`
- Service name `python-ai` không tồn tại trong docker-compose.multi-node.yml
- Docker không thể resolve DNS name `python-ai` → I/O error

## Giải pháp

### 1. Thêm AI Service Load Balancing vào NGINX

**File: `nginx-lb.conf`**

Thêm upstream cho AI services:
```nginx
upstream ai_backend {
    # Round-robin load balancing for AI services
    server python-ai-1:8000 max_fails=3 fail_timeout=30s;
    server python-ai-2:8000 max_fails=3 fail_timeout=30s;
    server python-ai-3:8000 max_fails=3 fail_timeout=30s;
}
```

Thêm location để route requests đến AI services:
```nginx
# AI Service endpoints - Direct access to AI services
location /ai/ {
    proxy_pass http://ai_backend/;
    
    # Standard proxy headers
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Timeouts for AI calls
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    
    # Enable buffering for AI responses
    proxy_buffering on;
}
```

### 2. Cấu hình Java Services sử dụng NGINX Load Balancer

**File: `docker-compose.multi-node.yml`**

Thêm environment variable cho tất cả Java WebSocket nodes:
```yaml
environment:
  # AI Service Configuration - Use NGINX load balancer
  - AI_SERVICE_URL=http://nginx-lb:80/ai
```

Cập nhật dependencies để đảm bảo NGINX khởi động trước Java services:
```yaml
java-websocket-1:
  depends_on:
    - redis
    - kafka
    - nginx-lb

nginx-lb:
  depends_on:
    - python-ai-1
    - python-ai-2
    - python-ai-3
```

## Luồng kết nối mới

```
Java Backend Nodes (3 nodes)
    ↓
NGINX Load Balancer (port 8080)
    ↓ (internal: nginx-lb:80/ai)
AI Service Load Balancer (upstream ai_backend)
    ↓
AI Service Nodes (3 nodes: python-ai-1, python-ai-2, python-ai-3)
```

## Triển khai

### Cách 1: Sử dụng Quick Start Script (Khuyến nghị)

Script này đảm bảo thứ tự khởi động đúng để tránh circular dependencies:

```bash
./QUICK_START_MULTINODE.sh
```

Script sẽ:
1. Dừng tất cả containers hiện tại
2. Start core infrastructure (Redis, Kafka)
3. Start AI services (3 nodes)
4. Start NGINX Load Balancer
5. Start Java WebSocket services (3 nodes)
6. Start Frontend
7. Hiển thị status và access points

### Cách 2: Manual Deployment

**Bước 1: Dừng các services hiện tại**

```bash
docker-compose -f docker-compose.multi-node.yml down
```

**Bước 2: Rebuild services (nếu cần)**

```bash
docker-compose -f docker-compose.multi-node.yml build
```

**Bước 3: Khởi động theo thứ tự**

```bash
# Start infrastructure
docker-compose -f docker-compose.multi-node.yml up -d redis kafka

# Wait for infrastructure
sleep 10

# Start AI services
docker-compose -f docker-compose.multi-node.yml up -d python-ai-1 python-ai-2 python-ai-3

# Wait for AI services
sleep 15

# Start NGINX LB
docker-compose -f docker-compose.multi-node.yml up -d nginx-lb

# Wait for NGINX
sleep 5

# Start Java services
docker-compose -f docker-compose.multi-node.yml up -d java-websocket-1 java-websocket-2 java-websocket-3

# Wait for Java services
sleep 20

# Start frontend
docker-compose -f docker-compose.multi-node.yml up -d frontend
```

**Bước 4: Kiểm tra logs**

```bash
# Kiểm tra Java backend logs
docker-compose -f docker-compose.multi-node.yml logs -f java-websocket-1

# Kiểm tra NGINX logs
docker-compose -f docker-compose.multi-node.yml logs -f nginx-lb

# Kiểm tra AI service logs
docker-compose -f docker-compose.multi-node.yml logs -f python-ai-1
```

### Bước 5: Chạy test kết nối

```bash
./test_multinode_connectivity.sh
```

Script test sẽ kiểm tra:
1. Health check của tất cả services
2. Kết nối trực tiếp đến từng AI service
3. Kết nối qua NGINX load balancer
4. Kết nối từ Java backend qua NGINX đến AI services
5. Environment variables trong Java containers

## Xác minh

### 1. Kiểm tra AI_SERVICE_URL trong Java containers

```bash
docker exec demo-java-websocket-1 printenv AI_SERVICE_URL
# Expected: http://nginx-lb:80/ai

docker exec demo-java-websocket-2 printenv AI_SERVICE_URL
# Expected: http://nginx-lb:80/ai

docker exec demo-java-websocket-3 printenv AI_SERVICE_URL
# Expected: http://nginx-lb:80/ai
```

### 2. Test NGINX AI load balancer

```bash
# Test qua NGINX
curl -X POST http://localhost:8080/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello","session_id":"test-session"}'
```

### 3. Test từ trong Java container

```bash
docker exec demo-java-websocket-1 curl -X POST http://nginx-lb:80/ai/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"hello from java","session_id":"test-java"}'
```

## Lợi ích của giải pháp

1. **Load Balancing**: Requests được phân phối đều giữa 3 AI service nodes
2. **High Availability**: Nếu một AI node down, requests tự động route đến nodes còn lại
3. **Single Point of Configuration**: Java backend chỉ cần biết URL của NGINX
4. **Scalability**: Dễ dàng thêm/bớt AI nodes bằng cách update nginx-lb.conf
5. **Monitoring**: Tất cả AI requests đi qua NGINX, dễ dàng monitor và log

## Troubleshooting

### Lỗi vẫn còn sau khi fix

1. **Kiểm tra NGINX đã khởi động chưa:**
   ```bash
   docker ps | grep nginx-lb
   docker-compose -f docker-compose.multi-node.yml logs nginx-lb
   ```

2. **Kiểm tra AI services đã healthy:**
   ```bash
   curl http://localhost:8001/health
   curl http://localhost:8002/health
   curl http://localhost:8003/health
   ```

3. **Kiểm tra network connectivity:**
   ```bash
   docker exec demo-java-websocket-1 ping -c 3 nginx-lb
   docker exec demo-nginx-lb ping -c 3 python-ai-1
   ```

4. **Rebuild và restart:**
   ```bash
   docker-compose -f docker-compose.multi-node.yml down
   docker-compose -f docker-compose.multi-node.yml build --no-cache java-websocket-1
   docker-compose -f docker-compose.multi-node.yml up -d
   ```

### NGINX không route đến AI services

1. **Kiểm tra NGINX config:**
   ```bash
   docker exec demo-nginx-lb nginx -t
   ```

2. **Kiểm tra NGINX upstream status:**
   ```bash
   docker-compose -f docker-compose.multi-node.yml logs nginx-lb | grep "upstream"
   ```

3. **Test trực tiếp từ NGINX container:**
   ```bash
   docker exec demo-nginx-lb wget -O- http://python-ai-1:8000/health
   ```

## Files thay đổi

1. **nginx-lb.conf**: Thêm AI service upstream và location
2. **docker-compose.multi-node.yml**: Thêm AI_SERVICE_URL cho Java services
3. **test_multinode_connectivity.sh**: Script test kết nối (mới)
4. **MULTINODE_AI_SERVICE_FIX.md**: Tài liệu này (mới)

## Ghi chú

- Giải pháp này chỉ áp dụng cho môi trường **multi-node**
- Môi trường single-node (docker-compose.yml) vẫn sử dụng service name `python-ai` trực tiếp
- NGINX load balancer sử dụng round-robin algorithm để phân phối requests
- Mỗi AI service có health check riêng, NGINX tự động skip nodes không healthy
