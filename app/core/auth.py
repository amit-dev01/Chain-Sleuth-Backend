"""
auth.py – Identity stub for ChainSleuth (Auth0 removed).

All requests are treated as an authenticated admin officer.
The User model and dependency interface are preserved so no other
file needs to change.
"""
from __future__ import annotations

import logging

from fastapi import Depends
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ── User Identity Model ────────────────────────────────────────────────────────

class User(BaseModel):
    """Authenticated user profile (auth-free mode)."""
    sub: str = Field(default="officer|chainsleuth_default")
    email: str | None = Field(default="investigating_officer@cybercrime.gov.in")
    name: str | None = Field(default="Nodal Cyber Crime Officer")
    roles: list[str] = Field(default_factory=lambda: ["admin", "investigator"])
    permissions: list[str] = Field(
        default_factory=lambda: [
            "trace:read", "trace:write",
            "notice:generate", "labels:manage",
            "cases:read", "cases:write",
        ]
    )
    is_authenticated: bool = Field(default=True)

    def has_role(self, role: str) -> bool:
        """Always returns True — auth is disabled."""
        return True


# ── Dependency: get_current_user ───────────────────────────────────────────────

async def get_current_user() -> User:
    """
    Returns a default authenticated officer.
    Auth0 has been removed — all requests are treated as admin.
    """
    return User()


# ── RBAC Role Guard (no-op) ───────────────────────────────────────────────────

def require_role(required_role: str):
    """
    No-op role guard. Auth0 removed — all officers pass all role checks.
    Interface preserved for compatibility with existing route decorators.
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        return user

    return role_checker
