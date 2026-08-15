from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPERIENCE = ROOT / "frontend" / "src" / "AdminWeeklyDigestAction.tsx"
MAIN = ROOT / "frontend" / "src" / "main.tsx"


def test_admin_weekly_digest_action_is_not_mounted_in_normal_ui() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert 'import { AdminWeeklyDigestAction }' not in source
    assert "<AdminWeeklyDigestAction />" not in source
    assert 'import { FridayStatusExperience }' in source
    assert "<FridayStatusExperience />" in source


def test_admin_digest_recovery_client_never_supplies_a_recipient() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8")

    assert "/api/v1/notifications/admin-weekly-digest/" in source
    assert 'method: "POST"' in source
    assert "recipient_email" not in source
    assert "ToAddresses" not in source
    assert "requesting-admin" in source
    assert "authenticated TPP account email" in source


def test_admin_digest_recovery_ui_explains_content_minimization() -> None:
    source = EXPERIENCE.read_text(encoding="utf-8").lower()

    assert "school-level submission counts" in source
    assert "does not include teacher names" in source
    assert "reflection text" in source
    assert "generated instructional insight" in source
    assert "student data" in source
    assert "teacher-quality scores" in source
