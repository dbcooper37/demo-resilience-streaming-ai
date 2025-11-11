#!/usr/bin/env python3
"""
Script test tích hợp để tái hiện race condition với WebSocket thật

Kịch bản:
1. Setup history với 6 chunks
2. Mở WebSocket connection (Java sẽ đọc history)
3. Trong lúc delay 2s, publish chunk 7
4. Verify chunk 7 bị mất
"""

import asyncio
import json
import time
import redis
import websockets
from datetime import datetime
import threading

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
WS_URL = 'ws://localhost:8080/ws/chat'
SESSION_ID = 'race_test_session_' + str(int(time.time()))
USER_ID = 'race_test_user'
MESSAGE_ID = 'race_test_msg_001'

# Redis client
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Track received messages
received_chunks = []
received_messages_lock = threading.Lock()

def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")

def create_chunk_message(chunk_num, accumulated_content, is_complete=False):
    """Create chunk message like Python AI Service"""
    return {
        "message_id": MESSAGE_ID,
        "session_id": SESSION_ID,
        "user_id": USER_ID,
        "role": "assistant",
        "content": accumulated_content,
        "chunk": f"word{chunk_num}",
        "timestamp": int(time.time() * 1000),
        "is_complete": is_complete
    }

def setup_initial_history():
    """Setup: Create initial history with 6 chunks"""
    log("=" * 80)
    log("STEP 0: SETUP - Creating initial history (chunks 1-6)")
    log("=" * 80)
    
    history_key = f"chat:history:{SESSION_ID}"
    
    # Clear existing
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
    
    # Add chunks 1-6
    accumulated = ""
    for i in range(1, 7):
        accumulated += f"word{i} "
        msg = create_chunk_message(i, accumulated.strip())
        redis_client.lpush(history_key, json.dumps(msg))
    
    redis_client.expire(history_key, 3600)
    
    log(f"✓ Created history with chunks 1-6")
    log(f"  Content: '{accumulated.strip()}'")
    log("")
    
    return accumulated.strip()

