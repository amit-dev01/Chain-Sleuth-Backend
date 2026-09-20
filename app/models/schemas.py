"""
schemas.py – Shared Pydantic models (request / response DTOs) for ChainSleuth.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class Chain(str, Enum):
    TRON = "tron"
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseStatus(str, Enum):
    OPEN = "open"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


# ── Trace ────────────────────────────────────────────────────────────────────

class TraceRequest(BaseModel):
    address: str = Field(..., description="Blockchain wallet address to trace")
    chain: Chain = Chain.TRON
    depth: int = Field(default=3, ge=1, le=10, description="Graph traversal depth")
    include_exchange: bool = True

    @field_validator("address")
    @classmethod
    def address_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("address must not be empty")
        return v.strip()


class TraceNode(BaseModel):
    address: str
    chain: Chain
    label: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    balance_usd: Optional[float] = None
    is_exchange: bool = False
    tags: list[str] = Field(default_factory=list)


class TraceEdge(BaseModel):
    from_address: str
    to_address: str
    tx_hash: str
    amount_usd: float
    timestamp: datetime
    chain: Chain


class TraceResponse(BaseModel):
    trace_id: UUID = Field(default_factory=uuid4)
    root_address: str
    chain: Chain
    depth: int
    nodes: list[TraceNode] = Field(default_factory=list)
    edges: list[TraceEdge] = Field(default_factory=list)
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Cases ────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    suspect_addresses: list[str] = Field(default_factory=list)
    chain: Chain = Chain.TRON
    assigned_officer: Optional[str] = None


class CaseResponse(BaseModel):
    case_id: UUID = Field(default_factory=uuid4)
    title: str
    description: Optional[str] = None
    status: CaseStatus = CaseStatus.OPEN
    suspect_addresses: list[str]
    chain: Chain
    assigned_officer: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── FIR ─────────────────────────────────────────────────────────────────────

class FIRCreate(BaseModel):
    case_id: UUID
    complainant_name: str
    complainant_designation: str
    incident_description: str
    suspect_addresses: list[str] = Field(default_factory=list)
    estimated_loss_inr: Optional[float] = None
    date_of_incident: datetime


class FIRResponse(BaseModel):
    fir_id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    fir_number: str
    complainant_name: str
    incident_description: str
    suspect_addresses: list[str]
    estimated_loss_inr: Optional[float] = None
    date_of_incident: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    pdf_url: Optional[str] = None


# ── Legal Notice ─────────────────────────────────────────────────────────────

class NoticeCreate(BaseModel):
    case_id: UUID
    recipient_exchange: str
    suspect_address: str
    chain: Chain
    legal_basis: str = Field(default="PMLA 2002 / IT Act 2000")
    requesting_authority: str


class NoticeResponse(BaseModel):
    notice_id: UUID = Field(default_factory=uuid4)
    case_id: UUID
    recipient_exchange: str
    suspect_address: str
    chain: Chain
    legal_basis: str
    requesting_authority: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    pdf_url: Optional[str] = None
