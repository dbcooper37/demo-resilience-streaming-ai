package com.demo.websocket.infrastructure;

import com.demo.websocket.domain.ChatSession;
import com.demo.websocket.domain.Message;
import com.demo.websocket.domain.StreamChunk;
import com.demo.websocket.domain.StreamMetadata;
import com.demo.websocket.model.ChatMessage;
import com.demo.websocket.service.EventPublisher;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.stereotype.Service;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.RedisTemplate;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Service
@Slf4j
public class ChatOrchestrator {

    private final RedisStreamCache streamCache;
    private final MessageRepository messageRepository;
    private final RedisPubSubPublisher pubSubPublisher;
    private final RedisMessageListenerContainer listenerContainer;
    private final ObjectMapper objectMapper;
    
    // Optional: Kafka event publisher (null if Kafka is disabled)
    private final EventPublisher eventPublisher;

    @Value("${stream.ownership-ttl-minutes:10}")  // NEW: Configurable TTL for ownership
    private int ownershipTtlMinutes;

    // Track active streaming sessions
    private final Map<String, StreamingContext> activeStreams = new ConcurrentHashMap<>();

    @Autowired
    private RedisTemplate<String, String> redisTemplate;  // Assume injected via constructor

    public ChatOrchestrator(RedisStreamCache streamCache,
                           MessageRepository messageRepository,
                           RedisPubSubPublisher pubSubPublisher,
                           RedisMessageListenerContainer listenerContainer,
                           ObjectMapper objectMapper,
                           @Autowired(required = false) EventPublisher eventPublisher) {
        this.streamCache = streamCache;
        this.messageRepository = messageRepository;
        this.pubSubPublisher = pubSubPublisher;
        this.listenerContainer = listenerContainer;
        this.objectMapper = objectMapper;
        this.eventPublisher = eventPublisher;
        
        log.info("Ownership TTL configured: {} minutes", ownershipTtlMinutes);

        if (eventPublisher != null) {
            log.info("Kafka EventPublisher enabled for event sourcing and analytics");
        } else {
            log.info("Kafka EventPublisher disabled - using Redis PubSub only");
        }
    }

    /**
     * Start listening for streaming chat from AI service
     * This subscribes to the legacy chat:stream channel and converts to new format
     */
    public void startStreamingSession(String sessionId,
                                      String userId,
                                      StreamCallback callback) {

        String messageId = UUID.randomUUID().toString();

        // Create chat session
        ChatSession session = ChatSession.builder()
                .sessionId(sessionId)
                .userId(userId)
                .conversationId(sessionId)
                .status(ChatSession.SessionStatus.INITIALIZING)
                .startTime(Instant.now())
                .totalChunks(0)
                .metadata(StreamMetadata.builder().build())
                .build();

        // NEW: Claim session ownership
        String ownerKey = "session:owner:" + sessionId;
        Boolean claimed = redisTemplate.opsForValue().setIfAbsent(ownerKey, getNodeId(), Duration.ofMinutes(ownershipTtlMinutes));
        
        if (claimed == null || !claimed) {
            log.warn("Failed to claim ownership for session: {}, already owned by another node", sessionId);
            // Optionally: Don't start, or retry/redirect – for PoC, return early
            return;  // Skip: Let another node handle
        }
        
        log.info("Claimed ownership for session: {} by node: {}", sessionId, getNodeId());

        // Initialize stream in cache
        streamCache.initializeStream(session);

        // Create streaming context
        StreamingContext context = new StreamingContext(session, callback);
        activeStreams.put(sessionId, context);

        // Publish session started event to Kafka (if enabled)
        if (eventPublisher != null) {
            eventPublisher.publishSessionStarted(session);
        }

        // NEW: Only subscribe if we own the session
        String legacyChannel = "chat:stream:" + sessionId;
        subscribeToLegacyChannel(legacyChannel, context);

        log.info("Started streaming session: sessionId={}, messageId={}", sessionId, messageId);
    }

