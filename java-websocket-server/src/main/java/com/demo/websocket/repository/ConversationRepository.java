package com.demo.websocket.repository;

import com.demo.websocket.domain.ConversationEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Repository for Conversation entities
 */
@Repository
public interface ConversationRepository extends JpaRepository<ConversationEntity, String> {

    /**
     * Find conversation by ID
     */
    Optional<ConversationEntity> findByConversationId(String conversationId);

    /**
     * Find conversations by user ID
     */
    @Query("SELECT c FROM ConversationEntity c " +
           "WHERE c.userId = :userId " +
           "AND c.status = 'ACTIVE' " +
           "ORDER BY c.updatedAt DESC")
    List<ConversationEntity> findByUserId(@Param("userId") String userId);

    /**
     * Find recent conversations
     */
    @Query("SELECT c FROM ConversationEntity c " +
           "WHERE c.userId = :userId " +
           "AND c.status = 'ACTIVE' " +
           "AND c.updatedAt > :since " +
           "ORDER BY c.updatedAt DESC")
    List<ConversationEntity> findRecentByUserId(
        @Param("userId") String userId,
        @Param("since") Instant since
    );
    
    /**
     * Count active conversations for user
     */
    @Query("SELECT COUNT(c) FROM ConversationEntity c " +
           "WHERE c.userId = :userId " +
           "AND c.status = 'ACTIVE'")
    long countActiveByUserId(@Param("userId") String userId);
}
