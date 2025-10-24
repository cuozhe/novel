from __future__ import annotations

import time
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class TokenBucketLimiter(BaseHTTPMiddleware):
    def __init__(self, app, capacity: int = 60, refill_rate: float = 1.0):
        super().__init__(app)
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.buckets: Dict[str, Tuple[float, float]] = {}
        # key -> (tokens, last_ts)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "anonymous"
        tokens, last_ts = self.buckets.get(client_ip, (self.capacity, time.time()))
        now = time.time()
        elapsed = now - last_ts
        tokens = min(self.capacity, tokens + elapsed * self.refill_rate)
        if tokens < 1.0:
            retry_after = int(max(1, (1.0 - tokens) / self.refill_rate))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests", "retry_after": retry_after},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.capacity),
                    "X-RateLimit-Remaining": "0",
                },
            )
        tokens -= 1.0
        self.buckets[client_ip] = (tokens, now)
        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.capacity)
        response.headers["X-RateLimit-Remaining"] = str(int(tokens))
        return response
