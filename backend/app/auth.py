from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any, cast

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.settings import Settings, get_settings
from app.supabase_rest import SupabaseRestClient, SupabaseRestError


@dataclass(frozen=True, slots=True)
class AuthenticatedTeacher:
    subject: str
    email: str
    display_name: str
    school_id: str | None = None
    roles: frozenset[str] = frozenset()
    access_token: str | None = None


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


def _record_list(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError("Supabase returned an invalid authorization response")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


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
        identity = authorize_google_identity(
            subject=subject,
            email=email,
            display_name=display_name,
            email_verified=True,
            settings=settings,
        )
        return AuthenticatedTeacher(
            subject=identity.subject,
            email=identity.email,
            display_name=identity.display_name,
            access_token=token,
        )
    except (PyJWTError, PermissionError, ValueError) as error:
        raise PermissionError("Supabase access token is invalid or unauthorized") from error


def load_governed_identity(
    identity: AuthenticatedTeacher,
    settings: Settings,
) -> AuthenticatedTeacher:
    """Require an active governed profile and load all concurrent application roles."""
    if identity.access_token is None:
        raise RuntimeError("Authenticated access token is unavailable")

    client = SupabaseRestClient.from_settings(settings, access_token=identity.access_token)
    try:
        profiles = _record_list(
            client.request(
                "GET",
                "profiles",
                params={
                    "id": f"eq.{identity.subject}",
                    "select": "id,email,display_name,school_id,is_active",
                    "limit": "1",
                },
            )
        )
        if not profiles or profiles[0].get("is_active") is not True:
            raise PermissionError("Authenticated account is not provisioned for this pilot")

        profile = profiles[0]
        school_id = profile.get("school_id")
        if not isinstance(school_id, str) or not school_id:
            raise PermissionError("Authenticated account is not assigned to a pilot school")

        role_records = _record_list(
            client.request(
                "GET",
                "profile_roles",
                params={
                    "profile_id": f"eq.{identity.subject}",
                    "school_id": f"eq.{school_id}",
                    "select": "role",
                },
            )
        )
        roles = frozenset(
            role
            for record in role_records
            if isinstance((role := record.get("role")), str) and role
        )
        if not roles:
            raise PermissionError("Authenticated account has no active pilot role")

        profile_email = profile.get("email")
        profile_name = profile.get("display_name")
        return AuthenticatedTeacher(
            subject=identity.subject,
            email=profile_email if isinstance(profile_email, str) else identity.email,
            display_name=profile_name if isinstance(profile_name, str) else identity.display_name,
            school_id=school_id,
            roles=roles,
            access_token=identity.access_token,
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise PermissionError("Authenticated account is not authorized for this pilot") from error
        raise RuntimeError("Pilot authorization service is unavailable") from error


def require_teacher(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedTeacher:
    """FastAPI dependency for authenticated, allowlisted, governed pilot users."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer access token is required")
    try:
        identity = verify_supabase_access_token(credentials.credentials, settings)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error

    try:
        return load_governed_identity(identity, settings)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
