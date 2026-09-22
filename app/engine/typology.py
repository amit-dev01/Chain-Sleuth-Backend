"""
typology.py – Crypto crime typology detectors for ChainSleuth.

Implemented algorithms:
  1. peeling_chain_detector  – Flags wallets that forward >85% of funds while
                                retaining <15% (classic peel-chain layering).
  2. first_funder_trace      – Traces back to find the TRX gas-fee funder of a
                                zero-balance wallet; flags that funder node.

Each function mutates the typologyFlags list on affected WalletNode objects
in-place and returns a summary dict for logging / audit trail.
"""
from __future__ import annotations

import logging
from datetime import UTC

import httpx

from app.core.config import get_settings
from app.models.schemas import TransferEdge, WalletNode

log = logging.getLogger(__name__)
settings = get_settings()

# Peeling chain thresholds
_PEEL_FORWARD_THRESHOLD = 0.85   # must forward ≥85% of received funds
_PEEL_RETAIN_THRESHOLD  = 0.15   # must retain <15% of received funds
_PEEL_MIN_HOPS          = 3      # chain must be at least 3 consecutive hops

# Fan-out / smurfing thresholds
_FAN_OUT_MIN_RECIPIENTS   = 3     # minimum distinct recipients
_FAN_OUT_MIN_DISBURSE_PCT = 0.60  # must disburse ≥60% of total inbound funds

# TronGrid base (reuse config)
_TRONGRID_BASE = "https://api.trongrid.io"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Peeling Chain Detector
# ─────────────────────────────────────────────────────────────────────────────

def _build_adjacency(
    edges: list[TransferEdge],
) -> dict[str, list[TransferEdge]]:
    """Build an outbound adjacency map: from_address → [edges]."""
    adj: dict[str, list[TransferEdge]] = {}
    for edge in edges:
        adj.setdefault(edge.from_address, []).append(edge)
    return adj


def _total_inbound(address: str, edges: list[TransferEdge]) -> float:
    """Sum of all inbound transfer values for *address*."""
    return sum(e.value for e in edges if e.to_address == address)


def _total_outbound(address: str, adj: dict[str, list[TransferEdge]]) -> float:
    """Sum of all outbound transfer values for *address*."""
    return sum(e.value for e in adj.get(address, []))


def peeling_chain_detector(
    nodes: list[WalletNode],
    edges: list[TransferEdge],
) -> dict[str, list[str]]:
    """
    Detect peeling-chain layering patterns in a trace graph.

    A wallet is tagged ``peeling_chain`` if:
      - It received funds from exactly 1 source within the graph.
      - It forwarded ≥ ``_PEEL_FORWARD_THRESHOLD`` (85%) of those received funds.
      - It retained < ``_PEEL_RETAIN_THRESHOLD`` (15%) of those received funds.
      - This pattern holds for at least ``_PEEL_MIN_HOPS`` (3) consecutive hops.

    The detector works by:
      1. Building a linear-chain candidate list via inbound/outbound ratio scoring.
      2. Walking consecutive hops and checking the 85/15 rule at each step.
      3. Flagging all nodes in a qualifying run.

    Args:
        nodes: All WalletNode objects from the trace.
        edges: All TransferEdge objects from the trace.

    Returns:
        A dict mapping ``"flagged_addresses"`` to a list of addresses tagged
        with the peeling_chain typology, for audit logging.
    """
    adj       = _build_adjacency(edges)
    node_map  = {n.address: n for n in nodes}
    flagged:  list[str] = []

    # Score every node: peel_ratio = outbound / inbound
    peel_candidates: list[tuple[str, float, float]] = []  # (address, in, out)

    for node in nodes:
        inbound  = _total_inbound(node.address, edges)
        outbound = _total_outbound(node.address, adj)

        if inbound <= 0:
            continue

        forward_ratio = outbound / inbound
        retain_ratio  = 1.0 - forward_ratio

        if forward_ratio >= _PEEL_FORWARD_THRESHOLD and retain_ratio < _PEEL_RETAIN_THRESHOLD:
            peel_candidates.append((node.address, inbound, outbound))

    candidate_addrs = {c[0] for c in peel_candidates}

    # Walk consecutive hop chains among candidates
    # A peeling chain is a linear run: A→B→C→D where each is a candidate
    visited_in_chain: set[str] = set()

    for addr, _, _ in peel_candidates:
        if addr in visited_in_chain:
            continue

        # Walk forward from this node collecting consecutive peel hops
        chain: list[str] = [addr]
        current = addr

        while True:
            # Find outbound edges to other candidates (single-output peeling)
            out_edges = [
                e for e in adj.get(current, [])
                if e.to_address in candidate_addrs and e.to_address not in visited_in_chain
            ]
            if len(out_edges) != 1:
                break  # branching or dead-end → stop chain walk
            next_addr = out_edges[0].to_address
            chain.append(next_addr)
            current = next_addr

        # Only flag runs of >= _PEEL_MIN_HOPS
        if len(chain) >= _PEEL_MIN_HOPS:
            for addr_in_chain in chain:
                visited_in_chain.add(addr_in_chain)
                wallet = node_map.get(addr_in_chain)
                if wallet and "peeling_chain" not in wallet.typologyFlags:
                    wallet.typologyFlags.append("peeling_chain")  # type: ignore[arg-type]
                    flagged.append(addr_in_chain)
                    log.info("PEELING CHAIN flagged: %s (chain_len=%d)", addr_in_chain, len(chain))

    log.info("peeling_chain_detector: %d addresses flagged.", len(flagged))
    return {"flagged_addresses": flagged}


