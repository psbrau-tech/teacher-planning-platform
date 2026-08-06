from app.readiness import evaluate_runtime_readiness
from app.settings import Settings


def test_runtime_readiness_requires_core_pilot_configuration() -> None:
    readiness = evaluate_runtime_readiness(Settings())

    assert readiness.core_ready is False
    assert readiness.supabase_configured is False
    assert readiness.pilot_access_configured is False
    assert readiness.privileged_runtime_credentials_absent is True


def test_runtime_readiness_accepts_minimal_runtime_configuration() -> None:
    readiness = evaluate_runtime_readiness(
        Settings(
            environment="pilot",
            public_base_url="https://planner.guidedscholar.ai",
            supabase_url="https://example.supabase.co",
            supabase_anon_key="anon-secret",
            allowed_email_domains="anniston.k12.al.us",
        )
    )

    assert readiness.core_ready is True
    assert readiness.supabase_configured is True
    assert readiness.pilot_access_configured is True
    assert readiness.privileged_runtime_credentials_absent is True
    assert readiness.environment == "pilot"
    assert readiness.public_base_url == "https://planner.guidedscholar.ai/"


def test_runtime_readiness_rejects_unused_privileged_credentials() -> None:
    readiness = evaluate_runtime_readiness(
        Settings(
            supabase_url="https://example.supabase.co",
            supabase_anon_key="anon-secret",
            supabase_service_role_key="service-secret",
            database_url="postgresql://secret",
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            openai_api_key="openai-secret",
            allowed_email_domains="anniston.k12.al.us",
        )
    )

    assert readiness.core_ready is False
    assert readiness.privileged_runtime_credentials_absent is False


def test_runtime_readiness_does_not_contain_secret_values() -> None:
    readiness = evaluate_runtime_readiness(
        Settings(
            supabase_url="https://example.supabase.co",
            supabase_anon_key="anon-secret",
            supabase_service_role_key="service-secret",
            database_url="postgresql://secret",
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            openai_api_key="openai-secret",
            allowed_email_domains="anniston.k12.al.us",
        )
    )

    rendered = repr(readiness)
    for secret in (
        "anon-secret",
        "service-secret",
        "postgresql://secret",
        "client-secret",
        "openai-secret",
    ):
        assert secret not in rendered
