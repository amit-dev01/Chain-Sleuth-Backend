"""
routes_fir.py – Endpoints for generating First Information Reports (FIR).
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.models.schemas import FIRCreate, FIRResponse

router = APIRouter(prefix="/fir", tags=["FIR"])


@router.post(
    "/",
    response_model=FIRResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a blockchain FIR document",
)
async def generate_fir(payload: FIRCreate) -> FIRResponse:
    """
    Produce a legally formatted FIR PDF for a given case,
    embedding transaction trails and risk evidence.
    """
    # TODO: wire up legal.pdf_generator
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="PDF generator not yet wired up")


@router.get(
    "/{fir_id}/download",
    summary="Download a generated FIR PDF",
    response_class=FileResponse,
)
async def download_fir(fir_id: UUID) -> FileResponse:
    """Stream the PDF file for a previously generated FIR."""
    # TODO: fetch PDF path and stream
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
