"""
chain_router.py – Dispatcher that selects the correct chain-specific tracer.
"""
from __future__ import annotations

from app.models.schemas import Chain, TraceRequest, TraceResponse


async def route_trace(request: TraceRequest) -> TraceResponse:
    """
    Route a TraceRequest to the correct blockchain engine.

    Supported chains:
      - tron  → engine.tron_tracer
      - ethereum / bsc / polygon → (future adapters)
    """
    match request.chain:
        case Chain.TRON:
            from app.engine.tron_tracer import fetch_transactions  # noqa: F401
            # TODO: call tron_tracer + traversal + typology
            raise NotImplementedError("TRON routing not yet fully implemented")
        case _:
            raise NotImplementedError(f"Chain '{request.chain}' is not yet supported")
