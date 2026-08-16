from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.notification_email import (
    SesDeliveryError,
    WeeklyAdminDigestMetrics,
    send_weekly_admin_digest,
    weekly_admin_digest_text,
)
from app.settings import (
    APPROVED_SES_FROM_EMAIL,
    APPROVED_SES_REPLY_TO_EMAIL,
    Settings,
)

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "backend" / "app" / "notifications_api.py"
MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260814231500_notification_delivery_events.sql"
)
DECISION = ROOT / "docs" / "governance" / "ADMIN_EMAIL_NOTIFICATION_DECISION_2026-08-14.md"


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


def test_ses_delivery_rejects_unapproved_sender_identity() -> None:
    settings = Settings(
        ses_from_email="another-sender@planner.guidedscholar.ai",
        allowed_email_domains="anniston.k12.al.us",
    )
    with pytest.raises(SesDeliveryError, match="approved TPP sender"):
        send_weekly_admin_digest(
            settings,
            recipient_email="principal@anniston.k12.al.us",
            metrics=metrics(),
        )


def test_ses_delivery_rejects_unapproved_reply_to_mailbox() -> None:
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        ses_reply_to_email="someone-else@example.org",
        allowed_email_domains="anniston.k12.al.us",
    )
    with pytest.raises(SesDeliveryError, match="approved TPP mailbox"):
        send_weekly_admin_digest(
            settings,
            recipient_email="principal@anniston.k12.al.us",
            metrics=metrics(),
        )


def test_ses_delivery_uses_exact_governed_from_and_reply_to(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    class FakeSesClient:
        def send_email(self, **kwargs: Any) -> dict[str, str]:
            sent.update(kwargs)
            return {"MessageId": "bounded-provider-id"}

    def fake_client(service_name: str, *, region_name: str) -> FakeSesClient:
        assert service_name == "sesv2"
        assert region_name == "us-east-2"
        return FakeSesClient()

    monkeypatch.setattr("app.notification_email.boto3.client", fake_client)
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        allowed_email_domains="anniston.k12.al.us",
    )

    message_id = send_weekly_admin_digest(
        settings,
        recipient_email="principal@anniston.k12.al.us",
        metrics=metrics(),
    )

    assert message_id == "bounded-provider-id"
    assert sent["FromEmailAddress"] == APPROVED_SES_FROM_EMAIL
    assert sent["ReplyToAddresses"] == [APPROVED_SES_REPLY_TO_EMAIL]
    assert sent["Destination"] == {"ToAddresses": ["principal@anniston.k12.al.us"]}


def test_ses_delivery_rejects_recipient_outside_governed_account_boundary() -> None:
    settings = Settings(
        ses_from_email=APPROVED_SES_FROM_EMAIL,
        allowed_email_domains="anniston.k12.al.us",
    )
    with pytest.raises(SesDeliveryError, match="outside the governed"):
        send_weekly_admin_digest(
            settings,
            recipient_email="outside@example.org",
            metrics=metrics(),
        )


def test_approved_sender_is_recorded_but_runtime_remains_fail_closed() -> None:
    source = DECISION.read_text(encoding="utf-8")
    assert APPROVED_SES_FROM_EMAIL == "notifications@planner.guidedscholar.ai"
    assert "`notifications@planner.guidedscholar.ai`" in source
    assert "Recording this address does not activate email delivery" in source


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
