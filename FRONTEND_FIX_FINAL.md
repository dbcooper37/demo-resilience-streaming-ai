# Frontend-Backend Connection Fix - FINAL VERSION

## 🔴 Vấn đề chính (Root Cause)

**Browser không thể access Docker network internal names!**

Khi frontend chạy trong browser:
- Browser chạy trên **client-side** (máy user), không phải trong Docker container
- Browser **KHÔNG THỂ** resolve Docker network names như `python-ai`, `java-websocket`
- Browser chỉ có thể call tới `localhost` hoặc public domains

### Giải thích chi tiết:

```
❌ SAI: Browser gọi tới python-ai:8000
   → Browser không biết "python-ai" là gì (chỉ có Docker network biết)

❌ SAI: Browser gọi tới /api và hy vọng Vite proxy xử lý
   → Trong Docker, việc proxy phức tạp và không cần thiết

✅ ĐÚNG: Browser gọi trực tiếp tới http://localhost:8000
   → Port 8000 đã được expose ra ngoài từ python-ai container
```

## ✅ Giải pháp

### 1. Frontend gọi trực tiếp tới exposed ports

**File: `docker-compose.yml`**
```yaml
frontend:
  environment:
    - VITE_WS_URL=ws://localhost:8080/ws/chat      # Port exposed từ java-websocket
    - VITE_API_URL=http://localhost:8000            # Port exposed từ python-ai
```

**File: `frontend/.env`**
```env
VITE_WS_URL=ws://localhost:8080/ws/chat
VITE_API_URL=http://localhost:8000
```

### 2. Exposed Ports trong Docker Compose

```yaml
python-ai:
  ports:
    - "8000:8000"  # ← Browser có thể gọi tới localhost:8000

java-websocket:
  ports:
    - "8080:8080"  # ← Browser có thể connect tới localhost:8080

frontend:
  ports:
    - "3000:3000"  # ← Browser access frontend qua localhost:3000
```

### 3. CORS Configuration

Python AI service đã được config CORS để accept requests từ browser:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🏗️ Architecture Đúng

```
┌─────────────────────────────────────┐
│          User's Browser             │
│         (localhost/client)          │
└──────────┬──────────────────────────┘
           │
           ├─── http://localhost:3000 (Frontend)
           │    ↓ Browser renders React app
           │
           ├─── ws://localhost:8080/ws/chat (WebSocket)
           │    ↓ Port mapped từ java-websocket container
           │
           └─── http://localhost:8000/chat (API)
                ↓ Port mapped từ python-ai container

┌──────────────────────────────────────┐
│         Docker Network               │
│                                      │
│  ┌──────────┐      ┌─────────────┐ │
│  │ Frontend │      │  Python AI  │ │
│  │  :3000   │      │    :8000    │ │ → :8000 exposed
│  └──────────┘      └──────┬──────┘ │
│                           │         │
│  ┌──────────────┐         │        │
│  │ Java WS      │─────────┴────┐   │
│  │   :8080      │              │   │ → :8080 exposed
│  └──────────────┘      ┌────────┐  │
│                        │ Redis  │  │
│                        │ :6379  │  │
│                        └────────┘  │
└──────────────────────────────────────┘
```

## 🚀 Cách Test

### 1. Rebuild và start containers:

```bash
docker compose down
docker compose build frontend
docker compose up -d
```

### 2. Kiểm tra containers đang chạy:

```bash
docker compose ps

# Output expected:
# NAME                  STATUS    PORTS
# demo-frontend         Up        0.0.0.0:3000->3000/tcp
# demo-java-websocket   Up        0.0.0.0:8080->8080/tcp
# demo-python-ai        Up        0.0.0.0:8000->8000/tcp
# demo-redis            Up        0.0.0.0:6379->6379/tcp
```

### 3. Test từng service:

```bash
# Test Python AI service
curl http://localhost:8000/health
# Expected: {"status":"healthy","redis":"connected",...}

# Test Java WebSocket service
curl http://localhost:8080/health
# Expected: {"status":"UP",...}

# Test Frontend
curl http://localhost:3000
# Expected: HTML content
```

### 4. Test trên browser:

