"""
btc_tracer.py – Async Bitcoin UTXO transaction tracer using public Blockstream / Mempool APIs.

Design:
  - Connects to public Blockstream / Mempool.space REST APIs.
  - Decomposes UTXO inputs (vin) and outputs (vout) into directional fund-flow edges.
  - Normalizes satoshis to BTC (10^8 satoshis = 1 BTC).
  - Deduplicates and caches lookups in Redis (5-min TTL).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.database import cache_get, cache_set

log = logging.getLogger(__name__)

MEMPOOL_API_BASE = "https://mempool.space/api"
BLOCKSTREAM_API_BASE = "https://blockstream.info/api"
_CACHE_TTL = 300


def _cache_key(address: str) -> str:
    return f"btc:transfers:{address}"


async def fetch_btc_transfers(
    address: str,
    only_outbound: bool = True,
    min_value_btc: float = 0.0,
) -> list[dict[str, Any]]:
    """
    Fetch confirmed UTXO transactions for a Bitcoin address.
    Translates UTXO inputs and outputs into directional transfer edges.
    """
    cache_key = _cache_key(address)
    cached = await cache_get(cache_key)
    if cached is not None:
        log.debug("Cache HIT – Bitcoin transfers for %s (%d records)", address, len(cached))
        return cached

    all_transfers: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MEMPOOL_API_BASE}/address/{address}/txs")
            if resp.status_code != 200:
                # Fallback to Blockstream API
                resp = await client.get(f"{BLOCKSTREAM_API_BASE}/address/{address}/txs")

            if resp.status_code == 200:
                txs = resp.json()
                for tx in txs:
                    tx_id = tx.get("txid", "")
                    status_info = tx.get("status", {})
                    block_time = status_info.get("block_time") or 0

                    # Check inputs (vin) to see if address is sender
                    vins = tx.get("vin", [])
                    is_sender = any(
                        vin.get("prevout", {}).get("scriptpubkey_address", "").lower() == address.lower()
                        for vin in vins
                    )

                    if only_outbound and not is_sender:
                        continue

                    # Process outputs (vout)
                    vouts = tx.get("vout", [])
                    for vout in vouts:
                        dest = vout.get("scriptpubkey_address", "")
                        # Skip change outputs returning to self if other outputs exist
                        if dest.lower() == address.lower() and len(vouts) > 1:
                            continue

                        satoshis = vout.get("value", 0)
                        btc_val = satoshis / 100_000_000

                        if btc_val < min_value_btc:
                            continue

                        all_transfers.append({
                            "tx_hash": tx_id,
                            "from_address": address if is_sender else (vins[0].get("prevout", {}).get("scriptpubkey_address", "") if vins else "Coinbase"),
                            "to_address": dest or "Unknown Output",
                            "value": round(btc_val, 8),
                            "token": "BTC",
                            "contract": "NATIVE",
                            "block_ts": block_time * 1000,
                            "timestamp": block_time,
                        })
    except Exception as exc:
        log.warning("Bitcoin UTXO query failed for %s: %s", address, exc)

    log.info("Bitcoin fetch complete: %s -> %d transfer edges", address, len(all_transfers))
    await cache_set(cache_key, all_transfers, ttl=_CACHE_TTL)
    return all_transfers


async def get_btc_balance(address: str) -> float:
    """Fetch current confirmed balance in BTC for a Bitcoin address."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{MEMPOOL_API_BASE}/address/{address}")
            if resp.status_code == 200:
                stats = resp.json().get("chain_stats", {})
                funded = stats.get("funded_txo_sum", 0)
                spent = stats.get("spent_txo_sum", 0)
                satoshis = funded - spent
                return max(0.0, satoshis / 100_000_000)
    except Exception as exc:
        log.debug("Could not fetch Bitcoin balance for %s: %s", address, exc)
    return 0.0
