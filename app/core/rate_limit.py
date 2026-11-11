"""
rate_limit.py – Distributed Redis & In-Memory Rate Limiting Dependency for FastAPI.

Provides tiered rate limiting to protect resource-heavy endpoints (blockchain BFS traversal,
Gemini NLP complaint parsing) against Denial of Service (DoS) and API quota exhaustion.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, status

from app.core.database import init_redis

log = logging.getLogger(__name__)

# Fallback in-memory store if Redis is unavailable: {key: [timestamps]}
_IN_MEMORY_BUCKET: dict[str, list[float]] = defaultdict(list)


class RateLimiter:
    """
    FastAPI dependency for endpoint-level rate limiting.

    Uses Redis sliding-window counter when connected, falling back gracefully
    to an in-memory sliding window.
    """

    def __init__(self, times: int = 20, seconds: int = 60, scope: str = "default") -> None:
        self.times = times
        self.seconds = seconds
        self.scope = scope

    async def __call__(self, request: Request) -> None:
        # Determine client identifier: X-Forwarded-For -> remote host -> fallback
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        key = f"rl:{self.scope}:{client_ip}"
        now = time.time()

        # 1. Try Redis first
        try:
            redis = await init_redis()
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, self.seconds)
            elif current > self.times:
                ttl = await redis.ttl(key)
                log.warning("Rate limit exceeded for %s on %s (current=%d, max=%d)", client_ip, request.url.path, current, self.times)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {max(ttl, 1)} seconds.",
                    headers={"Retry-After": str(max(ttl, 1))},
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            log.debug("Redis rate-limiter unavailable (%s), falling back to in-memory bucket", exc)

        # 2. In-memory sliding window fallback
        timestamps = _IN_MEMORY_BUCKET[key]
        cutoff = now - self.seconds
        _IN_MEMORY_BUCKET[key] = [t for t in timestamps if t > cutoff]

        if len(_IN_MEMORY_BUCKET[key]) >= self.times:
            retry_after = int(self.seconds - (now - _IN_MEMORY_BUCKET[key][0])) + 1
            log.warning("In-memory rate limit exceeded for %s on %s", client_ip, request.url.path)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {max(retry_after, 1)} seconds.",
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        _IN_MEMORY_BUCKET[key].append(now)