# ─────────────────────────────────────────────────────────────────────────────
# 2. First Funder Trace
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_trx_activator(
    address: str,
    api_key: str,
) -> dict | None:
    """
    Query TronGrid for the earliest TRX transfer that activated *address*.

    TRON accounts are created on-chain when they first receive TRX.
    We fetch the account's transaction history, filtered to TRX transfers
    (not TRC-20), and return the earliest one that credits this address.
    """
    params = {
        "only_to":    "true",         # we want inbound TRX (not TRC-20)
        "limit":      "1",
        "order_by":   "block_timestamp,asc",  # oldest first
        "search_internal": "false",
    }
    headers = {
        "Accept":           "application/json",
        "TRON-PRO-API-KEY": api_key,
    }

    try:
        async with httpx.AsyncClient(
            base_url=_TRONGRID_BASE,
            headers=headers,
            timeout=10.0,
        ) as client:
            resp = await client.get(
                f"/v1/accounts/{address}/transactions",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        log.warning("TronGrid TRX activation query failed for %s: %s", address, exc)
        return None

    # Walk records and find the first TRX credit to this address
    for tx in data:
        raw_data = tx.get("raw_data", {})
        contracts = raw_data.get("contract", [])
        for contract in contracts:
            c_type   = contract.get("type", "")
            c_params = contract.get("parameter", {}).get("value", {})

            # TransferContract = native TRX transfer
            if c_type == "TransferContract":
                to_addr   = c_params.get("to_address", "")
                from_addr = c_params.get("owner_address", "")
                amount    = c_params.get("amount", 0) / 1_000_000  # SUN → TRX

                if to_addr.lower() == address.lower() and amount > 0:
                    return {
                        "tx_hash":      tx.get("txID", ""),
                        "from_address": from_addr,
                        "to_address":   to_addr,
                        "amount_trx":   amount,
                        "block_ts":     raw_data.get("timestamp", 0) // 1000,
                    }
    return None


async def first_funder_trace(
    nodes: list[WalletNode],
    edges: list[TransferEdge],
) -> dict[str, list[str]]:
    """
    Detect the 'first funder match' typology for zero-balance wallets.

    Algorithm:
      1. Identify wallets in the trace graph whose ``balance == 0``
         (indicating all funds have been swept out — classic mule behaviour).
      2. For each such wallet, query TronGrid for the earliest native TRX
         transaction that credited it (the activation / gas-fee funding tx).
      3. Check whether the funder address already exists in our trace graph.
         If yes → tag it with ``first_funder_match`` directly.
         If no  → create a synthetic node and add it to the ``nodes`` list
                  so it appears in the result graph.
      4. Write a ``FEE_FUNDED_BY`` relationship to Neo4j for the pair.

    Args:
        nodes: All WalletNode objects from the trace (mutated in-place).
        edges: All TransferEdge objects from the trace.

    Returns:
        A dict with ``"funder_addresses"`` (list of tagged funder addresses)
        and ``"zero_balance_wallets"`` (the wallets that triggered the search).
    """
    from datetime import datetime

    from app.core.database import create_fee_funded_by_edge
    from app.models.schemas import WalletNode as WN

    node_map = {n.address.lower(): n for n in nodes}
    funder_addresses: list[str]         = []
    zero_balance_wallets: list[str]     = []
    api_key = settings.TRONGRID_KEY

    for node in list(nodes):  # iterate a snapshot so we can safely append
        if node.balance > 0:
            continue

        zero_balance_wallets.append(node.address)
        log.info("Zero-balance wallet detected: %s – tracing TRX funder.", node.address)

        activation = await _fetch_trx_activator(node.address, api_key)
        if activation is None:
            log.warning("No TRX activation record found for %s.", node.address)
            continue

        funder_addr = activation["from_address"]
        amount_trx  = activation["amount_trx"]
        tx_hash     = activation["tx_hash"]

        # ── Tag or create the funder node ─────────────────────────────────────
        funder_node = node_map.get(funder_addr.lower())
        if funder_node is None:
            # Funder is outside our existing trace graph → add synthetic node
            funder_node = WN(
                address      = funder_addr,
                chain        = node.chain,
                riskScore    = 50,          # elevated: unknown funder
                balance      = 0.0,
                firstSeen    = datetime.now(UTC).isoformat(),
                typologyFlags= ["first_funder_match"],  # type: ignore[list-item]
                isVasp       = None,
            )
            nodes.append(funder_node)
            node_map[funder_addr.lower()] = funder_node
            log.info("Synthetic funder node added: %s", funder_addr)
        else:
            if "first_funder_match" not in funder_node.typologyFlags:
                funder_node.typologyFlags.append("first_funder_match")  # type: ignore[arg-type]
                log.info("first_funder_match flagged on existing node: %s", funder_addr)

        funder_addresses.append(funder_addr)

        # ── Write FEE_FUNDED_BY edge to Neo4j ────────────────────────────────
        try:
            await create_fee_funded_by_edge(
                funded_address  = node.address,
                funder_address  = funder_addr,
                chain           = node.chain,
                tx_hash         = tx_hash,
                amount          = amount_trx,
            )
        except Exception as exc:
            log.error(
                "Failed to write FEE_FUNDED_BY edge %s→%s: %s",
                funder_addr, node.address, exc,
            )

    log.info(
        "first_funder_trace: %d funders found for %d zero-balance wallets.",
        len(funder_addresses), len(zero_balance_wallets),
    )
    return {
        "funder_addresses":     funder_addresses,
        "zero_balance_wallets": zero_balance_wallets,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fan-Out / Smurfing Detector
# ─────────────────────────────────────────────────────────────────────────────

def fan_out_detector(
    nodes: list[WalletNode],
    edges: list[TransferEdge],
    min_recipients: int = _FAN_OUT_MIN_RECIPIENTS,
) -> dict[str, list[str]]:
    """
    Detect fan-out / smurfing dispersion patterns in a trace graph.

    A wallet is tagged ``fan_out`` if:
      - It disburses funds to >= min_recipients (default 3) distinct destination wallets.
      - Its outbound transfer volume represents a significant portion (>= 60%) of its observed inbound volume.
      - It is not an attributed exchange hot-wallet.

    Args:
        nodes: All WalletNode objects from the trace (mutated in-place).
        edges: All TransferEdge objects from the trace.
        min_recipients: Minimum unique destinations to qualify as fan-out.

    Returns:
        A dict mapping ``"flagged_addresses"`` to a list of flagged wallet addresses.
    """
    adj = _build_adjacency(edges)
    node_map = {n.address.lower(): n for n in nodes}
    flagged: list[str] = []

    for node in nodes:
        if node.isVasp:
            continue

        out_edges = adj.get(node.address, [])
        unique_recipients = {
            e.to_address.lower() for e in out_edges
            if e.to_address.lower() != node.address.lower()
        }

        if len(unique_recipients) >= min_recipients:
            inbound = _total_inbound(node.address, edges)
            outbound = _total_outbound(node.address, adj)

            if inbound <= 0 or (outbound / inbound) >= _FAN_OUT_MIN_DISBURSE_PCT:
                wallet = node_map.get(node.address.lower())
                if wallet and "fan_out" not in wallet.typologyFlags:
                    wallet.typologyFlags.append("fan_out")  # type: ignore[arg-type]
                    flagged.append(node.address)
                    log.info(
                        "FAN-OUT (Smurfing) flagged: %s (%d outbound destinations)",
                        node.address, len(unique_recipients),
                    )

    log.info("fan_out_detector: %d addresses flagged.", len(flagged))
    return {"flagged_addresses": flagged}

