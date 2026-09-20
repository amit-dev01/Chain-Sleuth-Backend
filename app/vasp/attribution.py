"""
attribution.py – Address-to-entity attribution logic.

Combines VASP registry lookups, on-chain heuristics (co-spend clustering),
and optional Gemini AI enrichment to label wallet addresses.
"""
from __future__ import annotations

from app.models.schemas import TraceNode
from app.vasp.registry import lookup_vasp


async def attribute_node(node: TraceNode) -> TraceNode:
    """
    Enrich a TraceNode with entity label and risk metadata.

    Steps:
    1. Check VASP registry (known exchange / mixer addresses).
    2. Apply co-spend clustering heuristics.
    3. (Optional) Query Gemini AI for open-source intelligence.
    """
    vasp = lookup_vasp(node.address)
    if vasp:
        node.label = vasp.name
        node.is_exchange = True
        node.risk_level = vasp.risk_level  # type: ignore[assignment]
        node.tags = vasp.tags

    # TODO: co-spend clustering
    # TODO: Gemini AI enrichment
    return node


async def attribute_nodes(nodes: list[TraceNode]) -> list[TraceNode]:
    """Attribute a list of TraceNodes concurrently."""
    import asyncio
    return await asyncio.gather(*[attribute_node(n) for n in nodes])
