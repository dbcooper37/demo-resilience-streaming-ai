# 🐛 Race Condition Bug: Chunk 7 Data Loss

## 📖 Quick Summary

This repository contains a **reproduced race condition bug** in the WebSocket streaming system that causes **data loss** when clients reconnect during active streaming.

## 🎯 The Bug

**Symptom:** Client receives chunks `1,2,3,4,5,6,8,9,10` but **missing chunk 7**

**Root Cause:** Gap between reading history and subscribing to Pub/Sub

**Impact:** User sees incomplete messages with missing content

## 📁 Files in This Repository

### Documentation

1. **`RACE_CONDITION_REPRODUCTION.md`** ⭐ START HERE
   - Step-by-step reproduction guide
   - Expected results
   - Verification checklist

2. **`RACE_CONDITION_ANALYSIS.md`**
   - Deep technical analysis
   - Code walkthrough
   - Impact assessment

3. **`DOCUMENTATION.md`**
   - Original system architecture
   - Section about the race condition issue

### Test Scripts

4. **`test_race_condition.py`**
   - Simple simulation test (no real services needed)
   - Demonstrates the timing issue with Redis

5. **`test_integrated_race_condition.py`**
   - Full integration test with real WebSocket
   - Requires running services

6. **`run_race_condition_test.sh`**
   - Automated test runner
   - Checks prerequisites and runs both tests

### Modified Code

7. **`java-websocket-server/src/main/java/com/demo/websocket/handler/ChatWebSocketHandler.java`**
   - **Lines 103-113:** Added 2-second delay to expand risk window
   - Makes the race condition **easy to reproduce**

## 🚀 Quick Start

### Option 1: Read Documentation (5 minutes)

```bash
# Read the reproduction guide
cat RACE_CONDITION_REPRODUCTION.md

# Read the technical analysis
cat RACE_CONDITION_ANALYSIS.md
```

### Option 2: Run Simulation Test (2 minutes)

```bash
# Install dependencies
pip3 install redis

# Run simple simulation
python3 test_race_condition.py
```

**Expected output:**
```
=== T1: Java Node 2 reads history from Redis ===
✓ Read 7 items from history
📊 History contains up to chunk 6

=== T2 (RISK WINDOW): Python AI Service publishes chunk 7 ===
⚠️  Published to 0 subscribers
⚠️  Chunk 7 is LOST for this connection!

💔 RESULT: DATA LOSS!
```

### Option 3: Full Integration Test (10 minutes)

```bash
# 1. Start services
docker-compose up -d redis java-websocket-1 python-ai-1

# 2. Install dependencies
pip3 install redis websockets

# 3. Run integrated test
python3 test_integrated_race_condition.py
```

Or use the automated runner:
```bash
./run_race_condition_test.sh
```

## 🔍 What You'll See

### In Java Logs

```
[12:34:56.123] INFO  Sent 6 history messages to session race_test_session
[12:34:56.124] WARN  ⚠️ RACE CONDITION TEST: Sleeping 2 seconds before subscribe...
[12:34:56.124] WARN  ⚠️ If Python publishes chunk 7 during this window, it will be LOST!
[12:34:58.124] WARN  ⚠️ RACE CONDITION TEST: Delay complete, now subscribing...
[12:34:58.125] INFO  === SUBSCRIBING TO CHANNEL: chat:stream:race_test_session ===
```

### In Test Output

```
📊 Total unique messages received: 9
  
Received content in order:
  1. 'word1'
  2. 'word1 word2'
  3. 'word1 word2 word3'
  4. 'word1 word2 word3 word4'
  5. 'word1 word2 word3 word4 word5'
  6. 'word1 word2 word3 word4 word5 word6'
  7. 'word1 word2 word3 word4 word5 word6 word8'        ← Missing word7!
  8. 'word1 word2 word3 word4 word5 word6 word8 word9'
  9. 'word1 word2 ... word6 word8 word9 word10'

🔍 Checking for chunk 7 (containing 'word7'):
  ❌ NOT FOUND!

💔 RACE CONDITION CONFIRMED!
```

### In Redis Monitor

