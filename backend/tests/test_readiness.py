from app.readiness import evaluate_runtime_readiness
from app.settings import Settings


def test_runtime_readiness_requires_core_pilot_configuration() -> None:
    readiness = evaluate_runtime_readiness(Settings())

    assert readiness.core_ready is False
    assert readiness.supabase_configured is False
    assert readiness.database_configured is False
    assert readiness.google_sso_configured is False
    assert readiness.pilot_access_configured is False


def test_runtime_readiness_accepts_complete_core_configuration() -> None:
    readiness = evaluate_runtime_readiness(
        Settings(
            environment="pilot",
            public_base_url="https://planner.guidedscholar.ai",
            supabase_url="https://example.supabase.co",
            supabase_anon_key="anon-secret",
            supabase_service_role_key="service-secret",
            database_url="postgresql://user:password@example:5432/postgres",
            google_oauth_client_id="client-id",
            google_oauth_client_secret="client-secret",
            openai_api_key="openai-secret",
            allowed_pilot_emails="teacher@example.org",
        )
    )

    assert readiness.core_ready is True
    assert readiness.openai_configured is True
    assert readiness.environment == "pilot"
    assert readiness.public_base_url == "https://planner.guidedscholar.ai/"


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
            allowed_pilot_emails="teacher@example.org",
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
