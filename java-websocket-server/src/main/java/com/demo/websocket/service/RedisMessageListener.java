package com.demo.websocket.service;

import com.demo.websocket.handler.ChatWebSocketHandler;
import com.demo.websocket.model.ChatMessage;
import com.demo.websocket.domain.PubSubMessage;
import com.demo.websocket.domain.StreamChunk;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Lazy;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Service
public class RedisMessageListener implements MessageListener {

    private final ObjectMapper objectMapper;
    private final RedisMessageListenerContainer listenerContainer;
    private final Map<String, ChannelTopic> subscriptions = new ConcurrentHashMap<>();

    private ChatWebSocketHandler webSocketHandler;

    public RedisMessageListener(ObjectMapper objectMapper,
                                @Lazy RedisMessageListenerContainer listenerContainer) {
        this.objectMapper = objectMapper;
        this.listenerContainer = listenerContainer;
    }

    public void setWebSocketHandler(ChatWebSocketHandler handler) {
        this.webSocketHandler = handler;
    }

    /**
     * Subscribe to Redis PubSub channel for a specific session
     */
    public void subscribe(String sessionId, ChatWebSocketHandler handler) {
        if (webSocketHandler == null) {
            webSocketHandler = handler;
        }

        String chunkChannelName = "stream:channel:" + sessionId + ":chunk";
        String completeChannelName = "stream:channel:" + sessionId + ":complete";
        String errorChannelName = "stream:channel:" + sessionId + ":error";

        if (!subscriptions.containsKey(sessionId)) {
            ChannelTopic chunkTopic = new ChannelTopic(chunkChannelName);
            ChannelTopic completeTopic = new ChannelTopic(completeChannelName);
            ChannelTopic errorTopic = new ChannelTopic(errorChannelName);

            subscriptions.put(sessionId, chunkTopic);
            // Store only one topic key but subscribe three topics
            listenerContainer.addMessageListener(this, chunkTopic);
            listenerContainer.addMessageListener(this, completeTopic);
            listenerContainer.addMessageListener(this, errorTopic);
            log.info("Subscribed to Redis fan-out channels for session: {}", sessionId);
        }
    }

    /**
     * Unsubscribe from Redis PubSub channel for a specific session
     */
    public void unsubscribe(String sessionId) {
        ChannelTopic topic = subscriptions.remove(sessionId);
        if (topic != null) {
            listenerContainer.removeMessageListener(this, topic);
            log.info("Unsubscribed from Redis channel: {}", topic.getTopic());
        }
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        try {
            String channel = new String(message.getChannel());
            String body = new String(message.getBody());

            log.info("RedisMessageListener received message from channel {}: {}", 
                    channel, body.substring(0, Math.min(100, body.length())));

            PubSubMessage pubSub = objectMapper.readValue(body, PubSubMessage.class);

            switch (pubSub.getType()) {
                case CHUNK -> {
                    StreamChunk chunk = objectMapper.convertValue(pubSub.getData(), StreamChunk.class);
                    ChatMessage chunkMsg = ChatMessage.builder()
                            .messageId(chunk.getMessageId())
                            .sessionId(pubSub.getSessionId())
                            .userId("ai")
                            .role("assistant")
                            .content(chunk.getContent())
                            .chunk(chunk.getContent())
                            .timestamp(chunk.getTimestamp().toEpochMilli())
                            .isComplete(false)
                            .build();
                    if (webSocketHandler != null) {
                        webSocketHandler.broadcastToSession(pubSub.getSessionId(), chunkMsg);
                    }
                }
                case COMPLETE -> {
                    com.demo.websocket.domain.Message complete = objectMapper.convertValue(pubSub.getData(), com.demo.websocket.domain.Message.class);
                    ChatMessage completeMsg = ChatMessage.builder()
                            .messageId(complete.getId())
                            .sessionId(pubSub.getSessionId())
                            .userId(complete.getUserId())
                            .role("assistant")
                            .content(complete.getContent())
                            .timestamp(complete.getCreatedAt().toEpochMilli())
                            .isComplete(true)
                            .build();
                    if (webSocketHandler != null) {
                        webSocketHandler.broadcastToSession(pubSub.getSessionId(), completeMsg);
                    }
                }
                case ERROR -> {
                    if (webSocketHandler != null) {
                        webSocketHandler.broadcastErrorToSession(pubSub.getSessionId(), pubSub.getError());
                    }
                }
            }

        } catch (Exception e) {
            log.error("Error processing Redis message: {}", e.getMessage(), e);
        }
    }
}
