from pathlib import Path

from app import scheduled_digest_worker as worker
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "backend" / "app" / "scheduled_digest_worker.py"
SCHEDULED_STACK = ROOT / "infra" / "scheduled-admin-digest-stack.yml"
MAIN_STACK = ROOT / "infra" / "pilot-stack.yml"


def test_scheduled_worker_service_client_builds_without_anon_key() -> None:
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key=None,
        supabase_service_role_key="service-role-placeholder",
    )

    client = worker._service_client(settings)

    assert client is not None


def test_scheduled_worker_uses_service_role_as_api_key_and_bearer_token() -> None:
    source = WORKER.read_text(encoding="utf-8")

    assert "service_key = settings.supabase_service_role_key" in source
    assert "SupabaseRestClient(" in source
    assert "api_key=service_key" in source
    assert "access_token=service_key" in source
    assert "SupabaseRestClient.from_settings" not in source


def test_scheduled_task_does_not_gain_anon_key_or_expand_web_task_privilege() -> None:
    scheduled = SCHEDULED_STACK.read_text(encoding="utf-8")
    main = MAIN_STACK.read_text(encoding="utf-8")

    assert "TPP_SUPABASE_SERVICE_ROLE_KEY" in scheduled
    assert "TPP_SUPABASE_URL" in scheduled
    assert "TPP_SUPABASE_ANON_KEY" not in scheduled
    assert "TPP_SUPABASE_SERVICE_ROLE_KEY" not in main
