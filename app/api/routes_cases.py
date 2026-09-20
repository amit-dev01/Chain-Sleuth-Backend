"""
routes_cases.py – CRUD endpoints for investigation cases.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import CaseCreate, CaseResponse

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "/",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new investigation case",
)
async def create_case(payload: CaseCreate) -> CaseResponse:
    """Create and persist a new ChainSleuth investigation case."""
    # TODO: persist to Neo4j / Postgres
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Retrieve a case by ID",
)
async def get_case(case_id: UUID) -> CaseResponse:
    """Fetch an existing case by its UUID."""
    # TODO: query DB
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get(
    "/",
    response_model=list[CaseResponse],
    summary="List all cases",
)
async def list_cases(skip: int = 0, limit: int = 20) -> list[CaseResponse]:
    """Return a paginated list of all investigation cases."""
    # TODO: paginated query
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a case",
)
async def delete_case(case_id: UUID) -> None:
    """Permanently remove a case and its associated data."""
    # TODO: delete from DB
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
