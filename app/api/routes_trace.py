"""
routes_trace.py – Full blockchain trace pipeline endpoint.

POST /api/v1/trace
  1. Validate address format via chain_router regex detector
  2. Execute value-weighted BFS traversal (tron_tracer → Neo4j)
  3. Run typology detectors (peeling_chain, first_funder)
  4. Run VASP attribution step-back
  5. Persist Case node to Neo4j
  6. Return complete TraceResult
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.core.database import get_case_by_id, save_trace_result
from app.engine.chain_router import DetectedChain, validate_address
from app.engine.recommendations import generate_recommendations
from app.engine.traversal import run_bfs_trace
from app.engine.typology import (
    bridge_hop_detector,
    dex_swap_detector,
    fan_out_detector,
    first_funder_trace,
    ofac_sanctions_detector,
    peeling_chain_detector,
    zero_gas_burner_detector,
)
from app.models.schemas import Chain, TraceRequest, TraceResult
from app.vasp.attribution import attribute_vasp

log = logging.getLogger(__name__)

router = APIRouter(prefix="/trace", tags=["Trace"])


@router.post(
    "/",
    response_model=TraceResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate a full blockchain address trace",
    description=(
        "Accepts a TraceRequest and executes the complete ChainSleuth pipeline: "
        "address validation → BFS traversal → Neo4j graph write → typology detection "
        "→ VASP attribution step-back. Returns a fully populated TraceResult."
    ),
)
async def trace_address(payload: TraceRequest) -> TraceResult:
    """
    Full trace pipeline:
      1. Validate address format matches declared chain.
      2. Run BFS over TronGrid (with Redis caching) up to max_hops.
      3. Write all nodes + edges to Neo4j.
      4. Detect peeling-chain and first-funder typologies.
      5. Run VASP attribution step-back to isolate deposit address.
      6. Persist Case metadata node to Neo4j.
      7. Return TraceResult.
    """
    # ── 1. Address format validation ─────────────────────────────────────────
    is_valid, detected_chain = validate_address(payload.suspect_address, declared_chain=payload.chain)

    if not is_valid:
        log.warning(
            "Address validation rejected: address='%s', declared_chain='%s'",
            payload.suspect_address, payload.chain,
        )
        raise HTTPException(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            detail=f"Unrecognised address format: '{payload.suspect_address}'. "
                   "Expected TRON (T + Base58 chars), EVM (0x + 40 hex), Solana (Base58 32–44), or Bitcoin (1/3/bc1).",
        )

    # Warn if declared chain doesn't match detected format
    chain_map = {
        DetectedChain.TRON:     "tron",
        DetectedChain.ETHEREUM: "ethereum",
        DetectedChain.SOLANA:   "solana",
        DetectedChain.BITCOIN:  "bitcoin",
    }
    if detected_chain and chain_map.get(detected_chain) != payload.chain:
        log.warning(
            "Chain mismatch: declared=%s detected=%s for address=%s. "
            "Proceeding with declared chain.",
            payload.chain, detected_chain, payload.suspect_address,
        )

    # ── 2–3. BFS traversal + Neo4j graph write ────────────────────────────────
    log.info(
        "Starting trace: address=%s chain=%s hops=%d threshold=%.1f%%",
        payload.suspect_address, payload.chain,
        payload.max_hops, payload.value_threshold_pct,
    )

    try:
        result: TraceResult = await run_bfs_trace(payload)
    except Exception as exc:
        log.exception("BFS traversal failed for %s: %s", payload.suspect_address, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Traversal engine error: {exc}",
        )

    # ── 4. Typology detection ─────────────────────────────────────────────────
    try:
        peel_summary      = peeling_chain_detector(result.nodes, result.edges)
        funder_summary    = await first_funder_trace(result.nodes, result.edges)
        fan_out_summary   = fan_out_detector(result.nodes, result.edges)
        burner_summary    = zero_gas_burner_detector(result.nodes, result.edges)
        dex_summary       = dex_swap_detector(result.nodes, result.edges)
        sanctions_summary = ofac_sanctions_detector(result.nodes, result.edges)
        bridge_summary    = bridge_hop_detector(result.nodes, result.edges)
        log.info(
            "Typology: peeling=%d | funder=%d | fan_out=%d | burner=%d | dex_swap=%d | sanctions=%d | bridges=%d",
            len(peel_summary.get("flagged_addresses", [])),
            len(funder_summary.get("funder_addresses", [])),
            len(fan_out_summary.get("flagged_addresses", [])),
            len(burner_summary.get("flagged_addresses", [])),
            len(dex_summary.get("flagged_addresses", [])),
            len(sanctions_summary.get("flagged_addresses", [])),
            len(bridge_summary.get("flagged_addresses", [])),
        )
    except Exception as exc:
        # Non-fatal: log and continue
        log.warning("Typology detection failed (non-fatal): %s", exc)

    # ── 5. VASP attribution step-back ─────────────────────────────────────────
    try:
        attribution = await attribute_vasp(
            suspect_address=payload.suspect_address,
            nodes=result.nodes,
            edges=result.edges,
        )
        result = result.model_copy(update={"attribution": attribution})
        if attribution:
            log.info(
                "VASP attributed: %s (confidence=%.2f)",
                attribution.vasp_name, attribution.confidence_score,
            )
    except Exception as exc:
        log.warning("VASP attribution failed (non-fatal): %s", exc)

    # ── 6. Generate Automated Investigative Recommendations & SLA Alert ────────
    try:
        recs, sla_alert = generate_recommendations(
            nodes=result.nodes,
            edges=result.edges,
            attribution=result.attribution,
            suspect_address=result.suspect_address,
            chain=result.chain,
        )
        result = result.model_copy(update={
            "recommendations": recs,
            "sla_cashout_alert": sla_alert,
        })
    except Exception as exc:
        log.warning("Failed to generate recommendations (non-fatal): %s", exc)

    # ── 7. Persist Case node ──────────────────────────────────────────────────
    try:
        await save_trace_result({
            "case_id":            result.case_id,
            "suspect_address":    result.suspect_address,
            "chain":              result.chain,
            "overall_risk_score": result.overall_risk_score,
            "status":             result.status,
            "node_count":         len(result.nodes),
            "edge_count":         len(result.edges),
            "attributed_vasp":    result.attribution.vasp_name if result.attribution else None,
            "attribution":        result.attribution.model_dump(mode="json") if result.attribution else None,
        })
    except Exception as exc:
        log.warning("Failed to persist Case node (non-fatal): %s", exc)

    log.info(
        "Trace complete: case_id=%s nodes=%d edges=%d risk=%d recs=%d",
        result.case_id, len(result.nodes), len(result.edges), result.overall_risk_score,
        len(result.recommendations),
    )
    return result


@router.get(
    "/{case_id}",
    response_model=TraceResult,
    summary="Retrieve a previously completed trace by case ID",
)
async def get_trace(case_id: str) -> TraceResult:
    """
    Fetch a stored trace result by its case_id from Neo4j (Redis-cached).
    """
    data = await get_case_by_id(case_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trace found for case_id: {case_id}",
        )

    raw_chain = str(data.get("chain", "tron")).lower()
    chain: Chain = (
        "solana" if raw_chain == "solana"
        else "ethereum" if raw_chain == "ethereum"
        else "tron"
    )

    return TraceResult(
        case_id            = data["case_id"],
        suspect_address    = data["suspect_address"],
        chain              = chain,
        nodes              = [],    # lightweight: full nodes via /case/{id}
        edges              = [],
        attribution        = None,
        overall_risk_score = data["overall_risk_score"],
        created_at         = datetime.now(UTC),
        status             = data["status"],
    )
