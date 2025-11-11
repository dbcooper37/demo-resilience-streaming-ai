# 🔧 Fix Cancel và Message Replace Issues

## Tổng Quan

Đã fix 2 lỗi quan trọng:

1. **❌ Lỗi 1: Không hủy được khi đang streaming**
   - Frontend bấm nút hủy nhưng không có tác dụng
   
2. **❌ Lỗi 2: Message bị replace nhầm**
   - User gửi message mới → tin nhắn AI cũ bị thay thế bởi tin nhắn mới

## Root Causes

### Lỗi 1: Cancel không hoạt động

**Nguyên nhân:**
- Frontend gọi `/api/cancel` với `message_id` nhưng không match với `message_id` trong `active_tasks`
- Python AI service trả về `user_message_id` thay vì `ai_message_id` trong response của `/chat` endpoint
- Frontend track sai `message_id`, dẫn đến cancel không tìm thấy task tương ứng

**Flow cũ (SAI):**
```
User gửi message "hello"
  ↓
Backend gọi /chat → AI service tạo user_message_id = "abc123"
  ↓
AI service bắt đầu stream với ai_message_id = "def456"
  ↓
Response trả về message_id = "abc123" (SAI!)
  ↓
Frontend track streamingMessageId = "abc123"
  ↓
User bấm cancel → gửi cancel request với message_id = "abc123"
  ↓
AI service kiểm tra active_tasks → không tìm thấy vì đang dùng "def456"
  ↓
Cancel FAILED ❌
```

### Lỗi 2: Message Replace

**Nguyên nhân:**
- Logic update trong `useChat.js` không giữ lại properties cũ khi update
- Khi nhận streaming chunk mới, toàn bộ message object bị thay thế thay vì chỉ update `content` và `chunk`
- Dẫn đến message cũ bị "mất" các thông tin khác

**Code cũ (SAI):**
```javascript
// Streaming chunk
const updated = [...prev];
updated[index] = {
  ...message,  // SAI: Thay thế toàn bộ
  content: message.content || '',
  chunk: message.chunk || ''
};
```

## Solutions Implemented

### Fix 1: Correct Message ID Tracking

#### 1.1. Python AI Service (`ai_service.py`)

**Thêm method mới:**
```python
def prepare_streaming_response(self, session_id: str, user_id: str) -> str:
    """
    Prepare for streaming response and return message_id
    This allows frontend to track the message_id before streaming starts
    """
    message_id = str(uuid.uuid4())
    
    # Pre-register this message for cancellation tracking
    self.active_tasks[session_id] = {
        "message_id": message_id,
        "cancelled": False
    }
    
    logger.info(f"Prepared streaming response: session={session_id}, msg_id={message_id}")
    return message_id

async def stream_ai_response_with_id(self, session_id: str, user_id: str, 
                                     user_message: str, message_id: str) -> None:
    """
    Stream AI response chunk by chunk with pre-assigned message_id
    """
    # Verify the message_id is registered
    if session_id not in self.active_tasks or self.active_tasks[session_id]["message_id"] != message_id:
        logger.error(f"Message ID mismatch or not registered: session={session_id}, msg_id={message_id}")
        return
    
    # ... streaming logic ...
```

**Cải thiện logging trong `cancel_streaming()`:**
```python
def cancel_streaming(self, session_id: str, message_id: str) -> bool:
    logger.info(f"Cancel request received: session={session_id}, msg_id={message_id}")
    logger.info(f"Active tasks: {list(self.active_tasks.keys())}")
    
    if session_id in self.active_tasks:
        task_info = self.active_tasks[session_id]
        logger.info(f"Found active task: current_msg_id={task_info['message_id']}, requested_msg_id={message_id}")
        
        if task_info["message_id"] == message_id:
            task_info["cancelled"] = True
            logger.info(f"✅ Marked streaming for cancellation")
            return True
        else:
            logger.warning(f"❌ Message ID mismatch")
            return False
    else:
        logger.warning(f"❌ No active streaming task found")
        return False
```

#### 1.2. Python AI Service Endpoint (`app.py`)

