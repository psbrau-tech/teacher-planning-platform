from datetime import date
from pathlib import Path

import pytest

from app.notification_email import (
    SesDeliveryError,
    WeeklyAdminDigestMetrics,
    send_weekly_admin_digest,
    weekly_admin_digest_text,
)
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "backend" / "app" / "notifications_api.py"
MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260814231500_notification_delivery_events.sql"
)


def metrics() -> WeeklyAdminDigestMetrics:
    return WeeklyAdminDigestMetrics(
        week_start=date(2026, 8, 10),
        configured_assignments=20,
        lesson_plans_submitted=18,
        lesson_plans_missing=2,
        completed_packets_submitted=16,
        completed_packets_missing=4,
        teachers_with_completed_packets=8,
    )


def test_weekly_digest_contains_counts_and_authenticated_link_only() -> None:
    text = weekly_admin_digest_text(metrics(), public_base_url="https://planner.guidedscholar.ai")

    assert "Lesson plans submitted: 18" in text
    assert "Lesson plans missing: 2" in text
    assert "Completed Friday packets missing: 4" in text
    assert "school PLC reflection brief can be generated" in text
    assert "https://planner.guidedscholar.ai" in text
    assert "teacher reflection text" in text
    assert "teacher-quality score" in text

    forbidden = (
        "teacher name:",
        "teacher email:",
        "reflection response:",
        "student name:",
    )
    lowered = text.lower()
    for phrase in forbidden:
        assert phrase not in lowered


def test_ses_delivery_is_fail_closed_until_sender_is_configured() -> None:
    settings = Settings(
        ses_from_email="",
        allowed_email_domains="anniston.k12.al.us",
    )
    with pytest.raises(SesDeliveryError, match="not configured"):
        send_weekly_admin_digest(
            settings,
            recipient_email="principal@anniston.k12.al.us",
            metrics=metrics(),
        )


def test_ses_delivery_rejects_recipient_outside_governed_account_boundary() -> None:
    settings = Settings(
        ses_from_email="notifications@example.org",
        allowed_email_domains="anniston.k12.al.us",
    )
    with pytest.raises(SesDeliveryError, match="outside the governed"):
        send_weekly_admin_digest(
            settings,
            recipient_email="outside@example.org",
            metrics=metrics(),
        )


def test_notification_api_sends_only_to_requesting_admin_account() -> None:
    source = API.read_text(encoding="utf-8")

    assert "recipient_email=identity.email" in source
    assert 'recipient_scope: str = "requesting-admin"' in source
    assert "admin_weekly_submission_status_v2" in source
    assert "teacher_name" not in source
    assert "reflection_text" not in source
    assert "completed_packet_revision" in source
    assert "lesson_plan_revision" in source


def test_notification_delivery_telemetry_is_content_free() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()

    assert "notification_delivery_events" in source
    assert "admin_weekly_digest_sent" in source
    assert "recipient address is stored" in source
    assert "email body" in source
    assert "reflection text" in source
    assert "student data" in source
    assert "recipient_email" not in source
    assert "message_id" not in source
