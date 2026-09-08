"""In-memory sliding-window rate limiter (HTTP middleware).

Per-client-IP limit backed by a simple deque of request timestamps. This
is a single-process guard for the demo stack (rate limit configured via
`api_rate_limit_per_minute`); production would swap in a shared store
(Redis) but the external behaviour — HTTP 429 with a Retry-After header —
stays identical.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int = 120):
        super().__init__(app)
        self.limit = max(1, int(limit_per_minute))
        self._window = 60.0
        self._hits: defaultdict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        now = time.monotonic()
        key = self._client_key(request)
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - self._window:
                q.popleft()
            if len(q) >= self.limit:
                retry_after = int(self._window - (now - q[0])) + 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": "rate_limit_exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)
        return await call_next(request)