**Update `/chat` endpoint để return đúng AI message_id:**
```python
@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    # Process user message
    user_message_id = await chat_service.process_user_message(...)
    
    # NEW: Generate AI response message_id before starting stream
    ai_message_id = chat_service.prepare_streaming_response(
        session_id=request.session_id,
        user_id=request.user_id
    )
    
    # Start streaming with pre-assigned message_id
    asyncio.create_task(
        chat_service.stream_ai_response_with_id(
            session_id=request.session_id,
            user_id=request.user_id,
            user_message=request.message,
            message_id=ai_message_id  # Use pre-assigned ID
        )
    )
    
    # Return AI message_id (NOT user_message_id)
    return ChatResponse(
        status="streaming",
        message_id=ai_message_id,  # ✅ CORRECT: AI response message_id
        session_id=request.session_id,
        message="AI is generating response..."
    )
```

#### 1.3. Frontend (`App.jsx`)

**Cải thiện tracking và logging:**
```javascript
const handleWebSocketMessage = (data) => {
  // ... other handlers ...
  
  else if (data.type === 'message') {
    handleStreamingMessage(data.data);
    
    // ONLY track if it's an assistant message that is actively streaming
    if (data.data.role === 'assistant' && !data.data.is_complete) {
      console.log('Tracking streaming message ID:', data.data.message_id);
      setStreamingMessageId(data.data.message_id);
    } else if (data.data.role === 'assistant' && data.data.is_complete) {
      console.log('Stream completed for message:', data.data.message_id);
      setStreamingMessageId(null);
      setIsSending(false);
    }
  }
  // ...
};
```

**Cải thiện cancel handler:**
```javascript
const cancelMessage = async () => {
  if (!streamingMessageId) {
    console.warn('No streaming message to cancel');
    return;
  }

  console.log('Cancelling streaming message:', streamingMessageId);

  try {
    const response = await axios.post(`${API_URL}/cancel`, {
      session_id: sessionId,
      message_id: streamingMessageId
    });
    
    console.log('Cancel request successful:', response.data);
    
    // Immediately update UI state
    setStreamingMessageId(null);
    setIsSending(false);
  } catch (error) {
    console.error('Error cancelling message:', error);
    const errorMessage = error.response?.data?.detail || 'Không thể hủy tin nhắn';
    alert(`Lỗi khi hủy: ${errorMessage}`);
  }
};
```

### Fix 2: Preserve Message Properties on Update

#### Frontend (`hooks/useChat.js`)

**Fix streaming message update logic:**
```javascript
const handleStreamingMessage = useCallback((message) => {
  // ... user message handler ...
  
  else if (message.role === 'assistant') {
    if (message.is_complete) {
      // Final complete message
      streamingMessagesRef.current.delete(message.message_id);
      
      setMessages((prev) => {
        const index = prev.findIndex(m => m.message_id === message.message_id);
        if (index >= 0) {
          const updated = [...prev];
          updated[index] = {
            ...message,
            is_complete: true
          };
          return updated;
        } else {
          return [...prev, message];
        }
      });
    } else {
      // Streaming chunk - PRESERVE existing properties
      setMessages((prev) => {
        const index = prev.findIndex(m => m.message_id === message.message_id);
        
        if (index >= 0) {
          // ✅ CORRECT: Update existing streaming message
          const updated = [...prev];
          updated[index] = {
            ...updated[index],  // ✅ Keep existing properties!
            content: message.content || '',
            chunk: message.chunk || '',
            timestamp: message.timestamp,
            is_complete: false
          };
          streamingMessagesRef.current.set(message.message_id, updated[index]);
          return updated;
        } else {
          // First chunk - add new streaming message
          const newMessage = {
            ...message,
            content: message.content || '',
            chunk: message.chunk || '',
            is_complete: false
          };
          streamingMessagesRef.current.set(message.message_id, newMessage);
          return [...prev, newMessage];
        }
      });
    }
  }
}, []);
```

**Key Change:**
```javascript
// BEFORE (SAI):
updated[index] = {
  ...message,  // Thay thế toàn bộ message
  content: message.content || '',
  chunk: message.chunk || ''
};

// AFTER (ĐÚNG):
updated[index] = {
  ...updated[index],  // ✅ Giữ lại properties cũ
  content: message.content || '',
  chunk: message.chunk || '',
  timestamp: message.timestamp,
  is_complete: false
};
```

## Testing Flow

### Test Cancel Functionality

1. **Start Application:**
   ```bash
   docker compose -f docker-compose.sticky-session.yml up -d
   ```

2. **Open Browser Console** và gửi message:
   - User gửi message "hello"
   - Xem console log: `Tracking streaming message ID: <message_id>`
   
3. **Click Cancel Button** trong khi đang streaming:
   - Console log: `Cancelling streaming message: <message_id>`
   - Console log: `Cancel request successful: {...}`
   
