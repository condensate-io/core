import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

EXEMPT_PATHS = frozenset({"/healthz", "/health", "/metrics"})
EXEMPT_PREFIX = "/assets"


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return path.startswith(EXEMPT_PREFIX)


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client_key: str, now: float | None = None) -> Tuple[bool, int]:
        current = time.monotonic() if now is None else now
        window_start = current - self.window_seconds

        with self._lock:
            timestamps = self._windows[client_key]
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                retry_after = max(
                    1, int(timestamps[0] + self.window_seconds - current) + 1
                )
                return False, retry_after

            timestamps.append(current)
            return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool = True,
        max_requests: int = 120,
        window_seconds: float = 60,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self._limiter = SlidingWindowRateLimiter(max_requests, window_seconds)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled or _is_exempt(request.url.path):
            return await call_next(request)

        allowed, retry_after = self._limiter.check(_client_ip(request))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
