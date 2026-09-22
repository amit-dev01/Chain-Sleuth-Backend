"""
auth.py – Auth0 Identity Management & JWT Token Verification Engine.

Provides:
1. Asymmetric RS256 JWT signature verification using Auth0 JWKS public keys.
2. Law Enforcement Role-Based Access Control (RBAC):
   - "investigator": Can run traces, view cases, and generate FIR/Section 94 dockets.
   - "admin": Can manage custom VASP labels, batch enrichments, and user roles.
   - "compliance_officer": Can view assigned VASP notices and provide KYC responses.
3. Development bypass mode (AUTH_ENABLED=False) to ensure zero friction during local testing.
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


# ── User Identity & Claims Model ──────────────────────────────────────────────

class User(BaseModel):
    """Authenticated user profile decoded from Auth0 JWT."""
    sub: str = Field(..., description="Auth0 unique subject / user identifier")
    email: str | None = Field(default=None, description="Officer / user email address")
    name: str | None = Field(default=None, description="Display name / designation")
    roles: list[str] = Field(default_factory=lambda: ["investigator"], description="Assigned RBAC roles")
    permissions: list[str] = Field(default_factory=list, description="Scopes and fine-grained permissions")
    is_authenticated: bool = Field(default=True, description="Authentication status")

    def has_role(self, role: str) -> bool:
        """Check if user possesses a specific role."""
        return role.lower() in [r.lower() for r in self.roles] or "admin" in [r.lower() for r in self.roles]


# ── JWKS Client (Lazy-loaded singleton) ───────────────────────────────────────

_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient | None:
    """Return cached PyJWKClient instance for Auth0 JWKS key rotation."""
    global _jwks_client
    if _jwks_client is None and settings.AUTH0_DOMAIN:
        domain = settings.AUTH0_DOMAIN.strip().rstrip("/")
        jwks_url = f"https://{domain}/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=86400)
        log.info("Auth0 JWKS Client initialised for domain: %s", domain)
    return _jwks_client


# ── Dependency: Verify & Decode Current User ─────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(token_auth_scheme),
) -> User:
    """
    FastAPI security dependency to authenticate incoming requests via Auth0 Bearer token.
    Gracefully allows development mode when AUTH_ENABLED=False.
    """
    # 1. Dev Mode Bypass
    if not settings.AUTH_ENABLED:
        return User(
            sub="auth0|officer_dev_mode",
            email="investigating_officer@cybercrime.gov.in",
            name="Nodal Cyber Crime Officer",
            roles=["admin", "investigator"],
            permissions=["trace:read", "trace:write", "notice:generate", "labels:manage"],
            is_authenticated=True,
        )

    # 2. Require Bearer Token
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header with Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    jwks_client = _get_jwks_client()
    if not jwks_client or not settings.AUTH0_DOMAIN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth0 is enabled but AUTH0_DOMAIN is not configured in backend .env.",
        )

    domain = settings.AUTH0_DOMAIN.strip().rstrip("/")
    issuer = settings.AUTH0_ISSUER or f"https://{domain}/"
    audience = settings.AUTH0_AUDIENCE or None

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decode_kwargs: dict[str, Any] = {
            "jwt": token,
            "key": signing_key.key,
            "algorithms": ["RS256"],
            "issuer": issuer,
        }
        if audience:
            decode_kwargs["audience"] = audience

        payload: dict[str, Any] = jwt.decode(**decode_kwargs)

        # Extract roles from standard Auth0 namespace or default claims
        ns_roles = (
            payload.get("https://chainsleuth.in/roles")
            or payload.get("https://chainsleuth.com/roles")
            or payload.get("roles")
            or ["investigator"]
        )
        if isinstance(ns_roles, str):
            ns_roles = [ns_roles]

        email = (
            payload.get("https://chainsleuth.in/email")
            or payload.get("email")
            or payload.get("sub")
        )
        name = payload.get("name") or payload.get("nickname")

        return User(
            sub=payload.get("sub", "auth0|anonymous"),
            email=email,
            name=name,
            roles=ns_roles,
            permissions=payload.get("permissions", []),
            is_authenticated=True,
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth0 access token has expired. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Auth0 token signature or claims: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── RBAC Role Guard Generator ─────────────────────────────────────────────────

def require_role(required_role: str):
    """
    Factory dependency to enforce specific law enforcement roles.
    Usage:
        @router.post("/labels", dependencies=[Depends(require_role("admin"))])
    """
    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if not user.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: User does not have the required '{required_role}' law enforcement role.",
            )
        return user

    return role_checker
