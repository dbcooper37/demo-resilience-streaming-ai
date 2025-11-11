#!/usr/bin/env python3
"""
Test script to reproduce the Chunk 7 Data Loss Bug

Bug Scenario (described in documentation):
- T1: Java Node 2 reads history from Redis → gets chunks 1-6
- T2 (Risk Window): Python AI publishes chunk 7 to PubSub → Node 2 not subscribed yet, MISSED!
- T3: Python AI saves chunk 7 to chat:history
- T4: Java Node 2 subscribes to PubSub → starts listening
- Result: Client received chunks 1-6 from history, missed chunk 7, will receive 8+ from PubSub

This script simulates this race condition by:
1. Setting up history with chunks 1-6
2. Simulating a new client connection (reads history)
3. Publishing chunk 7 during the "risk window" (before subscription)
4. Subscribing to PubSub
5. Publishing chunks 8+
6. Verifying that chunk 7 was missed
"""

import redis
import json
import time
import threading
import sys
from datetime import datetime
from typing import List

# Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
SESSION_ID = "test_race_condition_session"
MESSAGE_ID = "msg_race_test_001"


class RaceConditionTest:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
        self.pubsub = None
        self.received_chunks = []
        self.pubsub_started = False
        self.chunk7_published = False
        
    def cleanup(self):
        """Clean up Redis keys"""
        print("🧹 Cleaning up Redis keys...")
        self.redis_client.delete(f"chat:history:{SESSION_ID}")
        print("✅ Cleanup complete\n")
        
    def setup_initial_history(self):
        """Setup history with chunks 1-6 (simulating already existing messages)"""
        print("📝 Step 0: Setting up initial history with chunks 1-6...")
        
        for i in range(1, 7):
            chunk_message = {
                "message_id": MESSAGE_ID,
                "session_id": SESSION_ID,
                "user_id": "test_user",
                "role": "assistant",
                "content": f"Word " * i,  # Accumulated content
                "chunk": f"Word {i} ",
                "timestamp": int(time.time() * 1000),
                "is_complete": False
            }
            
            # Save to history
            key = f"chat:history:{SESSION_ID}"
            self.redis_client.rpush(key, json.dumps(chunk_message))
            
        print(f"✅ History initialized with 6 chunks\n")
        
    def simulate_read_history(self) -> List[dict]:
        """T1: Simulate Java Node reading history from Redis"""
        print("=" * 80)
        print("⏰ T1: Java Node 2 reads history from Redis")
        print("=" * 80)
        
        key = f"chat:history:{SESSION_ID}"
        history_json = self.redis_client.lrange(key, 0, -1)
        history = [json.loads(msg) for msg in history_json]
        
        print(f"📖 Retrieved {len(history)} messages from history")
        for i, msg in enumerate(history, 1):
            print(f"   - Chunk {i}: content='{msg['content'].strip()[:30]}...'")
            
        print(f"✅ History contains chunks 1-{len(history)}")
        print()
        
        return history
        
    def simulate_risk_window_publish(self):
        """T2: Python AI publishes chunk 7 BEFORE subscription (RISK WINDOW)"""
        print("=" * 80)
        print("⏰ T2: 🚨 RISK WINDOW - Python AI publishes chunk 7 (Node not subscribed yet!)")
        print("=" * 80)
        
        # Small delay to ensure we're in the risk window
        time.sleep(0.1)
        
        chunk7_message = {
            "message_id": MESSAGE_ID,
            "session_id": SESSION_ID,
            "user_id": "test_user",
            "role": "assistant",
            "content": "Word " * 7,  # Accumulated content
            "chunk": "Word 7 ",
            "timestamp": int(time.time() * 1000),
            "is_complete": False
        }
        
        channel = f"chat:stream:{SESSION_ID}"
        
        print(f"📤 Publishing chunk 7 to channel: {channel}")
        subscribers = self.redis_client.publish(channel, json.dumps(chunk7_message))
        
        print(f"⚠️  Subscribers listening: {subscribers}")
        if subscribers == 0:
            print("🚨 WARNING: No subscribers! Chunk 7 will be LOST!")
        else:
            print(f"✅ {subscribers} subscriber(s) received the message")
            
        self.chunk7_published = True
        print()
        
    def simulate_save_to_history(self):
        """T3: Python AI saves chunk 7 to history"""
        print("=" * 80)
        print("⏰ T3: Python AI saves chunk 7 to chat:history")
        print("=" * 80)
        
        chunk7_message = {
            "message_id": MESSAGE_ID,
            "session_id": SESSION_ID,
            "user_id": "test_user",
            "role": "assistant",
            "content": "Word " * 7,
            "chunk": "Word 7 ",
            "timestamp": int(time.time() * 1000),
            "is_complete": False
        }
        
        key = f"chat:history:{SESSION_ID}"
        self.redis_client.rpush(key, json.dumps(chunk7_message))
        
        print(f"💾 Chunk 7 saved to {key}")
        history_count = self.redis_client.llen(key)
        print(f"✅ History now contains {history_count} chunks (1-7)")
        print()
        
    def pubsub_listener(self):
        """Background thread to listen to PubSub"""
        channel = f"chat:stream:{SESSION_ID}"
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(channel)
        
        print(f"👂 PubSub listener thread started for channel: {channel}")
        
        for message in self.pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                chunk_num = len(data['content'].split())
                self.received_chunks.append(chunk_num)
                print(f"   📨 Received via PubSub: Chunk {chunk_num}")
                
    def simulate_subscribe_pubsub(self):
        """T4: Java Node subscribes to PubSub channel"""
        print("=" * 80)
        print("⏰ T4: Java Node 2 subscribes to PubSub channel")
        print("=" * 80)
        
        # Start PubSub listener in background thread
        listener_thread = threading.Thread(target=self.pubsub_listener, daemon=True)
        listener_thread.start()
        
        # Give it time to subscribe
        time.sleep(0.2)
        
        print(f"✅ Node 2 is now listening to PubSub")
        print(f"⚠️  But it's too late! Chunk 7 was already published and missed!")
        self.pubsub_started = True
        print()
        
    def publish_remaining_chunks(self):
        """Publish chunks 8-10 to verify subscription is working"""
        print("=" * 80)
        print("⏰ T5: Python AI continues streaming (chunks 8-10)")
        print("=" * 80)
        
        for i in range(8, 11):
            chunk_message = {
                "message_id": MESSAGE_ID,
                "session_id": SESSION_ID,
                "user_id": "test_user",
                "role": "assistant",
                "content": "Word " * i,
                "chunk": f"Word {i} ",
                "timestamp": int(time.time() * 1000),
                "is_complete": i == 10
            }
            
            channel = f"chat:stream:{SESSION_ID}"
            self.redis_client.publish(channel, json.dumps(chunk_message))
            print(f"📤 Published chunk {i}")
            time.sleep(0.1)
            
        print()
        
        # Wait for PubSub to receive messages
        time.sleep(0.3)
        
    def verify_bug(self, initial_history: List[dict]):
        """Verify that the bug occurred - chunk 7 was missed"""
        print("=" * 80)
        print("🔍 VERIFICATION: Checking for Data Loss")
        print("=" * 80)
        
        print("\n📊 What the client received:")
        print(f"   1. From initial history (T1): Chunks 1-{len(initial_history)}")
        print(f"   2. From PubSub (T4+): Chunks {self.received_chunks}")
        
        print("\n📋 Expected chunks: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10")
        
        all_chunks_received = list(range(1, len(initial_history) + 1)) + self.received_chunks
        print(f"📋 Actual chunks received: {all_chunks_received}")
        
        missing_chunks = []
        for i in range(1, 11):
            if i not in all_chunks_received:
                missing_chunks.append(i)
                
        print("\n" + "=" * 80)
        if missing_chunks:
            print("🚨 BUG CONFIRMED! DATA LOSS DETECTED!")
            print("=" * 80)
            print(f"❌ Missing chunks: {missing_chunks}")
            print()
            print("📝 Explanation:")
            print("   - Chunk 7 was published AFTER reading history (T1)")
            print("   - But BEFORE subscribing to PubSub (T4)")
            print("   - This is the 'risk window' where messages are lost!")
            print()
            print("💡 Root Cause:")
            print("   In ChatWebSocketHandler.afterConnectionEstablished():")
            print("   - Line 100: sendChatHistory() - reads history")
            print("   - Line 104: startStreamingSession() - subscribes to PubSub")
            print("   - The gap between these two lines is the risk window!")
            return False
        else:
            print("✅ NO BUG - All chunks received correctly")
            print("=" * 80)
            return True
            
    def run(self):
        """Run the complete test scenario"""
        print("\n" + "=" * 80)
        print("🧪 CHUNK 7 DATA LOSS - RACE CONDITION TEST")
        print("=" * 80)
        print()
        
        try:
            # Cleanup
            self.cleanup()
            
            # Setup
            self.setup_initial_history()
            
            # T1: Read history (gets chunks 1-6)
            initial_history = self.simulate_read_history()
            
            # T2: Publish chunk 7 (BEFORE subscription - RISK WINDOW!)
            self.simulate_risk_window_publish()
            
            # T3: Save chunk 7 to history
            self.simulate_save_to_history()
            
            # T4: Subscribe to PubSub (TOO LATE!)
            self.simulate_subscribe_pubsub()
            
            # T5: Continue publishing chunks 8-10
            self.publish_remaining_chunks()
            
            # Verify the bug
            success = self.verify_bug(initial_history)
            
            return success
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if self.pubsub:
                self.pubsub.close()
            print("\n🏁 Test complete\n")


if __name__ == "__main__":
    test = RaceConditionTest()
    success = test.run()
    sys.exit(0 if not success else 1)  # Exit 0 if bug found (expected), 1 if no bug