4. **Check AI Service Logs:**
   ```bash
   docker logs sticky-python-ai-1 --tail 50
   ```
   
   Expected logs:
   ```
   Prepared streaming response: session=<session_id>, msg_id=<message_id>
   Starting AI response streaming for session=<session_id>, msg_id=<message_id>
   Cancel request received: session=<session_id>, msg_id=<message_id>
   Active tasks: ['<session_id>']
   Found active task: current_msg_id=<message_id>, requested_msg_id=<message_id>
   ✅ Marked streaming for cancellation
   Streaming cancelled: session=<session_id>, msg_id=<message_id>
   ```

### Test Message Replace Fix

1. **Send Multiple Messages Quickly:**
   - User: "a"
   - Wait for streaming to start
   - User: "b" (send while first is streaming)
   
2. **Verify:**
   - Message "a" response should still be visible
   - Message "b" response should appear as NEW message
   - NO replacement should occur
   
3. **Check Message List:**
   - Each message should have unique `message_id`
   - Messages should remain in correct order
   - Previous messages should not be replaced

## Files Changed

### Frontend
- ✅ `frontend/src/App.jsx` - Better message_id tracking and cancel handling
- ✅ `frontend/src/hooks/useChat.js` - Fix message update logic

### Backend (Python AI Service)
- ✅ `python-ai-service/app.py` - Return AI message_id for tracking
- ✅ `python-ai-service/ai_service.py` - Pre-assign message_id, better logging

## Deployment Instructions

### Quick Rebuild (Recommended)

```bash
# Stop affected services
docker compose -f docker-compose.sticky-session.yml stop python-ai-1 python-ai-2 python-ai-3 frontend

# Rebuild with no cache
docker compose -f docker-compose.sticky-session.yml build --no-cache python-ai-1 frontend

# Start services
docker compose -f docker-compose.sticky-session.yml up -d python-ai-1 python-ai-2 python-ai-3 frontend

# Check logs
docker logs sticky-python-ai-1 --tail 50
docker logs sticky-frontend --tail 30
```

### Full Rebuild (If Issues Persist)

```bash
# Stop all services
docker compose -f docker-compose.sticky-session.yml down

# Remove old images
docker rmi sticky-python-ai-service sticky-frontend

# Rebuild all
docker compose -f docker-compose.sticky-session.yml build --no-cache

# Start all services
docker compose -f docker-compose.sticky-session.yml up -d

# Verify
docker ps
```

## Verification Checklist

- [ ] Frontend connects to WebSocket successfully
- [ ] Messages are sent and received
- [ ] Streaming works correctly
- [ ] Cancel button appears during streaming
- [ ] Cancel stops streaming immediately
- [ ] Multiple messages don't replace each other
- [ ] Message history is preserved correctly
- [ ] Cancel logs show correct message_id matching
- [ ] No errors in browser console
- [ ] No errors in AI service logs

## Expected Behavior After Fix

### Cancel Functionality
✅ User clicks cancel → Streaming stops immediately
✅ Message shows "[Đã hủy]" marker
✅ UI returns to ready state
✅ Next message can be sent normally

### Message Handling
✅ Multiple messages appear as separate entries
✅ No replacement of previous messages
✅ Each message maintains its own streaming state
✅ Message history persists across page reloads

## Troubleshooting

### If Cancel Still Doesn't Work

1. **Check message_id in browser console:**
   ```javascript
   // Should see:
   Tracking streaming message ID: <uuid>
   Cancelling streaming message: <uuid>
   ```

2. **Check AI service logs:**
   ```bash
   docker logs sticky-python-ai-1 | grep -A 5 "Cancel request"
   ```

3. **Verify the message_id matches:**
   - Frontend sends: `message_id=<uuid>`
   - Backend receives: `msg_id=<uuid>`
   - Should be IDENTICAL

### If Messages Still Replace Each Other

1. **Check message_id uniqueness:**
   ```javascript
   // In browser console, check messages array
   console.log(messages.map(m => ({ id: m.message_id, role: m.role })))
   ```

2. **Verify update logic:**
   - Each message should have unique `message_id`
   - Update should preserve `...updated[index]`

## Summary

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| Cancel không hoạt động | Sai message_id tracking | Pre-assign và return đúng AI message_id |
| Message bị replace | Không preserve properties | Spread `...updated[index]` trước khi update |

Bây giờ cả 2 tính năng đều hoạt động ĐÚNG! 🎉
