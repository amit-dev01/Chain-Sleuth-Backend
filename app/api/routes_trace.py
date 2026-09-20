"""
routes_trace.py – Endpoints for blockchain address tracing.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import TraceRequest, TraceResponse

router = APIRouter(prefix="/trace", tags=["Trace"])


@router.post(
    "/",
    response_model=TraceResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate a blockchain address trace",
)
async def trace_address(payload: TraceRequest) -> TraceResponse:
    """
    Kick off an async graph traversal from *address* up to *depth* hops.
    Returns a trace graph with risk scores for each node.
    """
    # TODO: wire up engine.tron_tracer / engine.traversal
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Tracer engine not yet wired up")


@router.get(
    "/{trace_id}",
    response_model=TraceResponse,
    summary="Fetch a previously run trace by ID",
)
async def get_trace(trace_id: UUID) -> TraceResponse:
    """Retrieve a cached trace result from Redis / Neo4j."""
    # TODO: fetch from cache / graph DB
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
