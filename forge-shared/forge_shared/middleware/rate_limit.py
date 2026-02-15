"""
Rate limiting middleware using Redis.

Provides token bucket rate limiting for API endpoints with configurable
limits and sliding window counters.

Example:
    ```python
    from fastapi import FastAPI
    from forge_shared.middleware import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        redis_url="redis://localhost:6379",
        requests_per_minute=60
    )
    ```
"""

from typing import Optional
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis
import time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis.

    Implements token bucket algorithm with sliding window counters.

    Attributes:
        app: ASGI application
        redis_url: Redis connection URL
        requests_per_minute: Maximum requests per minute
        burst_size: Burst capacity for token bucket
        key_prefix: Redis key prefix for rate limit counters

    Example:
        ```python
        app.add_middleware(
            RateLimitMiddleware,
            redis_url="redis://localhost:6379",
            requests_per_minute=60
        )
        ```
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_url: Optional[str] = None,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        key_prefix: str = "rate_limit",
    ) -> None:
        """
        Initialize rate limiting middleware.

        Args:
            app: ASGI application
            redis_url: Redis connection URL (None to disable Redis-based rate limiting)
            requests_per_minute: Maximum requests per minute
            burst_size: Burst capacity
            key_prefix: Redis key prefix
        """
        super().__init__(app)
        self.redis_url = redis_url  # None disables Redis-based rate limiting
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.key_prefix = key_prefix
        self._redis: Optional[redis.Redis] = None

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware or route handler

        Returns:
            Response or 429 Too Many Requests
        """
        # Get client identifier (IP address or user ID)
        identifier = self._get_identifier(request)

        # Check rate limit
        allowed, retry_after = await self._check_rate_limit(identifier)

        if not allowed:
            return Response(
                content="Too many requests",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    "Retry-After": str(int(retry_after)),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(self.requests_per_minute - 1)

        return response

    def _get_identifier(self, request: Request) -> str:
        """
        Get client identifier for rate limiting.

        Args:
            request: Request object

        Returns:
            Client identifier (user ID or IP address)
        """
        # Use user ID if authenticated
        user = getattr(request.state, "user", None)
        if user:
            return f"user:{user.id}"

        # Fall back to IP address
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    async def _check_rate_limit(self, identifier: str) -> tuple[bool, float]:
        """
        Check if request is within rate limit.

        Args:
            identifier: Client identifier

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        # Skip Redis-based rate limiting if no Redis URL configured
        if not self.redis_url:
            return True, 0

        if self._redis is None:
            self._redis = await redis.from_url(self.redis_url, decode_responses=True)

        key = f"{self.key_prefix}:{identifier}"
        current_time = int(time.time())
        window_start = current_time - 60  # 1 minute sliding window

        try:
            # Clean old entries
            await self._redis.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            count = await self._redis.zcard(key)

            if count >= self.requests_per_minute:
                # Rate limit exceeded
                oldest = await self._redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    retry_after = oldest[0][1] + 60 - current_time
                    return False, max(0, retry_after)

            # Add current request
            await self._redis.zadd(key, {str(current_time): current_time})
            await self._redis.expire(key, 60)

            return True, 0

        except Exception:
            # Fail open - allow request if Redis is unavailable
            return True, 0


async def close_redis() -> None:
    """
    Close Redis connection pool.

    Should be called on application shutdown.
    """
    # This would be implemented with proper connection pool management
    pass
