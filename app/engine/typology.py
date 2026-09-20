"""
typology.py – Crypto crime typology detector.

Identifies patterns such as:
  - Peel chains
  - Fan-out / fan-in mixing
  - Exchange hop structuring
  - Rapid layering
"""
from __future__ import annotations

from app.models.schemas import RiskLevel, TraceEdge, TraceNode


TYPOLOGY_RULES: dict[str, str] = {
    "peel_chain": "Single input → single output repeated ≥3 hops",
    "fan_out": "One source → multiple destinations in same block",
    "fan_in": "Multiple sources → one destination in same block",
    "layering": "≥5 consecutive hops within 10 minutes",
    "exchange_hop": "Passes through ≥2 known exchanges consecutively",
}


async def detect_typologies(
    nodes: list[TraceNode],
    edges: list[TraceEdge],
) -> dict[str, list[str]]:
    """
    Run all typology rules against the trace graph.

    Returns:
        A dict mapping typology name → list of suspect addresses.
    """
    # TODO: implement pattern matching logic
    raise NotImplementedError("Typology detection not yet implemented")


async def score_risk(
    nodes: list[TraceNode],
    typologies: dict[str, list[str]],
) -> dict[str, RiskLevel]:
    """
    Assign a RiskLevel to each address based on detected typologies.

    Returns:
        A dict mapping address → RiskLevel.
    """
    # TODO: implement scoring logic
    raise NotImplementedError("Risk scoring not yet implemented")
