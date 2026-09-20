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

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4

from app.core.database import (
    create_transfer_edge,
    merge_wallet_node,
)
from app.engine.tron_tracer import fetch_usdt_transfers, get_account_balance
from app.models.schemas import (
    Chain,
    TraceRequest,
    TraceResult,
    TransferEdge,
    WalletNode,
)

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
        firstSeen=datetime.now(timezone.utc).isoformat(),
        typologyFlags=[],
        isVasp=None,
    )


def _make_transfer_edge(transfer: dict) -> TransferEdge:
    return TransferEdge.model_validate(
        {
            "txHash":    transfer["tx_hash"],
            "from":      transfer["from_address"],
            "to":        transfer["to_address"],
            "value":     transfer["value"],
            "token":     transfer["token"],
            "timestamp": datetime.fromtimestamp(transfer["timestamp"], tz=timezone.utc),
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

    # BFS queue: (address, current_depth)
    queue: deque[tuple[str, int]] = deque()
    queue.append((request.suspect_address, 0))
    visited.add(request.suspect_address.lower())

    # Seed the root wallet
    root_balance = await get_account_balance(request.suspect_address)
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
        current_address, depth = queue.popleft()

        if depth >= max_hops:
            log.debug("Max depth %d reached at %s – not expanding.", max_hops, current_address)
            continue

        if len(node_map) >= _MAX_NODES:
            log.warning("Node cap (%d) reached – stopping BFS expansion.", _MAX_NODES)
            break

        # ── Fetch outbound USDT transfers (cached by tron_tracer) ─────────────
        log.debug("Fetching transfers: depth=%d address=%s", depth, current_address)
        try:
            transfers = await fetch_usdt_transfers(
                address=current_address,
                only_outbound=True,
            )
        except Exception as exc:
            log.error("Failed to fetch transfers for %s: %s", current_address, exc)
            continue

        if not transfers:
            continue

        # ── Value-weighted filtering ──────────────────────────────────────────
        total_volume = sum(t["value"] for t in transfers)
        cutoff_value = total_volume * threshold

        # Sort by value DESC (high-value hops explored first)
        significant = sorted(
            [t for t in transfers if t["value"] >= cutoff_value],
            key=lambda t: t["value"],
            reverse=True,
        )

        log.debug(
            "  %s → %d transfers, total=%.2f USDT, cutoff=%.2f, surviving=%d",
            current_address, len(transfers), total_volume, cutoff_value, len(significant),
        )

        # ── Process each significant transfer ─────────────────────────────────
        neo4j_tasks = []

        for transfer in significant:
            recipient = transfer["to_address"]
            tx_hash   = transfer["tx_hash"]

            # ── Build / update edge ───────────────────────────────────────────
            if tx_hash not in edge_map:
                edge = _make_transfer_edge(transfer)
                edge_map[tx_hash] = edge

                # Write edge to Neo4j (non-blocking, collected below)
                neo4j_tasks.append(
                    create_transfer_edge(
                        from_address = current_address,
                        to_address   = recipient,
                        chain        = chain,
                        tx_hash      = tx_hash,
                        value        = transfer["value"],
                        token        = transfer["token"],
                        timestamp    = datetime.fromtimestamp(
                            transfer["timestamp"], tz=timezone.utc
                        ),
                    )
                )

            # ── Build / update node ───────────────────────────────────────────
            if recipient not in node_map:
                bal  = await get_account_balance(recipient)
                node = _make_wallet_node(recipient, chain, bal)
                node_map[recipient] = node

                neo4j_tasks.append(
                    merge_wallet_node(
                        address    = recipient,
                        chain      = chain,
                        risk_score = node.riskScore,
                        balance    = bal,
                    )
                )

            # ── Enqueue recipient for next BFS level ──────────────────────────
            if recipient.lower() not in visited:
                visited.add(recipient.lower())
                queue.append((recipient, depth + 1))

        # Flush Neo4j writes concurrently for this BFS level
        if neo4j_tasks:
            await asyncio.gather(*neo4j_tasks, return_exceptions=True)

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
        created_at         = datetime.now(timezone.utc),
        status             = "completed",
    )
