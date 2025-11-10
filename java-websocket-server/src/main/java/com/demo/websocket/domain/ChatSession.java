package com.demo.websocket.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.io.Serializable;
import java.time.Instant;

/**
 * Chat Session Entity - Persisted in Database with Redis cache
 */
@Entity
@Table(name = "chat_sessions", indexes = {
    @Index(name = "idx_conversation_id", columnList = "conversationId"),
    @Index(name = "idx_user_id", columnList = "userId"),
    @Index(name = "idx_last_activity", columnList = "lastActivityTime")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatSession implements Serializable {
    private static final long serialVersionUID = 1L;
    
    @Id
    @Column(length = 100)
    private String sessionId;
    
    @Column(length = 100)
    private String conversationId;
    
    @Column(nullable = false, length = 100)
    private String userId;
    
    @Column(length = 100)
    private String messageId;
    
    @Enumerated(EnumType.STRING)
    @Column(length = 20, nullable = false)
    private SessionStatus status;
    
    @Column(nullable = false)
    private Instant startTime;
    
    @Column(nullable = false)
    private Instant lastActivityTime;
    
    @Column(nullable = false)
    private int totalChunks;
    
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "TEXT")
    private StreamMetadata metadata;

    public enum SessionStatus {
        INITIALIZING,
        STREAMING,
        COMPLETED,
        ERROR,
        TIMEOUT
    }
    
    @PrePersist
    protected void onCreate() {
        if (startTime == null) {
            startTime = Instant.now();
        }
        if (lastActivityTime == null) {
            lastActivityTime = Instant.now();
        }
        if (status == null) {
            status = SessionStatus.INITIALIZING;
        }
    }
    
    @PreUpdate
    protected void onUpdate() {
        lastActivityTime = Instant.now();
    }
}
