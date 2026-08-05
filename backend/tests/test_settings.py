from app.settings import Settings


def test_domain_allowlist_is_normalized() -> None:
    settings = Settings(
        allowed_email_domains="anniston.k12.al.us, Example.org ",
        allowed_pilot_emails="Pilot.Teacher@Other.org",
    )

    assert settings.email_is_allowed("teacher@anniston.k12.al.us") is True
    assert settings.email_is_allowed("USER@example.org") is True
    assert settings.email_is_allowed("pilot.teacher@other.org") is True
    assert settings.email_is_allowed("unknown@other.org") is False


def test_non_email_value_is_rejected() -> None:
    settings = Settings(allowed_email_domains="anniston.k12.al.us")
    assert settings.email_is_allowed("not-an-email") is False


def test_sensitive_settings_are_not_exposed_in_repr() -> None:
    settings = Settings(
        supabase_service_role_key="service-secret",
        openai_api_key="openai-secret",
        google_oauth_client_secret="google-secret",
    )
    rendered = repr(settings)
    assert "service-secret" not in rendered
    assert "openai-secret" not in rendered
    assert "google-secret" not in rendered
