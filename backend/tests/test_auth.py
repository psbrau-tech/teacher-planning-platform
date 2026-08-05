import pytest

from app.auth import authorize_google_identity
from app.settings import Settings


def test_verified_allowlisted_google_identity_is_authorized() -> None:
    teacher = authorize_google_identity(
        subject="google-subject-1",
        email="Teacher@AnnistonSchools.org",
        display_name="Pilot Teacher",
        email_verified=True,
        settings=Settings(allowed_pilot_emails="teacher@annistonschools.org"),
    )

    assert teacher.email == "teacher@annistonschools.org"
    assert teacher.display_name == "Pilot Teacher"


def test_allowed_school_domain_can_be_enabled() -> None:
    teacher = authorize_google_identity(
        subject="google-subject-2",
        email="teacher@annistonschools.org",
        display_name="Teacher",
        email_verified=True,
        settings=Settings(allowed_email_domains="annistonschools.org"),
    )

    assert teacher.subject == "google-subject-2"


def test_unverified_or_unapproved_google_identity_is_rejected() -> None:
    settings = Settings(allowed_pilot_emails="teacher@annistonschools.org")

    with pytest.raises(PermissionError, match="verified"):
        authorize_google_identity(
            subject="subject",
            email="teacher@annistonschools.org",
            display_name="Teacher",
            email_verified=False,
            settings=settings,
        )

    with pytest.raises(PermissionError, match="not authorized"):
        authorize_google_identity(
            subject="subject",
            email="other@example.com",
            display_name="Other",
            email_verified=True,
            settings=settings,
        )