```bash
redis-cli monitor | grep chat:stream
```

Output:
```
1234567891.123 [0 127.0.0.1:12345] "PUBLISH" "chat:stream:xxx" "{\"content\":\"...word7...\"}"
# Returns: (integer) 0  ← No subscribers!

1234567893.123 [0 127.0.0.1:12346] "SUBSCRIBE" "chat:stream:xxx"
# Subscription happens 2 seconds AFTER chunk 7 was published
```

## 🎬 Timeline Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│  T0: Setup                                                       │
│  └─ Redis history: [chunk1, chunk2, chunk3, chunk4, chunk5,    │
│     chunk6]                                                      │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  T1: Java Node 2 - WebSocket Connection                         │
│  └─ Read history from Redis                                     │
│  └─ Send to client: chunks 1-6                                  │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  RISK WINDOW (2 seconds in test, ~5ms in production)       │
│                                                                  │
│  T2: Python AI Service publishes chunk 7                        │
│  └─ PUBLISH to "chat:stream:xxx"                                │
│  └─ 0 subscribers → Message LOST!                               │
│                                                                  │
│  T3: Python saves chunk 7 to history                            │
│  └─ LPUSH to "chat:history:xxx"                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  T4: Java Node 2 - Subscribe to PubSub                          │
│  └─ SUBSCRIBE to "chat:stream:xxx"                              │
│  └─ Now listening for NEW messages                              │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  T5+: Python continues streaming                                │
│  └─ Publishes chunks 8, 9, 10                                   │
│  └─ Java receives and forwards to client ✓                      │
└─────────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│  Result: Client Display                                         │
│  ✓ Chunks: 1, 2, 3, 4, 5, 6, 8, 9, 10                          │
│  ❌ Missing: 7                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 🎯 Key Takeaways

### 1. The Problem

```java
// Current code (BUGGY)
sendChatHistory(wsSession, sessionId);        // Step 1: Read
// ⚠️ GAP: Python might publish here
chatOrchestrator.startStreamingSession(...);  // Step 3: Subscribe
```

### 2. Why It Happens

- Redis Pub/Sub delivers messages **only to active subscribers**
- If you're not subscribed when message is published → **LOST**
- Can't retrieve past Pub/Sub messages

### 3. When It Happens

- Page reload during streaming (most common)
- Network reconnection
- Load balancer rerouting
- Any scenario where connection is re-established

### 4. Impact

- **User experience:** Incomplete messages
- **Data integrity:** Violated
- **Trust:** Reduced
- **Recovery:** Manual refresh needed (might lose more data)

## 📚 Additional Resources

### In This Repository

- `DOCUMENTATION.md` - System architecture overview
- `README.md` - Project main README

### Related Topics

- Redis Pub/Sub limitations
- WebSocket reconnection patterns
- Distributed systems consistency
- Event sourcing vs message queues

## 🔧 Next Steps

After understanding the bug:

1. **Read** `RACE_CONDITION_ANALYSIS.md` for deep dive
2. **Run** tests to see it yourself
3. **Review** potential fixes (coming soon in `RACE_CONDITION_FIX.md`)
4. **Implement** the chosen solution
5. **Test** to verify fix works

## 💡 Solutions Preview

Some potential fixes (detailed analysis coming):

1. **Subscribe-First Pattern**
   - Subscribe BEFORE reading history
   - Then filter out duplicates

2. **Redis Streams Instead of Pub/Sub**
   - Persistent messages
   - Can read from last seen ID

3. **Sequence Number Validation**
   - Client detects gaps
   - Requests missing chunks from history

4. **Kafka or RabbitMQ**
   - Better at-least-once delivery
   - Offset-based consumption

## 📞 Questions?

If you have questions about:
- How to reproduce the bug → See `RACE_CONDITION_REPRODUCTION.md`
- Why it happens → See `RACE_CONDITION_ANALYSIS.md`
- How to fix it → Coming soon in `RACE_CONDITION_FIX.md`

---

**Status:** ✅ Reproduced Successfully  
**Date:** 2025-11-11  
**Priority:** HIGH  
**Complexity:** Medium  
**Fix:** In Progress
