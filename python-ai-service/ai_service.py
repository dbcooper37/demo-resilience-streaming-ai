"""
AI Service for generating responses
"""
import asyncio
import logging
from typing import AsyncGenerator
import uuid

from config import settings
from models import ChatMessage
from redis_client import redis_client


logger = logging.getLogger(__name__)


class AIService:
    """AI response generation service"""
    
    SAMPLE_RESPONSES = [
        """Xin chào! Tôi là AI assistant được xây dựng với công nghệ streaming hiện đại. Tôi có thể giúp bạn trả lời các câu hỏi, giải thích khái niệm phức tạp, viết code, phân tích dữ liệu và nhiều thứ khác. 

Hệ thống của tôi sử dụng kiến trúc microservices với WebSocket để giao tiếp real-time, Redis để caching và message queue, và Kafka để xử lý event-driven architecture. Điều này đảm bảo response của tôi được stream một cách mượt mà và có thể scale tốt khi có nhiều người dùng đồng thời.

Bạn có câu hỏi gì cho tôi hôm nay không?""",

        """Đây là một ví dụ chi tiết về streaming response trong hệ thống phân tán. Khi bạn gửi một tin nhắn, nó sẽ đi qua nhiều layer:

1. **Frontend Layer**: Tin nhắn được gửi từ React app qua WebSocket connection tới Java WebSocket Server
2. **API Gateway Layer**: Java server nhận request, validate và forward tới Python AI Service thông qua REST API
3. **AI Processing Layer**: Python service xử lý và tạo response theo dạng streaming
4. **Message Queue Layer**: Mỗi chunk được publish lên Redis PubSub channel
5. **Real-time Distribution**: Java WebSocket Handler subscribe channel đó và forward chunks về client

Toàn bộ quá trình này diễn ra trong vài milliseconds, tạo trải nghiệm real-time tuyệt vời cho người dùng. Hệ thống còn có khả năng recover khi connection bị gián đoạn, lưu lịch sử chat vào Redis để bạn có thể reload trang bất cứ lúc nào mà không mất dữ liệu.""",

        """Một tính năng quan trọng của hệ thống này là khả năng phục hồi (resilience) và persistence. Khi bạn reload trang web trong khi AI đang trả lời, điều thú vị sẽ xảy ra:

**Trước khi reload:**
- Tất cả messages đang hiển thị được lưu trong state của React component
- AI đang streaming response, mỗi chunk được cache trong Redis Stream
- WebSocket connection đang active và nhận real-time updates

**Trong quá trình reload:**
- Browser đóng WebSocket connection cũ
- AI service vẫn tiếp tục generate và lưu response vào Redis
- Không có data loss vì mọi thứ đều được persist

**Sau khi reload:**
- React app khởi động lại và tạo WebSocket connection mới
- Server gửi toàn bộ lịch sử chat từ Redis (bao gồm cả message đang streaming)
- Nếu AI vẫn đang generate, bạn sẽ tiếp tục thấy streaming từ vị trí hiện tại
- UI hiển thị seamlessly như chưa hề reload!

Đây là implementation của offline-first architecture pattern kết hợp với event sourcing.""",

        """Redis đóng vai trò trung tâm trong kiến trúc của hệ thống này với nhiều use cases khác nhau:

**1. Redis Streams cho Message Queue:**
- Mỗi session có một stream riêng (key: `stream:session:{session_id}`)
- Chunks được append vào stream với XADD command
- Consumer groups đảm bảo message không bị miss
- Có TTL để tự động cleanup old data

**2. Redis PubSub cho Real-time Broadcasting:**
- Channel: `chat:session:{session_id}`
- Publisher (Python AI) push chunks vào channel
- Subscriber (Java WebSocket) forward đến clients
- Low latency, high throughput

**3. Redis Hash cho Session Storage:**
- Lưu metadata: user_id, start_time, last_activity
- Track active streaming messages
- Store conversation context

**4. Redis Sorted Set cho History:**
- Messages được indexed theo timestamp
- Query efficient với ZRANGE commands
- Support pagination cho chat history dài

Kiến trúc này cho phép system scale horizontally bằng cách add thêm Redis nodes (cluster mode) và load balance across multiple backend instances.""",

        """Cảm ơn bạn đã hỏi! Để trả lời câu hỏi này một cách đầy đủ, tôi sẽ phân tích từ nhiều góc độ khác nhau:

**Về mặt kỹ thuật:** Hệ thống được thiết kế theo microservices pattern với separation of concerns rõ ràng. Java backend xử lý WebSocket connections và orchestration, Python service focus vào AI logic, Redis làm message broker và cache layer. Điều này tạo ra loose coupling giữa các components.

**Về mặt performance:** Với streaming approach, user thấy response ngay lập tức thay vì phải chờ toàn bộ answer được generate xong. Time to first byte (TTFB) rất thấp. Concurrent users được handle tốt nhờ async/await pattern trong cả Java (CompletableFuture) và Python (asyncio).

**Về mặt scalability:** System có thể scale từng component độc lập. Cần xử lý nhiều AI requests hơn? Scale Python service. Cần handle nhiều WebSocket connections hơn? Scale Java backend. Redis có thể chạy cluster mode với sharding.

**Về mặt reliability:** Multiple layers of fault tolerance: connection recovery, message retry mechanism, graceful degradation. Monitoring với Prometheus và Grafana dashboard để track metrics real-time.

Nếu bạn cần giải thích chi tiết về bất kỳ phần nào, cứ hỏi tôi nhé!""",

        """Tôi rất vui được giải thích về workflow chi tiết của một request trong hệ thống streaming chat này:

**Phase 1: Request Initiation (Frontend → Java Backend)**
- User nhập message và click Send
- React app tạo ChatMessage object với unique message_id (UUID)
- POST request được gửi tới `/api/chat` endpoint của Java backend
- Request body: `{session_id, message, user_id}`

**Phase 2: Request Validation & Orchestration (Java Backend)**
- ChatController nhận request
- Validate input: check message không empty, session_id hợp lệ
- RateLimitService check user không spam
- SessionManager tạo hoặc retrieve session
- ChatOrchestrator được invoke để handle business logic

**Phase 3: AI Service Invocation (Java → Python)**
- Java backend gọi Python AI service qua REST API
- Endpoint: `POST /api/chat/streaming`
- Python service nhận request và bắt đầu generate response

**Phase 4: Streaming Generation (Python AI Service)**
- AIService.select_response() chọn appropriate response
- generate_streaming_response() split text thành words
- Mỗi word được yield với delay nhỏ (simulate AI thinking)
- Chunks được accumulate để tạo full content

**Phase 5: Message Publishing (Python → Redis)**
- Mỗi chunk được publish lên Redis PubSub channel
- Channel name: `chat:session:{session_id}`
- Message format: JSON with metadata (message_id, chunk, content, is_complete)
- Simultaneously save to Redis Stream for persistence

**Phase 6: Real-time Distribution (Redis → Java → Client)**
- Java WebSocket Handler subscribe Redis channel
- Nhận chunks từ Redis PubSub
- Forward chunks tới WebSocket clients
- Client browser nhận và render từng chunk real-time

**Phase 7: Completion & Finalization**
- Last chunk có flag `is_complete: true`
- Final message được save vào conversation history
- Metrics được ghi lại (duration, chunk count, etc.)
- Resources được cleanup

Toàn bộ flow này diễn ra trong vài giây với latency rất thấp nhờ async processing!""",
    ]
    
    @classmethod
    async def generate_streaming_response(cls, text: str) -> AsyncGenerator[str, None]:
        """
        Generate streaming response word by word
        Simulates AI processing with delay between words
        """
        words = text.split()
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(settings.STREAM_DELAY)
            yield chunk
    
    @classmethod
    def select_response(cls, user_message: str) -> str:
        """
        Select appropriate response based on user message
        In real implementation, this would call an actual AI model
        """
        message_lower = user_message.lower()
        
        if "streaming" in message_lower:
            return cls.SAMPLE_RESPONSES[1]
        elif "reload" in message_lower or "history" in message_lower or "persistence" in message_lower:
            return cls.SAMPLE_RESPONSES[2]
        elif "redis" in message_lower or "pubsub" in message_lower:
            return cls.SAMPLE_RESPONSES[3]
        elif "workflow" in message_lower or "flow" in message_lower or "process" in message_lower:
            return cls.SAMPLE_RESPONSES[5]  # Detailed workflow explanation
        elif any(word in message_lower for word in ["how", "what", "why", "when", "where"]):
            return cls.SAMPLE_RESPONSES[4]
        else:
            return cls.SAMPLE_RESPONSES[0]


