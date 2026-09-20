"""
database.py – Async connection helpers for Neo4j and Redis.
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import get_settings

settings = get_settings()

# ── Neo4j ────────────────────────────────────────────────────────────────────

_neo4j_driver: AsyncDriver | None = None


async def get_neo4j_driver() -> AsyncDriver:
    """Return (or lazily create) the shared Neo4j async driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _neo4j_driver


async def close_neo4j_driver() -> None:
    """Close the Neo4j driver on application shutdown."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        await _neo4j_driver.close()
        _neo4j_driver = None


@asynccontextmanager
async def neo4j_session() -> AsyncGenerator:
    """Async context manager that yields a Neo4j session."""
    driver = await get_neo4j_driver()
    async with driver.session() as session:
        yield session


# ── Redis ────────────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return (or lazily create) the shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
