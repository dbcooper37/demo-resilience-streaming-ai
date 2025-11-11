#!/usr/bin/env python3
"""
Script để tái hiện race condition: Mất chunk 7 do subscribe muộn

Kịch bản:
T1: Java Node 2 đọc lịch sử từ Redis (có đến chunk 6)
T2: Python AI Service publish chunk 7 lên Pub/Sub (nhưng Node 2 chưa subscribe)
T3: Python save chunk 7 vào history
T4: Java Node 2 subscribe (từ giờ mới nhận được chunk 8+)

Hậu quả: Client nhận chunk 1-6, bỏ lỡ chunk 7, nhận chunk 8+
"""

import asyncio
import json
import time
import redis
from datetime import datetime

# Redis connection
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

SESSION_ID = "test_race_condition_session"
MESSAGE_ID = "test_message_001"
USER_ID = "test_user"

def log(message):
    """Log với timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def create_chunk_message(chunk_num, content, is_complete=False):
    """Tạo message chunk giống như Python AI Service"""
    return {
        "message_id": MESSAGE_ID,
        "session_id": SESSION_ID,
        "user_id": USER_ID,
        "role": "assistant",
        "content": content,  # Accumulated content
        "chunk": f"chunk{chunk_num} ",  # Current word
        "timestamp": int(time.time() * 1000),
        "is_complete": is_complete
    }

def setup_initial_history():
    """Setup: Tạo lịch sử ban đầu với 6 chunks"""
    log("=== SETUP: Creating initial history (chunks 1-6) ===")
    
    # Clear existing data
    history_key = f"chat:history:{SESSION_ID}"
    redis_client.delete(history_key)
    
    # Add user message
    user_msg = {
        "message_id": "user_msg_001",
        "session_id": SESSION_ID,
        "user_id": USER_ID,
        "role": "user",
        "content": "Test message",
        "timestamp": int(time.time() * 1000)
    }
    redis_client.lpush(history_key, json.dumps(user_msg))
    log(f"✓ Added user message to history")
    
    # Add first 6 chunks to history (accumulated)
    accumulated = ""
    for i in range(1, 7):
        accumulated += f"chunk{i} "
        msg = create_chunk_message(i, accumulated, is_complete=False)
        redis_client.lpush(history_key, json.dumps(msg))
    
    log(f"✓ Added chunks 1-6 to history: '{accumulated.strip()}'")
    redis_client.expire(history_key, 3600)  # 1 hour TTL
    
    return accumulated

def simulate_java_node_reads_history():
    """T1: Java Node đọc lịch sử (có đến chunk 6)"""
    log("\n=== T1: Java Node 2 reads history from Redis ===")
    
    history_key = f"chat:history:{SESSION_ID}"
    history_items = redis_client.lrange(history_key, 0, -1)
    
    log(f"✓ Read {len(history_items)} items from history")
    
    # Parse và hiển thị
    for item in reversed(history_items):  # Reverse để hiển thị đúng thứ tự
        msg = json.loads(item)
        if msg['role'] == 'assistant':
            log(f"  - Assistant message: '{msg['content']}'")
        else:
            log(f"  - User message: '{msg['content']}'")
    
    log("📊 History contains up to chunk 6")
    return history_items

def simulate_python_publishes_chunk7(accumulated_before):
    """T2: Python AI Service publishes chunk 7 to PubSub (MISSED!)"""
    log("\n=== T2 (RISK WINDOW): Python AI Service publishes chunk 7 ===")
    
    channel = f"chat:stream:{SESSION_ID}"
    accumulated = accumulated_before + "chunk7 "
    chunk7_msg = create_chunk_message(7, accumulated, is_complete=False)
    
    log(f"📤 Publishing chunk 7 to channel: {channel}")
    log(f"   Content: '{accumulated}'")
    
    # Publish to PubSub
    subscribers = redis_client.publish(channel, json.dumps(chunk7_msg))
    
    log(f"⚠️  Published to {subscribers} subscribers")
    log(f"⚠️  But Java Node 2 has NOT subscribed yet!")
    log(f"⚠️  Chunk 7 is LOST for this connection!")
    
    return accumulated

def simulate_python_saves_chunk7_to_history(accumulated):
    """T3: Python saves chunk 7 to history"""
    log("\n=== T3: Python AI Service saves chunk 7 to history ===")
    
    history_key = f"chat:history:{SESSION_ID}"
    chunk7_msg = create_chunk_message(7, accumulated, is_complete=False)
    
    redis_client.lpush(history_key, json.dumps(chunk7_msg))
    log(f"✓ Saved chunk 7 to history: '{accumulated}'")
    log(f"💾 History now contains chunks 1-7")

def simulate_java_node_subscribes():
    """T4: Java Node subscribes (TOO LATE for chunk 7)"""
    log("\n=== T4: Java Node 2 subscribes to channel ===")
    
    channel = f"chat:stream:{SESSION_ID}"
    log(f"✓ Java Node 2 now SUBSCRIBING to: {channel}")
    log(f"🎧 From now on, will receive chunks 8, 9, 10...")
    log(f"❌ But chunk 7 was already MISSED!")

def simulate_python_publishes_remaining_chunks(accumulated_before):
    """Simulate: Python continues publishing chunks 8, 9, 10"""
    log("\n=== AFTER T4: Python continues streaming (chunks 8, 9, 10) ===")
    
    channel = f"chat:stream:{SESSION_ID}"
    accumulated = accumulated_before
    
    for chunk_num in range(8, 11):
        accumulated += f"chunk{chunk_num} "
        chunk_msg = create_chunk_message(chunk_num, accumulated, is_complete=False)
        
        subscribers = redis_client.publish(channel, json.dumps(chunk_msg))
        log(f"📤 Published chunk {chunk_num} → {subscribers} subscribers will receive it")
        time.sleep(0.05)
    
    # Final complete message
    final_msg = create_chunk_message(10, accumulated, is_complete=True)
    redis_client.publish(channel, json.dumps(final_msg))
    log(f"✅ Published final complete message")
    
    # Save final to history
    history_key = f"chat:history:{SESSION_ID}"
    redis_client.lpush(history_key, json.dumps(final_msg))
    log(f"💾 Saved complete message to history")
    
    return accumulated

def verify_data_loss():
    """Verify: Kiểm tra dữ liệu bị mất"""
    log("\n=== VERIFICATION: Data Loss Analysis ===")
    
    history_key = f"chat:history:{SESSION_ID}"
    history_items = redis_client.lrange(history_key, 0, -1)
    
    log(f"📊 Full history in Redis ({len(history_items)} items):")
    for item in reversed(history_items):
        msg = json.loads(item)
        if msg['role'] == 'assistant':
            log(f"  ✓ '{msg['content']}'")
    
    log("\n🔍 What did the client receive?")
    log("  1. Initial history: chunks 1-6 (from T1)")
    log("  2. ❌ MISSED: chunk 7 (published at T2 before subscribe)")
    log("  3. Live stream: chunks 8, 9, 10 (after T4 subscribe)")
    
    log("\n💔 RESULT: DATA LOSS!")
    log("  - Client received: chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk8 chunk9 chunk10")
    log("  - Missing: chunk7")
    log("  - Full message should be: chunk1 chunk2 chunk3 chunk4 chunk5 chunk6 chunk7 chunk8 chunk9 chunk10")

def main():
    """Main test execution"""
    log("=" * 80)
    log("RACE CONDITION REPRODUCTION TEST")
    log("Testing: Chunk 7 data loss due to late subscription")
    log("=" * 80)
    
    try:
        # Setup
        accumulated = setup_initial_history()
        
        time.sleep(0.5)  # Small delay
        
        # T1: Java reads history
        simulate_java_node_reads_history()
        
        time.sleep(0.2)  # Delay to simulate processing time
        
        # T2: Python publishes chunk 7 (MISSED!)
        accumulated = simulate_python_publishes_chunk7(accumulated)
        
        time.sleep(0.1)
        
        # T3: Python saves chunk 7 to history
        simulate_python_saves_chunk7_to_history(accumulated)
        
        time.sleep(0.1)
        
        # T4: Java subscribes (too late)
        simulate_java_node_subscribes()
        
        time.sleep(0.2)
        
        # Continue with chunks 8, 9, 10
        accumulated = simulate_python_publishes_remaining_chunks(accumulated)
        
        time.sleep(0.5)
        
        # Verify data loss
        verify_data_loss()
        
        log("\n" + "=" * 80)
        log("TEST COMPLETED")
        log("=" * 80)
        
    except Exception as e:
        log(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