class ChatService:
    """Service for handling chat operations"""
    
    def __init__(self):
        self.ai_service = AIService()
        # Track active streaming tasks for cancellation
        self.active_tasks = {}  # session_id -> {"message_id": str, "cancelled": bool}
        # Track recently completed/cancelled messages to handle duplicate cancel requests
        self.completed_messages = {}  # session_id -> {"message_id": str, "completed_at": timestamp}
    
    async def process_user_message(self, session_id: str, user_id: str, 
                                   message_content: str) -> str:
        """
        Process user message and return message ID
        """
        message_id = str(uuid.uuid4())
        
        # Create user message
        user_message = ChatMessage.create_user_message(
            message_id=message_id,
            session_id=session_id,
            user_id=user_id,
            content=message_content
        )
        
        # Save to history
        redis_client.save_to_history(session_id, user_message)
        
        # Publish to PubSub
        redis_client.publish_message(session_id, user_message)
        
        logger.info(f"Processed user message: session={session_id}, msg_id={message_id}")
        
        return message_id
    
    async def stream_ai_response(self, session_id: str, user_id: str, 
                                 user_message: str) -> str:
        """
        Stream AI response chunk by chunk
        Returns the message_id for tracking
        """
        message_id = str(uuid.uuid4())
        
        # Track this streaming task
        self.active_tasks[session_id] = {
            "message_id": message_id,
            "cancelled": False
        }
        
        logger.info(f"Starting AI response streaming for session={session_id}, msg_id={message_id}")
        
        # Select response based on user message
        response_text = AIService.select_response(user_message)
        logger.info(f"Selected response text (length={len(response_text)}): {response_text[:50]}...")
        
        accumulated_content = ""
        chunk_count = 0
        cancelled = False
        
        try:
            # Stream response word by word
            async for chunk in AIService.generate_streaming_response(response_text):
                # Check if cancelled
                if self.active_tasks.get(session_id, {}).get("cancelled", False):
                    logger.info(f"Streaming cancelled for session={session_id}, msg_id={message_id}")
                    cancelled = True
                    break
                
                accumulated_content += chunk
                chunk_count += 1
                
                # Create streaming message
                stream_message = ChatMessage.create_assistant_message(
                    message_id=message_id,
                    session_id=session_id,
                    user_id=user_id,
                    content=accumulated_content,
                    is_complete=False,
                    chunk=chunk
                )
                
                # Publish to Redis PubSub
                published = redis_client.publish_message(session_id, stream_message)
                logger.debug(f"Published chunk #{chunk_count} to Redis: chunk='{chunk}', accumulated_length={len(accumulated_content)}, published={published}")
                
                await asyncio.sleep(settings.CHUNK_DELAY)
            
            if cancelled:
                # Send cancellation message
                cancel_message = ChatMessage.create_assistant_message(
                    message_id=message_id,
                    session_id=session_id,
                    user_id=user_id,
                    content=accumulated_content + "\n\n[Đã hủy]",
                    is_complete=True
                )
                redis_client.publish_message(session_id, cancel_message)
                redis_client.save_to_history(session_id, cancel_message)
                logger.info(f"Streaming cancelled: session={session_id}, msg_id={message_id}, chunks={chunk_count}")
            else:
                # Send final complete message
                final_message = ChatMessage.create_assistant_message(
                    message_id=message_id,
                    session_id=session_id,
                    user_id=user_id,
                    content=accumulated_content,
                    is_complete=True
                )
                
                # Publish final message
                published = redis_client.publish_message(session_id, final_message)
                logger.info(f"Published final complete message: published={published}")
                
                # Save to history
                redis_client.save_to_history(session_id, final_message)
                
                logger.info(f"Completed AI response streaming: session={session_id}, msg_id={message_id}, chunks={chunk_count}, total_length={len(accumulated_content)}")
            
        except asyncio.CancelledError:
            logger.info(f"Streaming task cancelled externally: session={session_id}, msg_id={message_id}")
            # Send cancellation message
            cancel_message = ChatMessage.create_assistant_message(
                message_id=message_id,
                session_id=session_id,
                user_id=user_id,
                content=accumulated_content + "\n\n[Đã hủy]",
                is_complete=True
            )
            redis_client.publish_message(session_id, cancel_message)
            redis_client.save_to_history(session_id, cancel_message)
            raise
        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            
            # Send error message
            error_message = ChatMessage.create_assistant_message(
                message_id=message_id,
                session_id=session_id,
                user_id=user_id,
                content="Xin lỗi, đã có lỗi xảy ra khi xử lý yêu cầu của bạn.",
                is_complete=True
            )
            redis_client.publish_message(session_id, error_message)
            redis_client.save_to_history(session_id, error_message)
        finally:
            # Clean up tracking and mark as completed
            if session_id in self.active_tasks:
                del self.active_tasks[session_id]
            
            # Track as completed for 30 seconds to handle duplicate cancel requests
            import time
            self.completed_messages[session_id] = {
                "message_id": message_id,
                "completed_at": time.time()
            }
            
            # Clean up old completed messages (older than 30 seconds)
            current_time = time.time()
            expired_sessions = [sid for sid, info in self.completed_messages.items() 
                              if current_time - info["completed_at"] > 30]
            for sid in expired_sessions:
                del self.completed_messages[sid]
        
        return message_id
    
    def cancel_streaming(self, session_id: str, message_id: str) -> bool:
        """
        Cancel an active streaming task
        Returns True if cancellation was successful
        """
        # Check if there's an active task
        if session_id in self.active_tasks:
            task_info = self.active_tasks[session_id]
            if task_info["message_id"] == message_id:
                # Check if already marked as cancelled
                if task_info.get("cancelled", False):
                    logger.info(f"Streaming already marked for cancellation: session={session_id}, msg_id={message_id}")
                    return True  # Return True to indicate it's being handled
                else:
                    task_info["cancelled"] = True
                    logger.info(f"Marked streaming for cancellation: session={session_id}, msg_id={message_id}")
                    return True
            else:
                logger.warning(f"Message ID mismatch for cancellation: expected={task_info['message_id']}, got={message_id}")
                return False
        
        # Check if this message was recently completed
        if session_id in self.completed_messages:
            completed_info = self.completed_messages[session_id]
            if completed_info["message_id"] == message_id:
                logger.info(f"Message already completed: session={session_id}, msg_id={message_id}")
                return True  # Return True to indicate the message is no longer streaming
        
        logger.warning(f"No active or recent streaming task found for session={session_id}, msg_id={message_id}")
        return False


# Global chat service instance
chat_service = ChatService()
