package com.demo.websocket.service;

import io.micrometer.core.instrument.Tags;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Simple Metrics Service for PoC
 * 
 * Chỉ log metrics thay vì Prometheus - đủ cho PoC
 * 
 * Features:
 * - Log-based metrics (no external dependencies)
 * - Counter, Timer, Gauge, Distribution tracking
 * - In-memory counters for debugging
 */
@Service
@Slf4j
public class MetricsService {

    private final ConcurrentHashMap<String, AtomicLong> counters = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, AtomicInteger> gauges = new ConcurrentHashMap<>();

    public MetricsService() {
        log.info("✅ MetricsService initialized (Log-only mode for PoC)");
    }

    // ===== Counter Metrics (Log only) =====

    public void incrementCounter(String name) {
        long count = counters.computeIfAbsent(name, k -> new AtomicLong(0)).incrementAndGet();
        log.debug("[METRIC] Counter: {} = {}", name, count);
    }

    public void incrementCounter(String name, Tags tags) {
        incrementCounter(name); // Ignore tags for PoC
    }

    public void incrementCounter(String name, String... tags) {
        incrementCounter(name); // Ignore tags for PoC
    }

    // ===== Timer Metrics (Log only) =====

    public TimerSample startTimer() {
        return new TimerSample();
    }

    public void stopTimer(TimerSample sample, String name) {
        Duration duration = sample.stop();
        log.debug("[METRIC] Timer: {} = {}ms", name, duration.toMillis());
    }

    public void stopTimer(TimerSample sample, String name, Tags tags) {
        stopTimer(sample, name); // Ignore tags for PoC
    }

    public void recordTimer(String name, Duration duration) {
        log.debug("[METRIC] Timer: {} = {}ms", name, duration.toMillis());
    }

    public void recordTimer(String name, Duration duration, Tags tags) {
        recordTimer(name, duration); // Ignore tags for PoC
    }

    // ===== Distribution Summary (Log only) =====

    public void recordDistribution(String name, long value) {
        log.debug("[METRIC] Distribution: {} = {}", name, value);
    }

    public void recordDistribution(String name, long value, Tags tags) {
        recordDistribution(name, value); // Ignore tags for PoC
    }

    // ===== Gauge Metrics (Log only) =====

    public void setGaugeValue(String name, int value) {
        gauges.put(name, new AtomicInteger(value));
        log.debug("[METRIC] Gauge: {} = {}", name, value);
    }

    public void incrementGauge(String name) {
        int value = gauges.computeIfAbsent(name, k -> new AtomicInteger(0)).incrementAndGet();
        log.debug("[METRIC] Gauge: {} = {}", name, value);
    }

    public void decrementGauge(String name) {
        int value = gauges.computeIfAbsent(name, k -> new AtomicInteger(0)).decrementAndGet();
        log.debug("[METRIC] Gauge: {} = {}", name, value);
    }
    
    // ===== Business Metrics =====

    public void recordWebSocketConnection(String userId, boolean success) {
        incrementCounter("websocket.connections");
        log.info("📥 WebSocket connection: userId={}, success={}", userId, success);
        
        if (success) {
            incrementGauge("active_connections");
        }
    }

    public void recordWebSocketDisconnection(String userId) {
        incrementCounter("websocket.disconnections");
        decrementGauge("active_connections");
        log.info("📤 WebSocket disconnection: userId={}", userId);
    }

    public void recordMessageReceived(String messageType) {
        incrementCounter("websocket.messages.received");
        log.debug("📨 Message received: type={}", messageType);
    }

    public void recordMessageSent(String messageType) {
        incrementCounter("websocket.messages.sent");
        log.debug("📤 Message sent: type={}", messageType);
    }

    public void recordStreamStarted(String sessionId) {
        incrementCounter("stream.started");
        incrementGauge("active_sessions");
        log.info("🎬 Stream started: sessionId={}", sessionId);
    }

    public void recordStreamCompleted(String sessionId, Duration duration, int chunkCount) {
        incrementCounter("stream.completed");
        decrementGauge("active_sessions");
        
        recordTimer("stream.duration", duration);
        recordDistribution("stream.chunks", chunkCount);
        
        log.info("✅ Stream completed: sessionId={}, duration={}ms, chunks={}", 
                 sessionId, duration.toMillis(), chunkCount);
    }

    public void recordStreamError(String sessionId, String errorType) {
        incrementCounter("stream.errors");
        decrementGauge("active_sessions");
        log.error("❌ Stream error: sessionId={}, errorType={}", sessionId, errorType);
    }

    public void recordCacheHit(String cacheLevel) {
        incrementCounter("cache.hits");
        log.debug("💾 Cache hit: level={}", cacheLevel);
    }

    public void recordCacheMiss(String cacheLevel) {
        incrementCounter("cache.misses");
        log.debug("💥 Cache miss: level={}", cacheLevel);
    }

    public void recordRecoveryAttempt(boolean success) {
        incrementCounter("recovery.attempts");
        log.info("🔄 Recovery attempt: success={}", success);
    }

    public void recordAuthenticationAttempt(boolean success) {
        incrementCounter("authentication.attempts");
        log.info("🔐 Auth attempt: success={}", success);
    }

    public void recordError(String errorType, String component) {
        incrementCounter("errors");
        log.error("⚠️ Error: type={}, component={}", errorType, component);
    }

    // ===== Performance Metrics =====

    public void recordLatency(String operation, Duration latency) {
        recordTimer(operation + ".latency", latency);
    }

    public void recordThroughput(String operation, long count) {
        recordDistribution(operation + ".throughput", count);
    }
    
    // ===== Utility Methods =====
    
    /**
     * Get current counter value (for debugging)
     */
    public long getCounterValue(String name) {
        AtomicLong counter = counters.get(name);
        return counter != null ? counter.get() : 0;
    }
    
    /**
     * Get current gauge value (for debugging)
     */
    public int getGaugeValue(String name) {
        AtomicInteger gauge = gauges.get(name);
        return gauge != null ? gauge.get() : 0;
    }
    
    /**
     * Print summary of all metrics (for debugging)
     */
    public void printSummary() {
        log.info("=== Metrics Summary ===");
        log.info("Counters:");
        counters.forEach((name, value) -> log.info("  {} = {}", name, value.get()));
        log.info("Gauges:");
        gauges.forEach((name, value) -> log.info("  {} = {}", name, value.get()));
        log.info("=====================");
    }
    
    // Simple Timer implementation
    public static class TimerSample {
        private final long startTime = System.currentTimeMillis();
        
        public Duration stop() {
            return Duration.ofMillis(System.currentTimeMillis() - startTime);
        }
    }
}
