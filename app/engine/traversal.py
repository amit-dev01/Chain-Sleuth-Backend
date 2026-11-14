"""
traversal.py – Value-weighted Breadth-First Search (BFS) for blockchain graph tracing.

Algorithm:
  1. Start at TraceRequest.suspect_address (depth 0).
  2. For each wallet in the BFS queue, fetch all outbound USDT transfers
     via tron_tracer.fetch_usdt_transfers().
  3. Compute the wallet's total outbound volume; drop any transfer whose
     value is below (value_threshold_pct / 100) × total_volume.
     This prunes dust/noise edges and focuses the graph on meaningful flows.
  4. Sort surviving transfers by value DESC so high-value paths are explored first.
  5. For each surviving recipient, create/merge a WalletNode and TransferEdge,
     write them into Neo4j, and enqueue the recipient if within max_hops.
  6. Return the completed TraceResult.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.core.database import (
    batch_create_transfer_edges,
    batch_merge_wallet_nodes,
    merge_wallet_node,
)
from app.engine.btc_tracer import fetch_btc_transfers, get_btc_balance
from app.engine.evm_tracer import fetch_evm_transfers, get_evm_balance
from app.engine.solana_tracer import fetch_solana_transfers, get_solana_balance
from app.engine.tron_tracer import fetch_usdt_transfers, get_account_balance
from app.models.schemas import (
    Chain,
    TraceRequest,
    TraceResult,
    TransferEdge,
    WalletNode,
)
from app.vasp.registry import is_hot_wallet

log = logging.getLogger(__name__)

# Maximum number of wallets visited per BFS (safety cap to avoid runaway queries)
_MAX_NODES = 500


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_wallet_node(
    address: str,
    chain: Chain,
    balance: float,
    risk_score: int = 0,
) -> WalletNode:
    return WalletNode(
        address=address,
        chain=chain,
        riskScore=risk_score,
        balance=balance,
        firstSeen=datetime.now(UTC).isoformat(),
        typologyFlags=[],
        isVasp=None,
    )


def _normalize_ts_sec(raw_ts: Any) -> float:
    """Normalize raw millisecond or second timestamp to UTC seconds float."""
    if not raw_ts:
        return 0.0
    try:
        val = float(raw_ts)
        return val / 1000.0 if val > 1e11 else val
    except Exception:
        return 0.0


def _make_transfer_edge(transfer: dict) -> TransferEdge:
    raw_ts = transfer.get("timestamp") or 0
    ts_sec = _normalize_ts_sec(raw_ts)
    if ts_sec > 0:
        try:
            ts_dt = datetime.fromtimestamp(ts_sec, tz=UTC)
        except Exception:
            ts_dt = datetime.now(UTC)
    else:
        ts_dt = datetime.now(UTC)

    return TransferEdge.model_validate(
        {
            "txHash":    transfer.get("tx_hash") or transfer.get("txHash") or "0x0",
            "from":      transfer.get("from_address") or transfer.get("from") or "",
            "to":        transfer.get("to_address") or transfer.get("to") or "",
            "value":     float(transfer.get("value") or 0.0),
            "token":     str(transfer.get("token") or "USDT"),
            "timestamp": ts_dt,
        }
    )


def _compute_risk_score(transfers_received: list[dict]) -> int:
    """
    Simple heuristic risk scorer based on incoming transfer volume.
    Returns an int 0–100; full scoring is handled by typology.py later.
    """
    if not transfers_received:
        return 0
    total = sum(t["value"] for t in transfers_received)
    if total > 1_000_000:
        return 80
    if total > 100_000:
        return 60
    if total > 10_000:
        return 40
    return 20


async def _fetch_transfers(address: str, chain: Chain) -> list[dict]:
    """Dispatch outbound transfer retrieval to chain-specific tracer."""
    if chain == "base":
        return await fetch_evm_transfers(address, chain="base", only_outbound=True)
    if chain == "ethereum":
        return await fetch_evm_transfers(address, chain="ethereum", only_outbound=True)
    if chain == "solana":
        return await fetch_solana_transfers(address, only_outbound=True)
    if chain == "bitcoin":
        return await fetch_btc_transfers(address, only_outbound=True)
    return await fetch_usdt_transfers(address, only_outbound=True)


async def _fetch_balance(address: str, chain: Chain) -> float:
    """Dispatch balance retrieval to chain-specific tracer."""
    if chain == "base":
        return await get_evm_balance(address, chain="base")
    if chain == "ethereum":
        return await get_evm_balance(address, chain="ethereum")
    if chain == "solana":
        return await get_solana_balance(address)
    if chain == "bitcoin":
        return await get_btc_balance(address)
    return await get_account_balance(address)


# ── Core BFS ──────────────────────────────────────────────────────────────────

async def run_bfs_trace(request: TraceRequest) -> TraceResult:
    """
    Execute a value-weighted BFS from ``request.suspect_address``.

    Args:
        request: Validated :class:`TraceRequest` (contains address, chain,
                 max_hops, value_threshold_pct, complaint_id).

    Returns:
        A fully populated :class:`TraceResult` with nodes, edges, and
        overall_risk_score; ready for VASP attribution and typology analysis.
    """
    case_id   = request.complaint_id or str(uuid4())
    chain     = request.chain
    max_hops  = request.max_hops
    threshold = request.value_threshold_pct / 100.0  # e.g. 2.0% → 0.02

    # ── State tracking ────────────────────────────────────────────────────────
    visited:      set[str]          = set()
    node_map:     dict[str, WalletNode]    = {}
    edge_map:     dict[str, TransferEdge]  = {}

    # BFS queue: (address, current_depth, min_timestamp_sec)
    queue: deque[tuple[str, int, float]] = deque()
    queue.append((request.suspect_address, 0, 0.0))
    visited.add(request.suspect_address.lower())

    # Seed the root wallet
    root_balance = await _fetch_balance(request.suspect_address, chain)
    root_node    = _make_wallet_node(request.suspect_address, chain, root_balance)
    node_map[request.suspect_address] = root_node

    await merge_wallet_node(
        address    = request.suspect_address,
        chain      = chain,
        risk_score = root_node.riskScore,
        balance    = root_balance,
    )

    log.info(
        "BFS start: address=%s chain=%s max_hops=%d threshold=%.2f%%",
        request.suspect_address, chain, max_hops, request.value_threshold_pct,
    )

    # ── BFS loop ──────────────────────────────────────────────────────────────
    while queue:
        current_address, depth, min_ts_sec = queue.popleft()

        if depth >= max_hops:
            log.debug("Max depth %d reached at %s – not expanding.", max_hops, current_address)
            continue

        if len(node_map) >= _MAX_NODES:
            log.warning("Node cap (%d) reached – stopping BFS expansion.", _MAX_NODES)
            break

        # ── Fetch outbound transfers for the current chain ────────────────────
        log.debug("Fetching transfers: depth=%d address=%s chain=%s min_ts=%.0f", depth, current_address, chain, min_ts_sec)
        try:
            transfers = await _fetch_transfers(current_address, chain)
        except Exception as exc:
            log.error("Failed to fetch transfers for %s (%s): %s", current_address, chain, exc)
            continue

        if not transfers:
            continue

        # ── Temporal Causal Filtering ─────────────────────────────────────────
        # An outbound hop is only part of the fund trail if it occurred at or after
        # the arrival timestamp of the funds at this node (depth > 0).
        if min_ts_sec > 0.0:
            filtered_transfers = [
                t for t in transfers
                if _normalize_ts_sec(t.get("timestamp")) >= min_ts_sec
            ]
            if filtered_transfers:
                transfers = filtered_transfers
            else:
                # 1-hour grace window for cross-node block time variance
                grace_ts = min_ts_sec - 3600.0
                transfers = [
                    t for t in transfers
                    if _normalize_ts_sec(t.get("timestamp")) >= grace_ts
                ]

        if not transfers:
            continue

        # ── Adaptive Smurfing-Aware Volume Pruning ────────────────────────────
        sorted_transfers = sorted(
            transfers,
            key=lambda t: float(t.get("value") or 0.0),
            reverse=True,
        )
        total_volume = sum(float(t.get("value") or 0.0) for t in sorted_transfers)

        if total_volume <= 0:
            continue

        dust_floor = 10.0
        target_cumulative = total_volume * 0.85
        per_tx_cutoff = total_volume * threshold

        accumulated = 0.0
        significant = []

        for t in sorted_transfers:
            val = float(t.get("value") or 0.0)
            if val < dust_floor and val < per_tx_cutoff:
                continue
            significant.append(t)
            accumulated += val
            # Once 85% of volume is captured and we have at least 5 paths, drop remaining long-tail noise
            if accumulated >= target_cumulative and len(significant) >= 5 and val < per_tx_cutoff:
                break

        log.debug(
            "  %s → %d transfers, total=%.2f, surviving=%d",
            current_address, len(transfers), total_volume, len(significant),
        )

        # ── Process each significant transfer ─────────────────────────────────
        nodes_to_merge: list[dict[str, Any]] = []
        edges_to_create: list[dict[str, Any]] = []

        for transfer in significant:
            recipient = transfer["to_address"]
            tx_hash   = transfer["tx_hash"]
            tx_ts_sec = _normalize_ts_sec(transfer.get("timestamp"))
            tx_dt = (
                datetime.fromtimestamp(tx_ts_sec, tz=UTC)
                if tx_ts_sec > 0
                else datetime.now(UTC)
            )

            # ── Build / update node ───────────────────────────────────────────
            if recipient not in node_map:
                bal  = await _fetch_balance(recipient, chain)
                node = _make_wallet_node(recipient, chain, bal)
                node_map[recipient] = node

                nodes_to_merge.append({
                    "address":   recipient,
                    "chain":     chain,
                    "riskScore": node.riskScore,
                    "balance":   bal,
                    "firstSeen": node.firstSeen,
                })

            # ── Terminal Sink Detection (Preventing Exchange Hairballs) ───────
            is_terminal_sink = is_hot_wallet(recipient)
            if is_terminal_sink:
                node_map[recipient].isVasp = True
                log.info(
                    "Terminal exchange sink identified at %s. Halting downstream expansion on this path.",
                    recipient,
                )

            # ── Build / update edge ───────────────────────────────────────────
            if tx_hash not in edge_map:
                edge = _make_transfer_edge(transfer)
                edge_map[tx_hash] = edge

                edges_to_create.append({
                    "fromAddress": current_address,
                    "toAddress":   recipient,
                    "chain":       chain,
                    "txHash":      tx_hash,
                    "value":       transfer["value"],
                    "token":       transfer["token"],
                    "timestamp":   tx_dt.isoformat(),
                })

            # ── Enqueue recipient for next BFS level (if not terminal sink) ──
            if not is_terminal_sink and recipient.lower() not in visited:
                visited.add(recipient.lower())
                queue.append((recipient, depth + 1, tx_ts_sec))

        # Write nodes first, then edges (guarantees referential integrity and eliminates deadlocks)
        if nodes_to_merge:
            try:
                await batch_merge_wallet_nodes(nodes_to_merge)
            except Exception as exc:
                log.error("Failed to batch merge wallet nodes: %s", exc)

        if edges_to_create:
            try:
                await batch_create_transfer_edges(edges_to_create)
            except Exception as exc:
                log.error("Failed to batch create transfer edges: %s", exc)

    # ── Compute overall risk score (simple average of node scores) ────────────
    scores = [n.riskScore for n in node_map.values()]
    overall_risk = int(sum(scores) / len(scores)) if scores else 0

    log.info(
        "BFS complete: nodes=%d edges=%d overall_risk=%d",
        len(node_map), len(edge_map), overall_risk,
    )

    return TraceResult(
        case_id            = case_id,
        suspect_address    = request.suspect_address,
        chain              = chain,
        nodes              = list(node_map.values()),
        edges              = list(edge_map.values()),
        attribution        = None,  # filled by vasp/attribution.py downstream
        overall_risk_score = overall_risk,
        created_at         = datetime.now(UTC),
        status             = "completed",
    )
