from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore


DEFAULT_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
]


@dataclass
class TokenBucket:
    capacity: int
    refill_rate: float  # tokens per second
    tokens: float
    last_refill: float

    def consume(self, amount: float = 1.0) -> float:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= amount:
            self.tokens -= amount
            return 0.0
        else:
            needed = amount - self.tokens
            wait = needed / self.refill_rate
            self.tokens = 0
            return wait


class HttpClient:
    def __init__(
        self,
        rps_per_domain: float = 2.0,
        cache_ttl: int = 120,
        proxies: Optional[Dict[str, str]] = None,
        user_agents: Optional[list[str]] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ) -> None:
        self.cache_ttl = cache_ttl
        self.proxies = proxies
        self.user_agents = user_agents or DEFAULT_UAS
        self.timeout = timeout
        self.max_retries = max_retries
        self._buckets: Dict[str, TokenBucket] = {}
        self._cache: Dict[Tuple[str, str], Tuple[float, Dict[str, str], bytes]] = {}
        # key -> (expires_at, headers, body)
        self._etags: Dict[Tuple[str, str], str] = {}
        self.rps_per_domain = rps_per_domain

    def _bucket_for(self, url: str) -> TokenBucket:
        host = urlparse(url).netloc
        if host not in self._buckets:
            self._buckets[host] = TokenBucket(
                capacity=max(1, int(self.rps_per_domain)),
                refill_rate=self.rps_per_domain,
                tokens=1.0,
                last_refill=time.time(),
            )
        return self._buckets[host]

    def request(
        self, method: str, url: str, data: Optional[dict] = None, headers: Optional[Dict[str, str]] = None
    ) -> Tuple[int, Dict[str, str], bytes]:
        if requests is None:
            raise RuntimeError("requests library is required to perform HTTP calls")
        method = method.lower()
        hdrs = {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        if headers:
            hdrs.update(headers)
        key = (method, url)
        # Return fresh cache if valid
        if key in self._cache:
            expires, cached_headers, cached_body = self._cache[key]
            if time.time() < expires:
                return 200, cached_headers, cached_body
        # ETag
        if key in self._etags:
            hdrs["If-None-Match"] = self._etags[key]
        # Rate limit
        bucket = self._bucket_for(url)
        wait = bucket.consume(1.0)
        if wait > 0:
            time.sleep(wait)
        # Retry with backoff
        backoff = 0.5
        for attempt in range(self.max_retries):
            try:
                if method == "get":
                    resp = requests.get(url, headers=hdrs, timeout=self.timeout, proxies=self.proxies)
                elif method == "post":
                    resp = requests.post(url, headers=hdrs, data=data or {}, timeout=self.timeout, proxies=self.proxies)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                status = resp.status_code
                # 304 - use cache
                if status == 304 and key in self._cache:
                    expires, cached_headers, body = self._cache[key]
                    return 200, cached_headers, body
                body = resp.content
                etag = resp.headers.get("ETag")
                if etag:
                    self._etags[key] = etag
                if status == 200 and self.cache_ttl > 0:
                    self._cache[key] = (time.time() + self.cache_ttl, dict(resp.headers), body)
                return status, dict(resp.headers), body
            except Exception:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(backoff)
                backoff *= 2
        raise RuntimeError("Unreachable")
