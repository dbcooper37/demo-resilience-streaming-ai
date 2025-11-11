# 🐛 Tái Hiện Race Condition: Mất Dữ Liệu Chunk 7

## 📋 Tóm Tắt Vấn Đề

Hệ thống hiện tại có một **race condition** trong luồng WebSocket connection, dẫn đến **mất dữ liệu** khi:
- Client reconnect trong khi AI đang streaming
- Hoặc connection được thiết lập trong khi đã có streaming đang diễn ra

### 🔴 Root Cause

Trong file `ChatWebSocketHandler.java`, phương thức `afterConnectionEstablished()` có 3 bước quan trọng:

```java
// Line 101: Bước 1 - Đọc lịch sử từ Redis
sendChatHistory(wsSession, sessionId);

// ⚠️ CỬA SỔ RỦI RO: Giữa Bước 1 và Bước 3
// Nếu Python AI Service publish chunk trong khoảng này → MISS!

// Line 117: Bước 3 - Subscribe to Redis PubSub
chatOrchestrator.startStreamingSession(sessionId, userId, callback);
```

**Vấn đề:** Giữa việc **đọc lịch sử** (Bước 1) và **subscribe PubSub** (Bước 3) có một khoảng trống. Nếu Python AI Service publish chunks trong khoảng này, chúng sẽ bị **mất**.

## 🎬 Kịch Bản Lỗi Chi Tiết

### Timeline

```
T0: Setup
    └─ Python AI Service đã publish chunks 1-6
    └─ Redis history chứa: chunk1, chunk2, ..., chunk6

T1: Java Node 2 - WebSocket Connection Established
    └─ sendChatHistory() đọc từ Redis
    └─ Client nhận: chunk1, chunk2, ..., chunk6
    └─ ✓ History contains up to chunk 6

T2: ⚠️ CỬA SỔ RỦI RO (Risk Window)
    └─ Python AI Service tiếp tục generate
    └─ PUBLISH chunk7 lên "chat:stream:{session_id}"
    └─ ❌ Java Node 2 CHƯA subscribe
    └─ ❌ Chunk 7 BỊ MẤT (lost in Redis Pub/Sub)

T3: Python AI Service
    └─ LPUSH chunk7 vào "chat:history:{session_id}"
    └─ ✓ Redis history now: chunk1...chunk7

T4: Java Node 2 - Subscribe to PubSub
    └─ chatOrchestrator.startStreamingSession()
    └─ subscribeToLegacyChannel("chat:stream:{session_id}")
    └─ ✓ Bắt đầu nghe từ BÂY GIỜ

T5: Python AI Service continues
    └─ PUBLISH chunk8, chunk9, chunk10
    └─ ✓ Java Node 2 nhận được (đã subscribe)
    └─ Client nhận: chunk8, chunk9, chunk10

T6: Stream completed
    └─ Client final content: "chunk1 chunk2 ... chunk6 chunk8 chunk9 chunk10"
    └─ ❌ MISSING: chunk7
```

### 💔 Hậu Quả

**Client thấy:**
```
chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk8 chunk9 chunk10
                                           ↑
                                     Missing chunk7!
```

**Redis history có:**
```
chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk7 chunk8 chunk9 chunk10
```

→ **Data inconsistency!**

## 🧪 Cách Tái Hiện (Reproduction Steps)

### Bước 1: Mở Rộng Cửa Sổ Rủi Ro

File `ChatWebSocketHandler.java` đã được chỉnh sửa để thêm delay 2 giây:

```java
// Send chat history
sendChatHistory(wsSession, sessionId);

// REPRODUCE RACE CONDITION: Add delay to expand risk window
log.warn("⚠️ RACE CONDITION TEST: Sleeping 2 seconds before subscribe...");
Thread.sleep(2000);  // 2 second delay
log.warn("⚠️ RACE CONDITION TEST: Delay complete, now subscribing...");

// Start streaming session (subscribe)
chatOrchestrator.startStreamingSession(sessionId, userId, callback);
```

**Location:** Lines 103-113 in `ChatWebSocketHandler.java`

### Bước 2: Chuẩn Bị Môi Trường

```bash
# 1. Start Redis
docker-compose up -d redis

# 2. Rebuild Java WebSocket Server (với delay)
docker-compose build java-websocket-1
docker-compose up -d java-websocket-1

# 3. Start Python AI Service
docker-compose up -d python-ai-1

# 4. Verify services
curl http://localhost:8080/actuator/health
redis-cli ping
```

### Bước 3: Chạy Test Simulation

**Option A: Simple Redis Test (Không cần WebSocket)**

```bash
python3 test_race_condition.py
```

Kết quả mong đợi:
```
=== T1: Java Node 2 reads history from Redis ===
✓ Read 7 items from history
📊 History contains up to chunk 6

=== T2 (RISK WINDOW): Python AI Service publishes chunk 7 ===
⚠️  Published to 0 subscribers
⚠️  But Java Node 2 has NOT subscribed yet!
⚠️  Chunk 7 is LOST for this connection!

=== T4: Java Node 2 subscribes to channel ===
✓ Java Node 2 now SUBSCRIBING to: chat:stream:xxx
🎧 From now on, will receive chunks 8, 9, 10...
❌ But chunk 7 was already MISSED!

💔 RESULT: DATA LOSS!
```

