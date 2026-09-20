"""
database.py – Async Neo4j (Community 5.x) driver pool + Redis cache layer.

Responsibilities:
  - Manage a single shared AsyncDriver (connection pool built-in to neo4j 5.x)
  - Provide typed helpers to MERGE Wallet and VASP nodes
  - Provide typed helpers to CREATE TRANSFER, FEE_FUNDED_BY, OWNED_BY_VASP relationships
  - Run the VASP path-discovery Cypher query
  - Provide a shared async Redis client for RPC transaction caching
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

import redis.asyncio as aioredis
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import Neo4jError

from app.core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Neo4j – Driver Pool
# ─────────────────────────────────────────────────────────────────────────────
# neo4j-python 5.x manages an internal connection pool automatically.
# We keep a single module-level AsyncDriver so the pool is reused across requests.

_neo4j_driver: AsyncDriver | None = None


async def init_neo4j() -> AsyncDriver:
    """
    Create (or return) the shared AsyncDriver.

    Pool tuning is handled via driver kwargs; Community Edition does not
    support Causal Clustering, so we target a single Bolt endpoint.
    """
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            # ── Connection pool settings ──────────────────────────────────
            max_connection_pool_size=50,       # concurrent bolt connections
            connection_timeout=10.0,            # seconds to establish connection
            max_connection_lifetime=3600,       # rotate connections after 1 h
            keep_alive=True,
            # ── Driver-level notifications ────────────────────────────────
            notifications_min_severity="WARNING",
        )
        log.info("Neo4j AsyncDriver initialised → %s", settings.NEO4J_URI)
    return _neo4j_driver


async def close_neo4j() -> None:
    """Drain the connection pool gracefully on application shutdown."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        await _neo4j_driver.close()
        _neo4j_driver = None
        log.info("Neo4j AsyncDriver closed.")


