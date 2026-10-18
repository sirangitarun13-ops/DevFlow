"""Rate limiting configuration and utilities."""

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import Response


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window",
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom handler for rate limit exceeded errors with Retry-After header."""
    response = _rate_limit_exceeded_handler(request, exc)
    # Add Retry-After header based on the limit's window size
    # The limit's get_expiry() returns the window size in seconds
    if hasattr(exc, "limit") and exc.limit and hasattr(exc.limit, "limit"):
        window_seconds = exc.limit.limit.get_expiry()
        if window_seconds and "Retry-After" not in response.headers:
            response.headers["Retry-After"] = str(int(window_seconds))
    return response


def get_limiter() -> Limiter:
    """Get the rate limiter instance."""
    return limiter