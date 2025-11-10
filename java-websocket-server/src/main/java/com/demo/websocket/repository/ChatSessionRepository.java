package com.demo.websocket.repository;

import com.demo.websocket.domain.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Repository for ChatSession entities
 */
@Repository
public interface ChatSessionRepository extends JpaRepository<ChatSession, String> {

    /**
     * Find session by session ID
     */
    Optional<ChatSession> findBySessionId(String sessionId);

    /**
     * Find sessions by conversation ID
     */
    @Query("SELECT cs FROM ChatSession cs " +
           "WHERE cs.conversationId = :conversationId " +
           "ORDER BY cs.startTime DESC")
    List<ChatSession> findByConversationId(@Param("conversationId") String conversationId);

    /**
     * Find sessions by user ID
     */
    @Query("SELECT cs FROM ChatSession cs " +
           "WHERE cs.userId = :userId " +
           "ORDER BY cs.startTime DESC")
    List<ChatSession> findByUserId(@Param("userId") String userId);

    /**
     * Find active sessions (STREAMING status)
     */
    @Query("SELECT cs FROM ChatSession cs " +
           "WHERE cs.status = 'STREAMING' " +
           "AND cs.lastActivityTime > :threshold " +
           "ORDER BY cs.lastActivityTime DESC")
    List<ChatSession> findActiveSessions(@Param("threshold") Instant threshold);

    /**
     * Find sessions by status
     */
    @Query("SELECT cs FROM ChatSession cs " +
           "WHERE cs.status = :status " +
           "ORDER BY cs.startTime DESC")
    List<ChatSession> findByStatus(@Param("status") ChatSession.SessionStatus status);

    /**
     * Count sessions by user
     */
    @Query("SELECT COUNT(cs) FROM ChatSession cs " +
           "WHERE cs.userId = :userId")
    long countByUserId(@Param("userId") String userId);

    /**
     * Delete old completed sessions
     */
    @Modifying
    @Transactional
    @Query("DELETE FROM ChatSession cs " +
           "WHERE cs.status IN ('COMPLETED', 'ERROR', 'TIMEOUT') " +
           "AND cs.lastActivityTime < :threshold")
    int deleteOldSessions(@Param("threshold") Instant threshold);
}
