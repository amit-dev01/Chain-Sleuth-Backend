"""
routes_notice.py – Endpoints for generating legal notices to VASPs / exchanges.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.models.schemas import NoticeCreate, NoticeResponse

router = APIRouter(prefix="/notices", tags=["Legal Notices"])


@router.post(
    "/",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a legal notice to a VASP / exchange",
)
async def generate_notice(payload: NoticeCreate) -> NoticeResponse:
    """
    Produce a legally formatted notice PDF addressed to an exchange,
    referencing suspect addresses and the applicable legal framework.
    """
    # TODO: wire up legal.pdf_generator + vasp.registry
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Notice generator not yet wired up")


@router.get(
    "/{notice_id}/download",
    summary="Download a generated legal notice PDF",
    response_class=FileResponse,
)
async def download_notice(notice_id: UUID) -> FileResponse:
    """Stream the PDF for a previously generated legal notice."""
    # TODO: fetch PDF path and stream
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