**Option B: Integrated WebSocket Test**

```bash
python3 test_integrated_race_condition.py
```

Hoặc chạy cả hai:
```bash
./run_race_condition_test.sh
```

### Bước 4: Quan Sát Logs

**Java WebSocket Server logs:**
```
[12:34:56.123] ⚠️ RACE CONDITION TEST: Sleeping 2 seconds before subscribe...
[12:34:56.123] ⚠️ If Python publishes chunk 7 during this window, it will be LOST!
[12:34:58.123] ⚠️ RACE CONDITION TEST: Delay complete, now subscribing...
[12:34:58.124] === SUBSCRIBING TO CHANNEL: chat:stream:xxx ===
```

**Redis Monitor (optional):**
```bash
redis-cli monitor
```

Bạn sẽ thấy:
```
1234567890.123456 [0 127.0.0.1:12345] "PUBLISH" "chat:stream:xxx" "{\"content\":\"chunk7\",\"is_complete\":false}"
# → 0 subscribers (message lost!)

1234567892.123456 [0 127.0.0.1:12345] "SUBSCRIBE" "chat:stream:xxx"
# → Subscription happens AFTER chunk 7 was published
```

## 📊 Verification Checklist

Sau khi chạy test, verify các điểm sau:

- [ ] **History read**: Client nhận chunks 1-6 từ history
- [ ] **Chunk 7 published**: Trong lúc delay (xem logs)
- [ ] **Chunk 7 missed**: Client KHÔNG nhận chunk 7 qua WebSocket
- [ ] **Subsequent chunks**: Client nhận chunks 8, 9, 10 sau khi subscribe
- [ ] **Redis history**: Kiểm tra Redis có đầy đủ chunks 1-10
- [ ] **Client display**: Client hiển thị thiếu chunk 7

## 🔧 Kiểm Tra Redis Trực Tiếp

```bash
# 1. Xem history trong Redis
redis-cli LRANGE "chat:history:{session_id}" 0 -1

# 2. Monitor Pub/Sub activity
redis-cli monitor | grep PUBLISH

# 3. Check subscribers count
redis-cli PUBSUB NUMSUB "chat:stream:{session_id}"
```

## 🎯 Expected Test Results

### ✅ Race Condition Reproduced Successfully

Nếu test thành công, bạn sẽ thấy:

```
VERIFICATION: Data Loss Analysis
================================

📊 Full history in Redis (11 items):
  ✓ 'chunk1'
  ✓ 'chunk1 chunk2'
  ✓ 'chunk1 chunk2 chunk3'
  ✓ 'chunk1 chunk2 chunk3 chunk4'
  ✓ 'chunk1 chunk2 chunk3 chunk4 chunk5'
  ✓ 'chunk1 chunk2 chunk3 chunk4 chunk5 chunk6'
  ✓ 'chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk7'        ← Có trong Redis
  ✓ 'chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk7 chunk8'
  ✓ 'chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk7 chunk8 chunk9'
  ✓ 'chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk7 chunk8 chunk9 chunk10'

🔍 What did the client receive?
  1. Initial history: chunks 1-6 (from T1)
  2. ❌ MISSED: chunk 7 (published at T2 before subscribe)
  3. Live stream: chunks 8, 9, 10 (after T4 subscribe)

💔 RESULT: DATA LOSS!
  - Client received: chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk8 chunk9 chunk10
  - Missing: chunk7                                           ↑ Gap!
  - Full message should be: chunk1...chunk10
```

## 🎓 Bài Học Quan Trọng

### Why This Happens?

1. **Redis Pub/Sub không persistent**: Messages chỉ được deliver tới subscribers đang ACTIVE
2. **Sequential operations**: Read history → Subscribe không atomic
3. **Timing-dependent**: Lỗi chỉ xảy ra khi Python publish trong cửa sổ rủi ro

### Impact

- ✅ **Phần lớn trường hợp OK**: Nếu subscribe nhanh hơn Python publish
- ❌ **Hiếm khi mất dữ liệu**: Khi timing xấu
- ⚠️ **Khó debug**: Lỗi không consistent, phụ thuộc timing
- 💔 **User experience**: Tin nhắn bị thiếu, không liền mạch

## 🔜 Next Steps

Sau khi reproduce thành công, xem file `RACE_CONDITION_FIX.md` để biết các giải pháp khắc phục.

## 📝 Notes

- Delay 2 giây chỉ để **dễ reproduce** trong test
- Trong production, cửa sổ rủi ro chỉ vài **milliseconds**
- Nhưng với traffic cao, probability xảy ra lỗi tăng lên
- Cần fix để đảm bảo 100% data consistency

---

**Created:** 2025-11-11  
**Status:** Reproduced  
**Priority:** High  
**Category:** Race Condition / Data Loss