@asynccontextmanager
async def get_session(
    database: str = "neo4j",
    fetch_size: int = 1000,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager that yields a Neo4j session from the pool.

    Usage::

        async with get_session() as session:
            result = await session.run(...)
    """
    driver = await init_neo4j()
    async with driver.session(database=database, fetch_size=fetch_size) as session:
        yield session


# ─────────────────────────────────────────────────────────────────────────────
# Redis – Async Client (RPC transaction cache)
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None
_CACHE_TTL_SECONDS = 300  # 5 minutes default TTL for RPC transaction data


async def init_redis() -> aioredis.Redis:
    """Create (or return) the shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        log.info("Redis client initialised → %s", settings.REDIS_URL)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection pool on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        log.info("Redis client closed.")


async def cache_set(key: str, value: Any, ttl: int = _CACHE_TTL_SECONDS) -> None:
    """Serialise *value* to JSON and store it in Redis with *ttl* seconds expiry."""
    client = await init_redis()
    await client.setex(key, ttl, json.dumps(value, default=str))


async def cache_get(key: str) -> Any | None:
    """Return the cached value for *key*, or None if absent / expired."""
    client = await init_redis()
    raw = await client.get(key)
    return json.loads(raw) if raw is not None else None


async def cache_delete(key: str) -> None:
    """Invalidate a single cache entry."""
    client = await init_redis()
    await client.delete(key)


# ─────────────────────────────────────────────────────────────────────────────
# Schema helpers – run once on startup to create constraints & indexes
# ─────────────────────────────────────────────────────────────────────────────

_SCHEMA_QUERIES = [
    # Wallet uniqueness constraint (also creates an index)
    "CREATE CONSTRAINT wallet_address_unique IF NOT EXISTS "
    "FOR (w:Wallet) REQUIRE (w.address, w.chain) IS UNIQUE",
    # VASP uniqueness constraint
    "CREATE CONSTRAINT vasp_name_unique IF NOT EXISTS "
    "FOR (v:VASP) REQUIRE v.name IS UNIQUE",
    # Index for fast risk-score range queries
    "CREATE INDEX wallet_risk_idx IF NOT EXISTS FOR (w:Wallet) ON (w.riskScore)",
]


async def ensure_schema() -> None:
    """Idempotently create Neo4j constraints and indexes for ChainSleuth."""
    async with get_session() as session:
        for q in _SCHEMA_QUERIES:
            try:
                await session.run(q)
            except Neo4jError as exc:
                log.warning("Schema query skipped (%s): %s", exc.code, q)
    log.info("Neo4j schema constraints/indexes verified.")


# ─────────────────────────────────────────────────────────────────────────────
# Node helpers
# ─────────────────────────────────────────────────────────────────────────────

async def merge_wallet_node(
    address: str,
    chain: str,
    risk_score: int = 0,
    balance: float = 0.0,
    first_seen: Optional[datetime] = None,
) -> None:
    """
    MERGE a :Wallet node, creating it if absent or updating properties if present.

    Node label: ``Wallet``
    Properties:
      - address    (str)   – on-chain address (part of uniqueness key)
      - chain      (str)   – blockchain identifier (part of uniqueness key)
      - riskScore  (int)   – 0-100 composite risk score
      - balance    (float) – native token balance
      - firstSeen  (str)   – ISO-8601 datetime of first observed tx
    """
    first_seen_iso = (first_seen or datetime.now(timezone.utc)).isoformat()
    cypher = """
        MERGE (w:Wallet {address: $address, chain: $chain})
        ON CREATE SET
            w.riskScore  = $riskScore,
            w.balance    = $balance,
            w.firstSeen  = $firstSeen,
            w.createdAt  = datetime()
        ON MATCH SET
            w.riskScore  = $riskScore,
            w.balance    = $balance,
            w.updatedAt  = datetime()
    """
    async with get_session() as session:
        await session.run(
            cypher,
            address=address,
            chain=chain,
            riskScore=risk_score,
            balance=balance,
            firstSeen=first_seen_iso,
        )


async def merge_vasp_node(
    name: str,
    is_fiu_registered: bool,
    deposit_address: str,
    hot_wallet: str,
    nodal_email: str,
) -> None:
    """
    MERGE a :VASP node.

    Node label: ``VASP``
    Properties:
      - name             (str)  – legal / trade name of the VASP (uniqueness key)
      - isFiuRegistered  (bool) – FIU-IND registration status
      - depositAddress   (str)  – suspect's deposit address at this VASP
      - hotWallet        (str)  – VASP's identified hot wallet address
      - nodalEmail       (str)  – compliance / nodal officer email
    """
    cypher = """
        MERGE (v:VASP {name: $name})
        ON CREATE SET
            v.isFiuRegistered = $isFiuRegistered,
            v.depositAddress  = $depositAddress,
            v.hotWallet       = $hotWallet,
            v.nodalEmail      = $nodalEmail,
            v.createdAt       = datetime()
        ON MATCH SET
            v.isFiuRegistered = $isFiuRegistered,
            v.depositAddress  = $depositAddress,
            v.hotWallet       = $hotWallet,
            v.nodalEmail      = $nodalEmail,
            v.updatedAt       = datetime()
    """
    async with get_session() as session:
        await session.run(
            cypher,
            name=name,
            isFiuRegistered=is_fiu_registered,
            depositAddress=deposit_address,
            hotWallet=hot_wallet,
            nodalEmail=nodal_email,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Relationship helpers
# ─────────────────────────────────────────────────────────────────────────────

async def create_transfer_edge(
    from_address: str,
    to_address: str,
    chain: str,
    tx_hash: str,
    value: float,
    token: str,
    timestamp: datetime,
) -> None:
    """
    Create a ``[:TRANSFER]`` relationship between two :Wallet nodes.

    Relationship properties:
      - txHash    (str)   – on-chain transaction hash
      - value     (float) – amount transferred in *token* units
      - token     (str)   – token symbol / contract (e.g. 'USDT', 'TRX')
      - timestamp (str)   – ISO-8601 confirmed datetime
    """
    cypher = """
        MATCH (from:Wallet {address: $fromAddress, chain: $chain})
        MATCH (to:Wallet   {address: $toAddress,   chain: $chain})
        MERGE (from)-[t:TRANSFER {txHash: $txHash}]->(to)
        ON CREATE SET
            t.value     = $value,
            t.token     = $token,
            t.timestamp = $timestamp
        ON MATCH SET
            t.value     = $value,
            t.token     = $token,
            t.timestamp = $timestamp
    """
    async with get_session() as session:
        await session.run(
            cypher,
            fromAddress=from_address,
            toAddress=to_address,
            chain=chain,
            txHash=tx_hash,
            value=value,
            token=token,
            timestamp=timestamp.isoformat(),
        )


async def create_fee_funded_by_edge(
    funded_address: str,
    funder_address: str,
    chain: str,
    tx_hash: str,
    amount: float,
) -> None:
    """
    Create a ``[:FEE_FUNDED_BY]`` relationship.

    Indicates that *funder_address* paid the gas / bandwidth fee that
    activated *funded_address* — a key indicator of 'first funder' typology.

    Relationship properties:
      - txHash  (str)   – funding transaction hash
      - amount  (float) – fee amount paid (in native token)
    """
    cypher = """
        MATCH (funded:Wallet {address: $fundedAddress, chain: $chain})
        MATCH (funder:Wallet {address: $funderAddress, chain: $chain})
        MERGE (funded)-[f:FEE_FUNDED_BY {txHash: $txHash}]->(funder)
        ON CREATE SET f.amount = $amount
        ON MATCH  SET f.amount = $amount
    """
    async with get_session() as session:
        await session.run(
            cypher,
            fundedAddress=funded_address,
            funderAddress=funder_address,
            chain=chain,
            txHash=tx_hash,
            amount=amount,
        )


async def create_owned_by_vasp_edge(
    wallet_address: str,
    chain: str,
    vasp_name: str,
) -> None:
    """
    Create an ``[:OWNED_BY_VASP]`` relationship from a :Wallet to a :VASP.

    Used after VASP attribution confirms that *wallet_address* is a
    deposit / hot-wallet controlled by *vasp_name*.
    """
    cypher = """
        MATCH (w:Wallet {address: $address, chain: $chain})
        MATCH (v:VASP   {name: $vaspName})
        MERGE (w)-[:OWNED_BY_VASP]->(v)
    """
    async with get_session() as session:
        await session.run(
            cypher,
            address=wallet_address,
            chain=chain,
            vaspName=vasp_name,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Path discovery – VASP deposit address reachability
# ─────────────────────────────────────────────────────────────────────────────

async def find_shortest_path_to_vasp(
    suspect_address: str,
    known_vasp_deposit_addresses: list[str],
) -> dict[str, Any] | None:
    """
    Discover the shortest TRANSFER path from *suspect_address* to any known
    VASP deposit address within 1–5 hops.

    Cypher executed::

        MATCH path = (start:Wallet {address: $suspect_address})
                     -[:TRANSFER*1..5]->
                     (target:Wallet)
        WHERE target.address IN $known_vasp_deposit_addresses
        RETURN path, target
        ORDER BY length(path) ASC
        LIMIT 1

    Returns:
        A dict with keys ``path_length``, ``target_address``, ``hops``
        (list of address strings along the path), and ``relationships``
        (list of edge property dicts); or ``None`` if no path is found.
    """
    # Check Redis cache first
    cache_key = f"vasp_path:{suspect_address}"
    cached = await cache_get(cache_key)
    if cached is not None:
        log.debug("Cache HIT for path query: %s", cache_key)
        return cached

    cypher = """
        MATCH path = (start:Wallet {address: $suspect_address})
                     -[:TRANSFER*1..5]->
                     (target:Wallet)
        WHERE target.address IN $known_vasp_deposit_addresses
        RETURN path, target
        ORDER BY length(path) ASC
        LIMIT 1
    """

    async with get_session() as session:
        result = await session.run(
            cypher,
            suspect_address=suspect_address,
            known_vasp_deposit_addresses=known_vasp_deposit_addresses,
        )
        record = await result.single()

    if record is None:
        log.info("No VASP path found for suspect: %s", suspect_address)
        return None

    # ── Deserialise Neo4j path object ────────────────────────────────────────
    neo4j_path = record["path"]
    target_node = record["target"]

    hops: list[str] = [node["address"] for node in neo4j_path.nodes]
    relationships: list[dict] = [
        {
            "txHash":    rel["txHash"],
            "value":     rel["value"],
            "token":     rel["token"],
            "timestamp": rel["timestamp"],
        }
        for rel in neo4j_path.relationships
    ]

    result_payload: dict[str, Any] = {
        "path_length":     len(neo4j_path.relationships),
        "target_address":  target_node["address"],
        "hops":            hops,
        "relationships":   relationships,
    }

    # Persist to Redis cache (5-minute TTL)
    await cache_set(cache_key, result_payload)
    log.info(
        "VASP path found: %s → %s (%d hops)",
        suspect_address,
        target_node["address"],
        len(neo4j_path.relationships),
    )
    return result_payload
