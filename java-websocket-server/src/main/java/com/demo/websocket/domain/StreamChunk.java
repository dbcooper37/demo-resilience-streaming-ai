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
import java.util.Map;

/**
 * Stream Chunk Entity - Persisted in Database with Redis cache
 */
@Entity
@Table(name = "stream_chunks", indexes = {
    @Index(name = "idx_message_id", columnList = "messageId"),
    @Index(name = "idx_message_id_index", columnList = "messageId,chunkIndex")
})
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StreamChunk implements Serializable {
    private static final long serialVersionUID = 1L;
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false, length = 100)
    private String messageId;
    
    @Column(name = "chunkIndex", nullable = false)
    private int index;
    
    @Column(columnDefinition = "TEXT")
    private String content;
    
    @Enumerated(EnumType.STRING)
    @Column(length = 20)
    private ChunkType type;
    
    @Column(nullable = false)
    private Instant timestamp;
    
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "TEXT")
    private Map<String, Object> metadata;

    public enum ChunkType {
        TEXT,
        CODE,
        THINKING,
        TOOL_USE,
        CITATION
    }
}
