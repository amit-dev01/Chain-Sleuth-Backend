"""
auth.py – Supabase Auth JWT Verification Engine for ChainSleuth.

How Supabase Auth works:
  - Supabase issues HS256 JWTs signed with the project's JWT Secret.
  - The JWT Secret is found in: Supabase Dashboard → Settings → API → JWT Secret.
  - Every authenticated user request carries a Bearer token in the Authorization header.
  - This module verifies that token and extracts the user identity.

Configuration:
  - AUTH_ENABLED=True   → Enforce JWT verification (production)
  - AUTH_ENABLED=False  → Passthrough mode, return default officer (development)
  - SUPABASE_JWT_SECRET → Your project JWT secret from Supabase dashboard

Supabase JWT payload structure:
  {
    "sub":  "uuid-of-user",          # Supabase user UUID
    "email": "user@example.com",
    "role":  "authenticated",        # or "anon"
    "app_metadata": { "role": "admin" },  # custom roles set via Supabase
    "user_metadata": { "name": "..." },
    "aud":  "authenticated",
    "iat":  1234567890,
    "exp":  1234567890
  }
"""
from __future__ import annotations

import logging
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()

token_auth_scheme = HTTPBearer(auto_error=False)


# ── User Identity Model ────────────────────────────────────────────────────────

class User(BaseModel):
    """Authenticated user profile decoded from Supabase JWT."""
    sub: str = Field(..., description="Supabase user UUID")
    email: str | None = Field(default=None, description="User email address")
    name: str | None = Field(default=None, description="Display name")
    roles: list[str] = Field(
        default_factory=lambda: ["investigator"],
        description="Assigned RBAC roles",
    )
    permissions: list[str] = Field(default_factory=list)
    is_authenticated: bool = Field(default=True)

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role. Admins pass all checks."""
        return (
            role.lower() in [r.lower() for r in self.roles]
            or "admin" in [r.lower() for r in self.roles]
        )


# ── JWT Verification ───────────────────────────────────────────────────────────

def _verify_supabase_token(token: str) -> dict[str, Any]:
    """
    Verify a Supabase-issued HS256 JWT using the project JWT secret.
    Returns the decoded payload dict.
    Raises HTTPException on any failure.
    """
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "AUTH_ENABLED=True but SUPABASE_JWT_SECRET is not set in .env. "
                "Copy it from: Supabase Dashboard → Settings → API → JWT Secret."
            ),
        )

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",   # Supabase sets aud="authenticated" for logged-in users
            options={"verify_exp": True},
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Supabase session token has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidAudienceError:
        # Try without audience check — some custom JWTs may differ
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                options={"verify_exp": True, "verify_aud": False},
            )
            return payload
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Supabase token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Supabase token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _extract_user_from_payload(payload: dict[str, Any]) -> User:
    """Build a User object from the decoded Supabase JWT payload."""
    app_meta = payload.get("app_metadata") or {}
    user_meta = payload.get("user_metadata") or {}

    # Role resolution: check app_metadata.role → app_metadata.roles → default
    raw_role = app_meta.get("role") or app_meta.get("roles") or "investigator"
    if isinstance(raw_role, str):
        roles = [raw_role]
    elif isinstance(raw_role, list):
        roles = raw_role
    else:
        roles = ["investigator"]

    # Map Supabase "service_role" → "admin" for ChainSleuth RBAC
    roles = ["admin" if r == "service_role" else r for r in roles]

    email = payload.get("email") or user_meta.get("email")
    name  = user_meta.get("name") or user_meta.get("full_name") or email

    return User(
        sub=payload.get("sub", "supabase|anonymous"),
        email=email,
        name=name,
        roles=roles,
        permissions=app_meta.get("permissions", []),
        is_authenticated=True,
    )


# ── FastAPI Dependency ─────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(token_auth_scheme),
) -> User:
    """
    FastAPI dependency — verify Supabase Bearer token and return User.
    Falls back to dev officer when AUTH_ENABLED=False.
    """
    # Dev mode bypass
    if not settings.AUTH_ENABLED:
        return User(
            sub="supabase|officer_dev_mode",
            email="investigating_officer@cybercrime.gov.in",
            name="Nodal Cyber Crime Officer",
            roles=["admin", "investigator"],
            permissions=["trace:read", "trace:write", "notice:generate", "labels:manage"],
            is_authenticated=True,
        )

    # Require Bearer token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Provide: Authorization: Bearer <supabase_access_token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _verify_supabase_token(credentials.credentials)
    return _extract_user_from_payload(payload)


# ── RBAC Role Guard ────────────────────────────────────────────────────────────

def require_role(required_role: str):
    """
    Factory dependency to enforce specific roles.
    Usage:
        @router.post("/admin/labels", dependencies=[Depends(require_role("admin"))])
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: your account does not have the "
                    f"'{required_role}' role. Contact your system administrator."
                ),
            )
        return user

    return role_checker
