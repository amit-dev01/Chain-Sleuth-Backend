"""
routes_cases.py – Case graph retrieval and dashboard listing endpoints.

GET /api/v1/cases/{caseId}  – Fetch full graph (nodes + edges) for a case
GET /api/v1/cases           – Paginated CaseSummary list for the dashboard
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import get_case_by_id, list_cases as db_list_cases
from app.models.schemas import CaseSummary, TraceResult, WalletNode, TransferEdge

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["Cases"])


# ── Helper: reconstruct Pydantic models from Neo4j raw dicts ──────────────────

def _build_wallet_node(raw: dict) -> WalletNode | None:
    """Safely reconstruct a WalletNode from a raw Neo4j property dict."""
    try:
        return WalletNode(
            address       = raw.get("address", ""),
            chain         = raw.get("chain", "tron"),
            riskScore     = int(raw.get("riskScore", 0)),
            balance       = float(raw.get("balance", 0.0)),
            firstSeen     = raw.get("firstSeen") or datetime.now(timezone.utc).isoformat(),
            typologyFlags = raw.get("typologyFlags", []),
            isVasp        = raw.get("isVasp"),
        )
    except Exception as exc:
        log.warning("Could not reconstruct WalletNode: %s | raw=%s", exc, raw)
        return None


def _build_transfer_edge(raw: dict) -> TransferEdge | None:
    """Safely reconstruct a TransferEdge from a raw Neo4j relationship dict."""
    try:
        ts = raw.get("timestamp")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        elif isinstance(ts, (int, float)):
            timestamp = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        return TransferEdge.model_validate({
            "txHash":    raw.get("txHash", ""),
            "from":      raw.get("from_address", raw.get("from", "")),
            "to":        raw.get("to_address",   raw.get("to", "")),
            "value":     float(raw.get("value", 0.0)),
            "token":     raw.get("token", "USDT"),
            "timestamp": timestamp,
        })
    except Exception as exc:
        log.warning("Could not reconstruct TransferEdge: %s | raw=%s", exc, raw)
        return None


# ── GET /cases/{caseId} ───────────────────────────────────────────────────────

@router.get(
    "/{case_id}",
    response_model=TraceResult,
    summary="Retrieve full graph for a case by ID",
    description=(
        "Queries Neo4j for the stored trace graph associated with *case_id*. "
        "Returns all Wallet nodes and TRANSFER edges reconstructed from the graph, "
        "along with case metadata and risk scores. Results are Redis-cached for 2 minutes."
    ),
)
async def get_case(case_id: str) -> TraceResult:
    """
    Fetch a complete stored TraceResult from Neo4j by case_id.

    The response includes:
      - All WalletNode objects discovered during the original BFS traversal.
      - All TransferEdge objects connecting them.
      - Case metadata: suspect address, chain, risk score, status.
    """
    data = await get_case_by_id(case_id)

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found. Run POST /api/v1/trace first.",
        )

    # Reconstruct node + edge lists, dropping malformed records
    nodes = [n for raw in data.get("nodes", []) if (n := _build_wallet_node(raw)) is not None]
    edges = [e for raw in data.get("edges", []) if (e := _build_transfer_edge(raw)) is not None]

    # Parse created_at from the Neo4j datetime string
    try:
        created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        created_at = datetime.now(timezone.utc)

    return TraceResult(
        case_id            = data["case_id"],
        suspect_address    = data["suspect_address"],
        chain              = data["chain"],
        nodes              = nodes,
        edges              = edges,
        attribution        = None,
        overall_risk_score = int(data.get("overall_risk_score", 0)),
        created_at         = created_at,
        status             = data.get("status", "completed"),
    )


# ── GET /cases ────────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=List[CaseSummary],
    summary="List all cases (dashboard)",
    description=(
        "Returns a paginated list of CaseSummary objects for the investigation dashboard. "
        "Each summary includes the case ID, suspect address, chain, risk score, VASP attribution, "
        "and node/edge counts. Ordered by creation date descending."
    ),
)
async def list_all_cases(
    skip:  int = Query(default=0,  ge=0,  description="Number of records to skip"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records to return"),
) -> List[CaseSummary]:
    """
    Return a paginated list of CaseSummary objects from Neo4j.

    Ordered by ``created_at DESC`` — most recent cases first.
    """
    raw_cases = await db_list_cases(skip=skip, limit=limit)

    summaries: list[CaseSummary] = []
    for raw in raw_cases:
        try:
            created_at_str = raw.get("created_at", "")
            try:
                created_at = datetime.fromisoformat(str(created_at_str).replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                created_at = datetime.now(timezone.utc)

            summaries.append(CaseSummary(
                case_id            = raw["case_id"],
                suspect_address    = raw["suspect_address"],
                chain              = raw["chain"],
                overall_risk_score = int(raw.get("overall_risk_score", 0)),
                status             = raw.get("status", "completed"),
                node_count         = int(raw.get("node_count", 0)),
                edge_count         = int(raw.get("edge_count", 0)),
                attributed_vasp    = raw.get("attributed_vasp"),
                created_at         = created_at,
            ))
        except Exception as exc:
            log.warning("Skipping malformed case record: %s | raw=%s", exc, raw)
            continue

    return summaries