    /**
     * Subscribe to legacy chat:stream channel and convert messages
     */
    private void subscribeToLegacyChannel(String channel, StreamingContext context) {
        log.info("=== SUBSCRIBING TO CHANNEL: {} ===", channel);
        log.info("ListenerContainer status - isRunning: {}, isActive: {}",
                listenerContainer.isRunning(), listenerContainer.isActive());

        MessageListener listener = (message, pattern) -> {
            try {
                String body = new String(message.getBody());
                log.info("=== RECEIVED MESSAGE FROM REDIS ===");
                log.info("Channel: {}", channel);
                log.info("Message body (first 200 chars): {}", body.substring(0, Math.min(200, body.length())));
                log.info("Full message length: {}", body.length());

                ChatMessage chatMessage = objectMapper.readValue(body, ChatMessage.class);
                log.info("Parsed ChatMessage: messageId={}, role={}, isComplete={}, contentLength={}",
                        chatMessage.getMessageId(), chatMessage.getRole(),
                        chatMessage.getIsComplete(),
                        chatMessage.getContent() != null ? chatMessage.getContent().length() : 0);

                handleLegacyMessage(chatMessage, context);
                log.info("=== MESSAGE PROCESSED SUCCESSFULLY ===");

            } catch (Exception e) {
                log.error("=== ERROR PROCESSING MESSAGE FROM CHANNEL: {} ===", channel, e);
                context.callback.onError(e);
            }
        };

        ChannelTopic topic = new ChannelTopic(channel);
        listenerContainer.addMessageListener(listener, topic);

        log.info("=== SUBSCRIPTION COMPLETE ===");
        log.info("Channel: {}", channel);
        log.info("Listener added to container");
        // log.info("Active message listeners count: {}", listenerContainer.getMessageListeners().size());
    }

    /**
     * Handle legacy chat message and convert to new streaming format
     */
    private void handleLegacyMessage(ChatMessage chatMessage, StreamingContext context) {
        ChatSession session = context.session;

        // Add this check at the beginning
        if ("user".equals(chatMessage.getRole())) {
            log.info("Ignoring user message in legacy handler: messageId={}, content length={}", 
                     chatMessage.getMessageId(), chatMessage.getContent() != null ? chatMessage.getContent().length() : 0);
            return;
        }

        log.info("=== HANDLING LEGACY MESSAGE ===");
        log.info("SessionId: {}", session.getSessionId());
        log.info("MessageId: {}", session.getMessageId());
        log.info("Role: {}", chatMessage.getRole());
        log.info("IsComplete: {}", chatMessage.getIsComplete());
        log.info("ContentLength: {}", chatMessage.getContent() != null ? chatMessage.getContent().length() : 0);
        log.info("ChunkIndex: {}", context.chunkIndex.get());

        // Update session status
        if (session.getStatus() == ChatSession.SessionStatus.INITIALIZING) {
            log.info("Updating session status from INITIALIZING to STREAMING");
            session.setStatus(ChatSession.SessionStatus.STREAMING);
            streamCache.updateSession(session);
        }

        // Create stream chunk with accumulated content (not just the chunk)
        // Python sends: content = accumulated_content, chunk = current_word
        // We want to use accumulated content for display
        if (!chatMessage.getIsComplete() && (session.getMessageId() == null || session.getMessageId().isEmpty())) {
            session.setMessageId(chatMessage.getMessageId());
            streamCache.updateSession(session);
            log.info("Set new messageId for session: {}", chatMessage.getMessageId());
        }

        StreamChunk chunk = StreamChunk.builder()
                .messageId(chatMessage.getMessageId())  // Changed from session.getMessageId()
                .index(context.chunkIndex.getAndIncrement())
                .content(chatMessage.getContent()) // Use accumulated content, not just the chunk
                .type(StreamChunk.ChunkType.TEXT)
                .timestamp(Instant.now())
                .build();

        log.info("Created StreamChunk: messageId={}, index={}, contentLength={}",
                chunk.getMessageId(), chunk.getIndex(),
                chunk.getContent() != null ? chunk.getContent().length() : 0);

        // Append to cache
        streamCache.appendChunk(chatMessage.getMessageId(), chunk);  // Changed from session.getMessageId()
        log.info("Appended chunk to cache");

        // Publish chunk event to Kafka for analytics (if enabled)
        if (eventPublisher != null) {
            eventPublisher.publishChunkReceived(session.getSessionId(), chunk);
        }

        // Publish to new PubSub format (for multi-node)
        pubSubPublisher.publishChunk(session.getSessionId(), chunk);
        log.info("Published chunk to multi-node PubSub");

        // Callback - this should send to WebSocket
        log.info("=== CALLING WEBSOCKET CALLBACK ===");
        log.info("Callback type: {}", context.callback.getClass().getName());
        context.callback.onChunk(chunk);
        log.info("=== CALLBACK COMPLETED ===");

        // Update session
        session.setLastActivityTime(Instant.now());
        session.setTotalChunks(context.chunkIndex.get());
        streamCache.updateSession(session);

        // Check if complete
        if (chatMessage.getIsComplete() != null && chatMessage.getIsComplete()) {
            log.info("Message is complete, handling completion");
            handleStreamComplete(chatMessage, context);
        }

        log.info("=== LEGACY MESSAGE HANDLING COMPLETE ===");
    }

