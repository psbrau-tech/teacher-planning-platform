from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.settings import Settings, get_settings


@dataclass(frozen=True, slots=True)
class AuthenticatedTeacher:
    subject: str
    email: str
    display_name: str


def authorize_google_identity(
    *,
    subject: str,
    email: str,
    display_name: str,
    email_verified: bool,
    settings: Settings,
) -> AuthenticatedTeacher:
    """Apply the controlled-pilot allowlist to a verified Google identity."""
    normalized_email = email.strip().lower()
    if not email_verified:
        raise PermissionError("Google account email must be verified")
    if not settings.email_is_allowed(normalized_email):
        raise PermissionError("Google account is not authorized for this pilot")
    return AuthenticatedTeacher(
        subject=subject.strip(),
        email=normalized_email,
        display_name=display_name.strip() or normalized_email,
    )


_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def _claim_text(claims: dict[str, Any], key: str) -> str:
    value = claims.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PermissionError(f"Authenticated identity is missing {key}")
    return value.strip()


def verify_supabase_access_token(token: str, settings: Settings) -> AuthenticatedTeacher:
    """Verify a Supabase access token and apply the controlled-pilot allowlist."""
    if settings.supabase_url is None:
        raise RuntimeError("Supabase authentication is not configured")

    base_url = str(settings.supabase_url).rstrip("/")
    issuer = f"{base_url}/auth/v1"
    jwks_url = f"{issuer}/.well-known/jwks.json"

    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            issuer=issuer,
        )
        subject = _claim_text(claims, "sub")
        email = _claim_text(claims, "email")
        user_metadata = claims.get("user_metadata")
        display_name = email
        if isinstance(user_metadata, dict):
            candidate = user_metadata.get("full_name") or user_metadata.get("name")
            if isinstance(candidate, str) and candidate.strip():
                display_name = candidate.strip()
        return authorize_google_identity(
            subject=subject,
            email=email,
            display_name=display_name,
            email_verified=True,
            settings=settings,
        )
    except (PyJWTError, PermissionError, ValueError) as error:
        raise PermissionError("Supabase access token is invalid or unauthorized") from error


def require_teacher(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedTeacher:
    """FastAPI dependency for authenticated, allowlisted pilot teachers."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer access token is required")
    try:
        return verify_supabase_access_token(credentials.credentials, settings)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
