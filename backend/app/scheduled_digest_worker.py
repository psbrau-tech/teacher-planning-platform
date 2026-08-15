from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .notification_email import (
    SesDeliveryError,
    WeeklyAdminDigestMetrics,
    send_weekly_admin_digest,
)
from .settings import Settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError


class ScheduledDigestWorkerError(RuntimeError):
    """Bounded scheduled-digest failure that never exposes credentials or email content."""


def _service_client(settings: Settings) -> SupabaseRestClient:
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        raise ScheduledDigestWorkerError("Scheduled digest database access is not configured")
    service_key = settings.supabase_service_role_key
    return SupabaseRestClient(
        base_url=str(settings.supabase_url).rstrip("/"),
        api_key=service_key,
        access_token=service_key,
    )


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ScheduledDigestWorkerError("Scheduled digest candidate data is invalid")
    return [cast(dict[str, Any], row) for row in payload if isinstance(row, dict)]


def week_start_for_timezone(timezone_name: str, now: datetime | None = None) -> date:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ScheduledDigestWorkerError("Scheduled digest timezone is invalid") from error
    current = now.astimezone(timezone) if now is not None else datetime.now(timezone)
    return current.date() - timedelta(days=current.weekday())


def _positive_int(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScheduledDigestWorkerError("Scheduled digest metrics are invalid")
    return value


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScheduledDigestWorkerError("Scheduled digest candidate data is invalid")
    return value.strip()


def _claim_candidates(
    client: SupabaseRestClient,
    *,
    week_start: date,
) -> list[dict[str, Any]]:
    try:
        payload = client.request(
            "POST",
            "rpc/claim_scheduled_admin_weekly_digest_candidates",
            payload={"target_week_start": week_start.isoformat()},
        )
    except SupabaseRestError as error:
        raise ScheduledDigestWorkerError("Scheduled digest candidates are unavailable") from error
    return _records(payload)


def _complete_delivery(
    client: SupabaseRestClient,
    *,
    delivery_id: str,
    success: bool,
) -> None:
    try:
        client.request(
            "POST",
            "rpc/complete_scheduled_admin_weekly_digest_delivery",
            payload={
                "target_delivery_id": delivery_id,
                "target_success": success,
            },
        )
    except SupabaseRestError as error:
        raise ScheduledDigestWorkerError(
            "Scheduled digest delivery status could not be recorded"
        ) from error


def _metrics(row: dict[str, Any], *, week_start: date) -> WeeklyAdminDigestMetrics:
    return WeeklyAdminDigestMetrics(
        week_start=week_start,
        configured_assignments=_positive_int(row, "configured_assignments"),
        lesson_plans_submitted=_positive_int(row, "lesson_plans_submitted"),
        lesson_plans_missing=_positive_int(row, "lesson_plans_missing"),
        completed_packets_submitted=_positive_int(row, "completed_packets_submitted"),
        completed_packets_missing=_positive_int(row, "completed_packets_missing"),
        teachers_with_completed_packets=_positive_int(
            row,
            "teachers_with_completed_packets",
        ),
    )


def run_scheduled_admin_digest(settings: Settings | None = None) -> dict[str, int | str]:
    """Claim and deliver one current-week digest per eligible school administrator.

    The service-role credential is used only by this isolated worker to claim a content-minimized
    recipient manifest. Claims are written before sending, so an automatic task retry will not
    duplicate a message after a partial worker failure. A failed claim can still be handled through
    the existing authenticated manual-send path.
    """
    effective_settings = settings or Settings()
    if effective_settings.ses_from_email != effective_settings.approved_ses_from_email:
        raise ScheduledDigestWorkerError("Scheduled digest sender is not the approved TPP address")

    week_start = week_start_for_timezone(effective_settings.scheduled_digest_timezone)
    client = _service_client(effective_settings)
    candidates = _claim_candidates(client, week_start=week_start)

    sent = 0
    failed = 0
    for row in candidates:
        delivery_id = _required_text(row, "delivery_id")
        recipient = _required_text(row, "recipient_email").lower()
        if not effective_settings.email_is_allowed(recipient):
            _complete_delivery(client, delivery_id=delivery_id, success=False)
            failed += 1
            continue

        try:
            send_weekly_admin_digest(
                effective_settings,
                recipient_email=recipient,
                metrics=_metrics(row, week_start=week_start),
            )
        except (SesDeliveryError, ScheduledDigestWorkerError):
            _complete_delivery(client, delivery_id=delivery_id, success=False)
            failed += 1
            continue

        _complete_delivery(client, delivery_id=delivery_id, success=True)
        sent += 1

    # Do not print recipient addresses, school identifiers, message bodies, or provider IDs.
    print(
        "scheduled_admin_digest_complete",
        f"week_start={week_start.isoformat()}",
        f"claimed={len(candidates)}",
        f"sent={sent}",
        f"failed={failed}",
    )
    return {
        "week_start": week_start.isoformat(),
        "claimed": len(candidates),
        "sent": sent,
        "failed": failed,
    }


def main() -> int:
    try:
        result = run_scheduled_admin_digest()
    except ScheduledDigestWorkerError as error:
        print("scheduled_admin_digest_failed", str(error))
        return 1
    return 0 if result["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
