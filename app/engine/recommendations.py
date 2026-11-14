"""
recommendations.py – Automated investigative recommendations & real-time cash-out SLA engine.

Generates contextual, actionable next steps for Investigating Officers (IOs)
based on detected typologies, VASP attribution, and cash-out window urgency.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.models.schemas import TransferEdge, VASPAttribution, WalletNode

log = logging.getLogger(__name__)


def generate_recommendations(
    nodes: list[WalletNode],
    edges: list[TransferEdge],
    attribution: VASPAttribution | None,
    suspect_address: str,
    chain: str = "tron",
) -> tuple[list[str], str]:
    """
    Produce an SLA cash-out alert and an ordered list of actionable recommendations for the IO.

    Returns:
        (recommendations, sla_cashout_alert)
    """
    recs: list[str] = []

    # ── 1. Real-time Cash-Out SLA Assessment ──────────────────────────────────
    sla_alert = (
        "NORMAL MONITORING: Transaction activity evaluated. Proceed with standard "
        "investigative documentation."
    )

    if edges:
        # Find latest edge by timestamp
        latest_edge = max(edges, key=lambda e: e.timestamp)
        now_utc = datetime.now(UTC)
        edge_time = latest_edge.timestamp
        if edge_time.tzinfo is None:
            edge_time = edge_time.replace(tzinfo=UTC)

        delta = now_utc - edge_time
        mins_elapsed = max(0, int(delta.total_seconds() / 60))

        if mins_elapsed <= 45:
            sla_alert = (
                f"⚡ HIGH URGENCY: Latest transaction recorded ~{mins_elapsed} minutes ago. "
                f"Immediate risk of asset transfer or liquidation. Serve compliance freeze notice "
                f"to prevent asset movement."
            )
        elif mins_elapsed <= 180:
            hours_elapsed = max(1, mins_elapsed // 60)
            sla_alert = (
                f"⚠️ ACTIVE TIMEFRAME: Activity recorded ~{hours_elapsed} hours ago. Off-ramp "
                f"settlement may still be pending. Notify compliance officers for identified exchanges."
            )
        else:
            days_elapsed = max(1, mins_elapsed // 1440)
            sla_alert = (
                f"📋 HISTORICAL ACTIVITY: Trail indicates activity from ~{days_elapsed} days ago. "
                f"Funds likely settled or transferred downstream. Issue formal records request for "
                f"account identification and transaction histories."
            )

    # ── 2. VASP Attribution Directives ────────────────────────────────────────
    if attribution:
        fiu_text = (
            "FIU-Registered VASP"
            if attribution.is_fiu_registered
            else "Offshore / Unregistered Exchange"
        )
        recs.append(
            f"1. ISSUE COMPLIANCE NOTICE: Direct compliance freeze notice to {attribution.vasp_name} "
            f"({fiu_text}) legal contact at {attribution.nodal_officer_email}. Request restriction "
            f"on KYC deposit address: {attribution.deposit_address}."
        )
        recs.append(
            f"2. REQUEST KYC & TRANSACTION RECORDS: Request account verification profile for {attribution.deposit_address} "
            f"from {attribution.vasp_name}, including registered identification, phone, IP access logs, "
            f"and associated withdrawal settlement records."
        )
        recs.append(
            f"3. HOT WALLET SEPARATION: Note that {attribution.hot_wallet_address} is an omnibus exchange hot wallet. "
            f"Direct freeze requests strictly to user deposit address {attribution.deposit_address} to ensure targeted execution."
        )
    else:
        recs.append(
            "1. EXTEND GRAPH TRAVERSAL: No direct exchange deposit identified within current hop limit. "
            "Increase hop depth or adjust transfer value threshold to continue tracking downstream flow."
        )

    # ── 3. Typology-Specific Action Items ─────────────────────────────────────
    # Check for First Funder / Gas Funder
    funder_nodes = [
        n.address for n in nodes
        if "first_funder_match" in n.typologyFlags
    ]
    if funder_nodes:
        recs.append(
            f"4. GAS FUNDER IDENTIFICATION: Target address received initial gas funding from {funder_nodes[0]}. "
            f"Correlate this funding address across incident records to identify related case files."
        )

    # Check for Peeling Chain / Layering
    peel_nodes = [
        n.address for n in nodes
        if "peeling_chain" in n.typologyFlags
    ]
    if peel_nodes:
        recs.append(
            f"5. PEELING CHAIN PATTERN: {len(peel_nodes)} transit addresses exhibit sequential peeling behavior "
            f"(>85% forwarded, <15% routed). Consistent with automated transaction structuring."
        )

    # Check for Fan-Out / Smurfing
    fan_nodes = [
        n.address for n in nodes
        if "fan_out" in n.typologyFlags
    ]
    if fan_nodes:
        recs.append(
            f"6. FAN-OUT / STRUCTURING PATTERN: Address {fan_nodes[0]} distributed funds across multiple parallel "
            f"recipient addresses. Request transaction and identity records for linked counterpart accounts."
        )

    # Check for Zero-Gas Burners
    burner_nodes = [
        n.address for n in nodes
        if "zero_gas_burner" in n.typologyFlags
    ]
    if burner_nodes:
        recs.append(
            f"7. UNFUNDED TRANSIT ADDRESS: Address {burner_nodes[0]} operated without native gas balance, "
            f"relying on external fee sponsorship. Trace preceding funder address and downstream destinations."
        )

    # Check for DEX Swap
    dex_nodes = [
        n.address for n in nodes
        if "dex_swap" in n.typologyFlags
    ]
    if dex_nodes:
        recs.append(
            f"8. DECENTRALIZED EXCHANGE (DEX) INTERACTION: Address {dex_nodes[0]} interacted with a decentralized "
            f"exchange router. Query on-chain swap events to extract the swapped asset contract and destination address."
        )

    # ── 4. Court Admissibility Protocol ───────────────────────────────────────
    recs.append(
        "9. EVIDENCE VERIFICATION: Generate digital evidence verification hash (SHA-256) to maintain "
        "chain-of-custody integrity for case documentation."
    )

    return recs, sla_alert
