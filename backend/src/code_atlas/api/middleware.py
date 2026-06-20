"""Middleware for Code Atlas API."""

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..logging_config import get_logger
from ..schemas.auth import TIER_RATE_LIMITS, APITier
from ..schemas.usage import UsageEventType

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tier-based hourly rate limiting middleware.

    Rate limits are per-hour and based on subscription tier:
    - Free: 10 requests/hour
    - Pro: 100 requests/hour
    - Team: 1000 requests/hour
    - Admin (key contains 'admin'): 10000 requests/hour

    Also records usage events for billing when usage_tracker is provided.
    """

    # Window size in seconds (1 hour)
    WINDOW_SECONDS = 3600

    def __init__(
        self,
        app,
        key_manager=None,
        usage_tracker=None,
    ):
        super().__init__(app)
        self._key_manager = key_manager
        self._usage_tracker = usage_tracker
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
        api_key = request.headers.get("X-API-Key", "")
        return api_key.startswith("admin-") or "admin" in api_key.lower()

    def _get_tier(self, request: Request) -> APITier:
        """Get tier for the request."""
        if self._is_admin(request):
            # Admin gets team-level limits
            return APITier.TEAM

        # For now, default to free tier
        # In production, look up tier from key_manager
        return APITier.FREE

    def _get_limit(self, request: Request) -> int:
        """Get rate limit based on tier."""
        if self._is_admin(request):
            return 10000  # Admin gets very high limit

        tier = self._get_tier(request)
        return TIER_RATE_LIMITS.get(tier, 10)

    def _cleanup_old_requests(self, client_key: str, now: datetime) -> None:
        """Remove requests older than window size."""
        if client_key in self._requests:
            cutoff = now.timestamp() - self.WINDOW_SECONDS
            self._requests[client_key] = [
                ts for ts in self._requests[client_key] if ts.timestamp() > cutoff
            ]

    def _check_rate_limit(self, request: Request) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Returns:
            Tuple of (is_allowed, remaining_requests, limit)
        """
        client_key = self._get_client_key(request)
        now = datetime.now(tz=UTC)

        # Cleanup old requests
        self._cleanup_old_requests(client_key, now)

        # Determine limit based on tier
        limit = self._get_limit(request)

        # Get current request count
        if client_key not in self._requests:
            self._requests[client_key] = []

        current_count = len(self._requests[client_key])

        if current_count >= limit:
            return False, 0, limit

        # Record this request
        self._requests[client_key].append(now)

        return True, limit - current_count - 1, limit

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in ("/health", "/metrics", "/status", "/"):
            return await call_next(request)

        is_allowed, remaining, limit = self._check_rate_limit(request)

        if not is_allowed:
            logger.warning(
                "Rate limit exceeded",
                client=self._get_client_key(request),
                path=request.url.path,
                limit=limit,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(self.WINDOW_SECONDS),
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        # Record usage event for billing (if tracker available)
        if self._usage_tracker and response.status_code < 400:
            try:
                key_id = self._get_client_key(request)
                # Determine event type based on endpoint
                event_type = UsageEventType.API_REQUEST
                if "/report" in request.url.path:
                    event_type = UsageEventType.REPORT_GENERATED

                self._usage_tracker.record_event(
                    key_id=key_id,
                    event_type=event_type,
                    endpoint=request.url.path,
                    metadata={"method": request.method, "status": response.status_code},
                )
            except Exception as e:
                logger.warning("Failed to record usage event", error=str(e))

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
