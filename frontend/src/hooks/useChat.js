import { useState, useRef, useCallback } from 'react';

/**
 * Custom hook for managing chat messages and streaming
 */
export const useChat = () => {
  const [messages, setMessages] = useState([]);
  const streamingMessagesRef = useRef(new Map());

  const handleStreamingMessage = useCallback((message) => {
    if (message.role === 'user') {
      // User message - add directly if not exists (DEDUPLICATION)
      setMessages((prev) => {
        const exists = prev.some(m => m.message_id === message.message_id);
        if (!exists) {
          return [...prev, message];
        }
        // Already exists - skip to avoid duplicates
        return prev;
      });
    } else if (message.role === 'assistant') {
      // Assistant message - handle streaming
      if (message.is_complete) {
        // Final complete message
        streamingMessagesRef.current.delete(message.message_id);

        setMessages((prev) => {
          const index = prev.findIndex(m => m.message_id === message.message_id);
          if (index >= 0) {
            // Update existing message with final content
            const updated = [...prev];
            updated[index] = message;
            return updated;
          } else {
            // Add new message
            return [...prev, message];
          }
        });
      } else {
        // Streaming chunk - use accumulated content from server
        // NOTE: The server (Python AI service and ChatOrchestrator) already sends
        // accumulated content in the 'content' field. We should NOT accumulate again
        // on the client side to avoid duplicate/overlapping text.
        setMessages((prev) => {
          const index = prev.findIndex(m => m.message_id === message.message_id);
          if (index >= 0) {
            // Update message with latest accumulated content from server
            const updated = [...prev];
            updated[index] = {
              ...message,
              content: message.content || '',
              chunk: message.chunk || ''
            };
            streamingMessagesRef.current.set(message.message_id, updated[index]);
            return updated;
          } else {
            // Add new streaming message with initial content
            const newMessage = {
              ...message,
              content: message.content || '',
              chunk: message.chunk || ''
            };
            streamingMessagesRef.current.set(message.message_id, newMessage);
            return [...prev, newMessage];
          }
        });
      }
    }
  }, []);

  const loadHistory = useCallback((historyMessages) => {
    // DEDUPLICATION STRATEGY (for Subscribe-First Pattern):
    // After we subscribe to PubSub, we read history. This means:
    // 1. We might receive chunks via PubSub BEFORE history loads
    // 2. History might contain chunks we already received via PubSub
    // 3. We MUST deduplicate based on message_id to avoid showing duplicates
    //
    // This function merges history with existing messages intelligently:
    // - Keeps all existing messages (already received via PubSub)
    // - Adds history messages that don't exist yet (message_id not in existing)
    // - Sorts by timestamp to maintain chronological order
    
    setMessages((prev) => {
      if (prev.length === 0) {
        // No existing messages, just load history
        return historyMessages;
      }
      
      // DEDUPLICATION: Filter out history messages that already exist
      const existingIds = new Set(prev.map(m => m.message_id));
      const newMessages = historyMessages.filter(m => !existingIds.has(m.message_id));
      
      console.log(`[Dedup] History: ${historyMessages.length}, Existing: ${prev.length}, New: ${newMessages.length}, Duplicates: ${historyMessages.length - newMessages.length}`);
      
      // Combine and sort by timestamp
      const combined = [...prev, ...newMessages].sort((a, b) => 
        (a.timestamp || 0) - (b.timestamp || 0)
      );
      
      return combined;
    });
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    streamingMessagesRef.current.clear();
  }, []);

  const addUserMessage = useCallback((messageId, content, sessionId, userId) => {
    const userMessage = {
      message_id: messageId,
      session_id: sessionId,
      user_id: userId,
      role: 'user',
      content: content,
      timestamp: Date.now(),
      is_complete: true
    };
    
    setMessages((prev) => [...prev, userMessage]);
  }, []);

  return {
    messages,
    handleStreamingMessage,
    loadHistory,
    clearMessages,
    addUserMessage
  };
};
