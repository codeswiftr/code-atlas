"""Middleware for Code Atlas API."""

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..logging_config import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    For production, consider using Redis-backed rate limiting
    with libraries like slowapi or fastapi-limiter.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 100,
        admin_requests_per_minute: int = 1000,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.admin_requests_per_minute = admin_requests_per_minute
        # In-memory storage: {client_key: [(timestamp, count)]}
        self._requests: dict[str, list[datetime]] = {}

    def _get_client_key(self, request: Request) -> str:
        """Get unique identifier for the client."""
        # Use API key if present, otherwise use IP
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"key:{api_key[:16]}"

        # Use forwarded IP if behind proxy, otherwise direct IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    def _is_admin(self, request: Request) -> bool:
        """Check if request is from admin."""
        # This is a simple check - in production, validate against stored keys
        api_key = request.headers.get("X-API-Key", "")
        return api_key.startswith("admin-") or "admin" in api_key.lower()

    def _cleanup_old_requests(self, client_key: str, now: datetime) -> None:
        """Remove requests older than 1 minute."""
        if client_key in self._requests:
            cutoff = now.timestamp() - 60  # 1 minute ago
            self._requests[client_key] = [
                ts for ts in self._requests[client_key]
                if ts.timestamp() > cutoff
            ]

    def _check_rate_limit(self, request: Request) -> tuple[bool, int]:
        """Check if request is within rate limit.

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        client_key = self._get_client_key(request)
        now = datetime.now(tz=UTC)

        # Cleanup old requests
        self._cleanup_old_requests(client_key, now)

        # Determine limit based on client type
        limit = (
            self.admin_requests_per_minute
            if self._is_admin(request)
            else self.requests_per_minute
        )

        # Get current request count
        if client_key not in self._requests:
            self._requests[client_key] = []

        current_count = len(self._requests[client_key])

        if current_count >= limit:
            return False, 0

        # Record this request
        self._requests[client_key].append(now)

        return True, limit - current_count - 1

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in ("/health", "/metrics", "/status", "/"):
            return await call_next(request)

        is_allowed, remaining = self._check_rate_limit(request)

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                client=self._get_client_key(request),
                path=request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(
            self.admin_requests_per_minute
            if self._is_admin(request)
            else self.requests_per_minute
        )
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details."""
        start_time = datetime.now(tz=UTC)

        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get("X-API-Key", "")
        masked_key = f"{api_key[:8]}..." if api_key else "none"

        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            api_key=masked_key,
        )

        try:
            response = await call_next(request)

            duration = (datetime.now(tz=UTC) - start_time).total_seconds()

            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_seconds=round(duration, 3),
            )

            return response

        except Exception as exc:
            duration = (datetime.now(tz=UTC) - start_time).total_seconds()

            logger.error(
                "Request failed",
                method=request.method,
                path=request.url.path,
                error=str(exc),
                duration_seconds=round(duration, 3),
            )
            raise
