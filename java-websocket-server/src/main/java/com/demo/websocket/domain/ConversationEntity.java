package com.demo.websocket.domain;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.Instant;

/**
 * Conversation Entity - Persisted in Database
 */
@Entity
@Table(name = "conversations", indexes = {
    @Index(name = "idx_user_id", columnList = "userId"),
    @Index(name = "idx_user_updated", columnList = "userId,updatedAt")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ConversationEntity implements Serializable {
    private static final long serialVersionUID = 1L;
    
    @Id
    @Column(length = 100)
    private String conversationId;
    
    @Column(nullable = false, length = 100)
    private String userId;
    
    @Column(length = 255)
    private String title;
    
    @Column(nullable = false)
    private Instant createdAt;
    
    @Column(nullable = false)
    private Instant updatedAt;
    
    @Column(nullable = false)
    private int messageCount;
    
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private ConversationStatus status;
    
    public enum ConversationStatus {
        ACTIVE,
        ARCHIVED,
        DELETED
    }
    
    @PrePersist
    protected void onCreate() {
        createdAt = Instant.now();
        updatedAt = Instant.now();
        if (status == null) {
            status = ConversationStatus.ACTIVE;
        }
    }
    
    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }
}