async def websocket_client():
    """WebSocket client to receive messages"""
    global received_chunks
    
    log("=" * 80)
    log("STEP 1: Opening WebSocket connection")
    log("=" * 80)
    
    url = f"{WS_URL}?session_id={SESSION_ID}&user_id={USER_ID}"
    log(f"Connecting to: {url}")
    
    try:
        async with websockets.connect(url) as websocket:
            log("✓ WebSocket connected")
            log("⏳ Java is now reading history from Redis (Step 1)...")
            log("")
            
            # Receive messages
            message_count = 0
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get('type')
                    
                    if msg_type == 'welcome':
                        log(f"📩 Received welcome message")
                        
                    elif msg_type == 'history':
                        messages = data.get('messages', [])
                        log(f"📚 Received history with {len(messages)} messages")
                        
                        # Extract chunks from history
                        for msg in messages:
                            if msg.get('role') == 'assistant' and not msg.get('is_complete'):
                                content = msg.get('content', '')
                                with received_messages_lock:
                                    if content and content not in received_chunks:
                                        received_chunks.append(content)
                        
                        if received_chunks:
                            log(f"  History chunks: {received_chunks}")
                        log("")
                        
                    elif msg_type == 'message':
                        msg_data = data.get('data', {})
                        role = msg_data.get('role')
                        content = msg_data.get('content', '')
                        is_complete = msg_data.get('is_complete', False)
                        
                        if role == 'assistant':
                            message_count += 1
                            
                            with received_messages_lock:
                                if content and content not in received_chunks:
                                    received_chunks.append(content)
                            
                            status = "COMPLETE" if is_complete else "STREAMING"
                            log(f"📨 [{status}] Received chunk #{message_count}: '{content}'")
                            
                            if is_complete:
                                log("✅ Stream completed")
                                break
                    
                    # Stop after 15 seconds or 20 messages
                    if message_count >= 20:
                        log("⏱️  Received enough messages, stopping...")
                        break
                        
                except json.JSONDecodeError:
                    log(f"⚠️  Failed to parse message: {message}")
                    
    except Exception as e:
        log(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()

def publish_chunk_during_delay():
    """Publish chunk 7 during the delay window"""
    log("=" * 80)
    log("BACKGROUND THREAD: Publishing chunk 7 during delay")
    log("=" * 80)
    
    # Wait for WebSocket to establish and start delay
    time.sleep(1.5)
    
    log("=" * 80)
    log("STEP 2 (RISK WINDOW): Publishing chunk 7 to Redis PubSub")
    log("=" * 80)
    log("⏰ This is happening DURING the 2-second delay")
    log("⚠️  Java has read history (chunks 1-6) but NOT subscribed yet!")
    log("")
    
    channel = f"chat:stream:{SESSION_ID}"
    accumulated = "word1 word2 word3 word4 word5 word6 word7"
    chunk7_msg = create_chunk_message(7, accumulated)
    
    log(f"📤 Publishing chunk 7 to channel: {channel}")
    log(f"   Content: '{accumulated}'")
    
    subscribers = redis_client.publish(channel, json.dumps(chunk7_msg))
    
    log(f"📡 Published to {subscribers} subscribers")
    
    if subscribers == 0:
        log("⚠️  ⚠️  ⚠️  NO SUBSCRIBERS! Chunk 7 is LOST!")
    else:
        log(f"✓ Received by {subscribers} subscribers")
    
    log("")
    
    # Also save to history (Python would do this)
    history_key = f"chat:history:{SESSION_ID}"
    redis_client.lpush(history_key, json.dumps(chunk7_msg))
    log(f"💾 Saved chunk 7 to history")
    log("")
    
    # Wait a bit, then publish chunks 8-10
    time.sleep(1.5)
    
    log("=" * 80)
    log("STEP 3: Java has now subscribed, publishing chunks 8-10")
    log("=" * 80)
    log("✓ Java should receive these chunks in real-time")
    log("")
    
    for chunk_num in range(8, 11):
        accumulated += f" word{chunk_num}"
        chunk_msg = create_chunk_message(chunk_num, accumulated)
        
        subscribers = redis_client.publish(channel, json.dumps(chunk_msg))
        log(f"📤 Published chunk {chunk_num} → {subscribers} subscriber(s)")
        time.sleep(0.1)
    
    # Final complete message
    time.sleep(0.2)
    final_msg = create_chunk_message(10, accumulated, is_complete=True)
    subscribers = redis_client.publish(channel, json.dumps(final_msg))
    log(f"✅ Published final complete message → {subscribers} subscriber(s)")
    
    # Save to history
    redis_client.lpush(history_key, json.dumps(final_msg))
    log(f"💾 Saved complete message to history")
    log("")

def verify_results():
    """Verify if chunk 7 was lost"""
    log("=" * 80)
    log("VERIFICATION: Analyzing received messages")
    log("=" * 80)
    
    with received_messages_lock:
        log(f"\n📊 Total unique messages received: {len(received_chunks)}")
        log("\nReceived content in order:")
        for i, chunk in enumerate(received_chunks, 1):
            log(f"  {i}. '{chunk}'")
    
    # Check for chunk 7
    log("\n🔍 Checking for chunk 7 (containing 'word7'):")
    
    chunk7_found = False
    with received_messages_lock:
        for chunk in received_chunks:
            if 'word7' in chunk:
                chunk7_found = True
                log(f"  ✓ Found: '{chunk}'")
                break
    
    if not chunk7_found:
        log(f"  ❌ NOT FOUND!")
        log(f"\n💔 RACE CONDITION CONFIRMED!")
        log(f"  - Chunks 1-6 were in history (received via history message)")
        log(f"  - Chunk 7 was published DURING the delay (MISSED)")
        log(f"  - Chunks 8-10 were published AFTER subscribe (received)")
        log(f"\n  Result: Client is missing chunk 7!")
    else:
        log(f"\n✓ Chunk 7 was received (race condition did not occur)")
    
    log("")
    
    # Show what should have been received
    expected_final = "word1 word2 word3 word4 word5 word6 word7 word8 word9 word10"
    log("📋 Expected final content:")
    log(f"  '{expected_final}'")
    
    with received_messages_lock:
        if received_chunks:
            actual_final = received_chunks[-1] if received_chunks else ""
            log(f"\n📋 Actual final content received:")
            log(f"  '{actual_final}'")
            
            if 'word7' not in actual_final:
                log(f"\n❌ DATA LOSS: word7 is missing!")

async def main():
    """Main test execution"""
    log("╔" + "═" * 78 + "╗")
    log("║" + " " * 20 + "RACE CONDITION REPRODUCTION TEST" + " " * 26 + "║")
    log("║" + " " * 15 + "Testing: Chunk 7 data loss due to late subscription" + " " * 11 + "║")
    log("╚" + "═" * 78 + "╝")
    log("")
    
    try:
        # Setup
        initial_content = setup_initial_history()
        
        # Start background thread to publish chunk 7 during delay
        publisher_thread = threading.Thread(target=publish_chunk_during_delay, daemon=True)
        publisher_thread.start()
        
        # Start WebSocket client
        await websocket_client()
        
        # Wait for publisher to finish
        publisher_thread.join(timeout=10)
        
        # Small delay before verification
        time.sleep(1)
        
        # Verify results
        verify_results()
        
        log("=" * 80)
        log("TEST COMPLETED")
        log("=" * 80)
        
    except Exception as e:
        log(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            redis_client.delete(f"chat:history:{SESSION_ID}")
            redis_client.delete(f"session:owner:{SESSION_ID}")
        except:
            pass

if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
