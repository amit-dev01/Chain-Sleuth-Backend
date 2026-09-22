"""
routes_auth.py – Auth0 Identity & Officer Session Endpoints.

Provides:
GET /api/v1/auth/me    – Return profile, verified roles, and permissions of the current officer
GET /api/v1/auth/roles – Return the system RBAC role definitions
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import User, get_current_user

router = APIRouter(prefix="/auth", tags=["Auth0 Identity & RBAC"])


@router.get(
    "/me",
    response_model=dict[str, Any],
    summary="Get authenticated officer profile & roles",
    description=(
        "Decodes the Auth0 Bearer JWT and returns the officer's unique identity, "
        "assigned law enforcement roles, email, and permissions."
    ),
)
async def get_current_officer_profile(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """
    Returns the authenticated officer profile from the Auth0 JWT.
    """
    return {
        "status": "authenticated",
        "sub": user.sub,
        "email": user.email,
        "name": user.name or "Law Enforcement Officer",
        "roles": user.roles,
        "permissions": user.permissions,
        "is_admin": user.has_role("admin"),
        "is_investigator": user.has_role("investigator"),
    }


@router.get(
    "/roles",
    summary="List law enforcement RBAC role hierarchy",
    description="Returns available system roles and their investigative permission scopes.",
)
async def list_rbac_roles() -> dict[str, Any]:
    return {
        "roles": [
            {
                "role": "investigator",
                "title": "Cyber Crime Investigating Officer",
                "description": "Can initiate multi-chain graph traces, analyze wallet clusters, and generate FIR/BNSS legal dockets.",
                "permissions": ["trace:read", "trace:write", "notice:generate", "cases:read"],
            },
            {
                "role": "admin",
                "title": "Cyber Cell Administrator / Senior SP",
                "description": "Full access to custom VASP labels, continuous intelligence enrichment, and system configuration.",
                "permissions": ["*"],
            },
            {
                "role": "compliance_officer",
                "title": "VASP Nodal / Exchange Compliance Officer",
                "description": "Restricted access to receive Section 94 BNSS notices and provide KYC transaction responses.",
                "permissions": ["notice:read", "kyc:respond"],
            },
        ]
    }
