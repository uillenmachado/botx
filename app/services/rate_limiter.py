"""
Rate limiter with Redis backend for distributed environments.
Falls back to in-memory for development/testing.
"""
import os
import time
import logging
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """Sliding-window limiter using in-memory deque (single process only)"""
    
    def __init__(self, max_requests: int, window: int):
        self.max_requests = max_requests
        self.window = window
        self.req = deque()

    def can_request(self):
        now = datetime.now()
        
        # Remove expired entries
        while self.req and self.req[0] < now - timedelta(seconds=self.window):
            self.req.popleft()
        
        remaining = self.max_requests - len(self.req)
        
        if remaining > 0:
            self.req.append(now)
            return True, remaining
        
        wait = (self.req[0] + timedelta(seconds=self.window) - now).total_seconds()
        return False, wait


class RedisRateLimiter:
    """Sliding-window limiter using Redis sorted sets (multi-process safe)"""
    
    def __init__(self, max_requests: int, window: int, redis_url: str = None):
        import redis
        
        self.max_requests = max_requests
        self.window = window
        self.key = "twitter_bot:rate_limit"
        
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.from_url(redis_url)

    def can_request(self):
        now = time.time()
        window_start = now - self.window
        
        pipe = self.redis.pipeline()
        
        # Remove expired entries
        pipe.zremrangebyscore(self.key, 0, window_start)
        
        # Count current entries
        pipe.zcard(self.key)
        
        results = pipe.execute()
        current_count = results[1]
        
        remaining = self.max_requests - current_count
        
        if remaining > 0:
            # Add new request timestamp
            self.redis.zadd(self.key, {str(now): now})
            self.redis.expire(self.key, self.window + 60)
            return True, remaining
        
        # Get oldest entry to calculate wait time
        oldest = self.redis.zrange(self.key, 0, 0, withscores=True)
        if oldest:
            oldest_time = oldest[0][1]
            wait = (oldest_time + self.window) - now
            return False, max(0, wait)
        
        return False, self.window


class RateLimiter:
    """
    Rate limiter factory that uses Redis in production and falls back to
    in-memory for development or when Redis is unavailable.
    """
    
    def __init__(self, max_requests: int, window: int):
        self.max_requests = max_requests
        self.window = window
        self._limiter = None
        self._init_limiter()

    def _init_limiter(self):
        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            try:
                self._limiter = RedisRateLimiter(
                    self.max_requests,
                    self.window,
                    redis_url
                )
                # Test connection
                self._limiter.redis.ping()
                logger.info("Using Redis rate limiter")
                return
            except Exception as e:
                logger.warning("Redis unavailable, falling back to in-memory: %s", e)
        
        self._limiter = InMemoryRateLimiter(self.max_requests, self.window)
        logger.info("Using in-memory rate limiter (single-process only)")

    def can_request(self):
        return self._limiter.can_request()