1. Mở browser: `http://localhost:3000`
2. Mở DevTools (F12) > Console
3. Kiểm tra:
   - ✅ WebSocket connection status hiển thị "connected" (màu xanh)
   - ✅ Không có CORS errors trong Console
   - ✅ Network tab hiển thị requests tới `localhost:8000/chat`

4. Gửi một message
5. Kiểm tra:
   - ✅ POST request tới `http://localhost:8000/chat` thành công (status 200)
   - ✅ Message hiển thị trong chat
   - ✅ AI response streaming qua WebSocket

### 5. Debug nếu có lỗi:

```bash
# Xem logs của từng service
docker logs demo-frontend -f
docker logs demo-python-ai -f
docker logs demo-java-websocket -f

# Check network connectivity
docker exec demo-frontend ping python-ai  # Should work (inside Docker)
curl http://localhost:8000/health          # Should work (from host)
```

## 📝 Summary of Changes

### Files Modified:
- ✅ `frontend/src/App.jsx` - Use environment variables
- ✅ `docker-compose.yml` - Update `VITE_API_URL` to `http://localhost:8000`
- ✅ `docker-compose.multi-node.yml` - Update for multi-node setup
- ✅ `frontend/.env` - Set correct API URL
- ✅ `frontend/.env.example` - Update documentation

### Files Created:
- ✅ `frontend/.env` - Environment variables
- ✅ `frontend/.env.example` - Template
- ✅ `frontend/.gitignore` - Ignore .env files
- ✅ `FRONTEND_FIX_FINAL.md` - This documentation

### Key Changes:
```diff
# docker-compose.yml
frontend:
  environment:
-   - VITE_API_URL=/api
+   - VITE_API_URL=http://localhost:8000
```

```diff
# frontend/.env
- VITE_API_URL=/api
+ VITE_API_URL=http://localhost:8000
```

## ⚠️ Important Notes

1. **Không cần Vite proxy**: Browser gọi trực tiếp tới exposed ports
2. **CORS phải được config**: Python AI service đã có CORS middleware
3. **Port mapping là quan trọng**: Phải expose ports ra localhost
4. **Environment variables phải được rebuild**: Cần rebuild frontend container sau khi thay đổi

## 🎯 Why This Works

1. **Python AI service** expose port `8000` → Browser có thể gọi `http://localhost:8000`
2. **Java WebSocket** expose port `8080` → Browser có thể connect `ws://localhost:8080`
3. **CORS đã config** → Browser được phép gọi cross-origin requests
4. **Environment variables** → Frontend biết gọi tới đâu

## 🔧 Multi-Node Setup

Với multi-node, python-ai-1 expose ở port 8001:

```yaml
python-ai-1:
  ports:
    - "8001:8000"

frontend:
  environment:
    - VITE_API_URL=http://localhost:8001  # Gọi tới node 1
```

## ❓ Troubleshooting

### Issue: "Network Error" hoặc "ERR_CONNECTION_REFUSED"

**Nguyên nhân**: Service chưa chạy hoặc port không được expose

**Giải pháp**:
```bash
# Check xem port có được listen không
netstat -an | grep 8000
# Hoặc
lsof -i :8000

# Restart service
docker compose restart python-ai
```

### Issue: CORS Error

**Nguyên nhân**: Python AI service chưa config CORS đúng

**Kiểm tra**: File `python-ai-service/app.py` phải có:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Hoặc specify exact origins
    ...
)
```

### Issue: WebSocket không connect

**Giải pháp**:
```bash
# Test WebSocket từ command line
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://localhost:8080/ws/chat?session_id=test
```

## ✅ Verification Checklist

- [ ] All containers running: `docker compose ps`
- [ ] Python AI health check: `curl http://localhost:8000/health`
- [ ] Java WS health check: `curl http://localhost:8080/health`
- [ ] Frontend accessible: Open `http://localhost:3000` in browser
- [ ] No CORS errors in browser console
- [ ] WebSocket connects (green status indicator)
- [ ] Can send message successfully
- [ ] AI response streams back via WebSocket

## 🎉 Expected Result

Sau khi apply fix này:
- ✅ Frontend load được tại `http://localhost:3000`
- ✅ WebSocket connect thành công (status màu xanh)
- ✅ Gửi message không có lỗi
- ✅ AI response hiển thị real-time
- ✅ Không có CORS errors
- ✅ Network tab hiển thị requests tới `localhost:8000`
