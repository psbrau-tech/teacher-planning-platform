from dataclasses import dataclass

from app.settings import Settings


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