    /**
     * Handle stream completion
     */
    private void handleStreamComplete(ChatMessage chatMessage, StreamingContext context) {
        ChatSession session = context.session;
        String currentMessageId = chatMessage.getMessageId();

        try {
            Duration latency = Duration.between(session.getStartTime(), Instant.now());

            // Update session
            session.setStatus(ChatSession.SessionStatus.COMPLETED);
            session.setTotalChunks(context.chunkIndex.get());

            // Mark stream as complete in cache
            streamCache.markComplete(currentMessageId, Duration.ofMinutes(5));

            // Save complete message to repository
            Message message = Message.builder()
                    .id(currentMessageId)
                    .conversationId(session.getConversationId())
                    .userId(session.getUserId())
                    .role(Message.MessageRole.ASSISTANT)
                    .content(chatMessage.getContent())
                    .status(Message.MessageStatus.COMPLETED)
                    .createdAt(session.getStartTime())
                    .updatedAt(Instant.now())
                    .metadata(com.demo.websocket.domain.MessageMetadata.builder()
                            .tokenCount(0)
                            .build())
                    .build();

            messageRepository.save(message);

            // Publish complete event to Kafka for event sourcing (if enabled)
            if (eventPublisher != null) {
                eventPublisher.publishStreamCompleted(session.getSessionId(), message, context.chunkIndex.get());
                eventPublisher.publishChatMessage(message);
            }

            // Publish complete event
            pubSubPublisher.publishComplete(session.getSessionId(), message);

            // Callback
            context.callback.onComplete(message);

            // Cleanup
            activeStreams.remove(session.getSessionId());

            // NEW: Release ownership
            String ownerKey = "session:owner:" + session.getSessionId();
            redisTemplate.delete(ownerKey);
            log.info("Released ownership for completed session: {}", session.getSessionId());

            log.info("Stream completed: messageId={}, chunks={}, latency={}ms",
                    currentMessageId,
                    context.chunkIndex.get(),
                    latency.toMillis());

        } catch (Exception e) {
            log.error("Error completing stream", e);
            handleStreamError(session, context.callback, e);
        }
    }

    /**
     * Resubscribe to ongoing stream for reconnection
     */
    public void resubscribeStream(String sessionId,
                                 ChatSession session,
                                 StreamCallback callback) {

        log.info("Resubscribing to stream: sessionId={}, messageId={}",
                sessionId, session.getMessageId());

        // Create new streaming context
        StreamingContext context = new StreamingContext(session, callback);
        context.chunkIndex.set(session.getTotalChunks());
        activeStreams.put(sessionId, context);

        // Subscribe to PubSub for remaining chunks
        pubSubPublisher.subscribe(sessionId, new PubSubListener() {
            @Override
            public void onChunk(StreamChunk chunk) {
                callback.onChunk(chunk);
            }

            @Override
            public void onComplete(Message message) {
                callback.onComplete(message);
                activeStreams.remove(sessionId);
            }

            @Override
            public void onError(String error) {
                callback.onError(new RuntimeException(error));
            }
        });
    }

    /**
     * Handle stream error
     */
    private void handleStreamError(ChatSession session,
                                   StreamCallback callback,
                                   Throwable error) {
        log.error("Stream error: sessionId={}, messageId={}",
                session.getSessionId(), session.getMessageId(), error);

        session.setStatus(ChatSession.SessionStatus.ERROR);
        streamCache.updateSession(session);

        // Publish error event to Kafka for monitoring (if enabled)
        if (eventPublisher != null) {
            eventPublisher.publishStreamError(session.getSessionId(), session.getMessageId(), error.getMessage());
        }

        // Update message status
        messageRepository.findById(session.getMessageId())
                .ifPresent(msg -> {
                    msg.setStatus(Message.MessageStatus.FAILED);
                    messageRepository.save(msg);
                });

        pubSubPublisher.publishError(session.getSessionId(), error.getMessage());
        callback.onError(error);

        // Cleanup
        activeStreams.remove(session.getSessionId());

        // NEW: Release ownership on error
        String ownerKey = "session:owner:" + session.getSessionId();
        redisTemplate.delete(ownerKey);
        log.info("Released ownership for errored session: {}", session.getSessionId());
    }

    /**
     * Streaming context to track session state
     */
    private static class StreamingContext {
        final ChatSession session;
        final StreamCallback callback;
        final AtomicInteger chunkIndex;
        final Instant startTime;

        StreamingContext(ChatSession session, StreamCallback callback) {
            this.session = session;
            this.callback = callback;
            this.chunkIndex = new AtomicInteger(0);
            this.startTime = Instant.now();
        }
    }

    // NEW: Helper to get current node ID (from env or random)
    private String getNodeId() {
        return System.getenv("NODE_ID") != null ? System.getenv("NODE_ID") : UUID.randomUUID().toString().substring(0, 8);
    }
}
