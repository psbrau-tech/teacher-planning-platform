from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .notification_email import (
    FridayAdminDigestMetrics,
    FridayTeacherReminderItem,
    SesDeliveryError,
    send_friday_admin_digest,
    send_teacher_friday_reminder,
)
from .settings import APPROVED_SES_FROM_EMAIL, Settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError


class ScheduledDigestWorkerError(RuntimeError):
    """Bounded Friday-notification failure that never exposes credentials or email content."""


@dataclass(frozen=True, slots=True)
class SchoolDispatchWindow:
    school_id: str
    timezone: str
    week_start: date


def _service_client(settings: Settings) -> SupabaseRestClient:
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        raise ScheduledDigestWorkerError(
            "Scheduled notification database access is not configured"
        )
    service_key = settings.supabase_service_role_key
    return SupabaseRestClient(
        base_url=str(settings.supabase_url).rstrip("/"),
        api_key=service_key,
        access_token=service_key,
    )


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ScheduledDigestWorkerError("Scheduled notification candidate data is invalid")
    return [cast(dict[str, Any], row) for row in payload if isinstance(row, dict)]


def week_start_for_timezone(timezone_name: str, now: datetime | None = None) -> date:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ScheduledDigestWorkerError("Scheduled notification timezone is invalid") from error
    current = now.astimezone(timezone) if now is not None else datetime.now(timezone)
    return current.date() - timedelta(days=current.weekday())


def _positive_int(row: dict[str, Any], key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ScheduledDigestWorkerError("Scheduled notification metrics are invalid")
    return value


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ScheduledDigestWorkerError("Scheduled notification candidate data is invalid")
    return value.strip()


def _required_uuid(row: dict[str, Any], key: str) -> str:
    value = _required_text(row, key)
    try:
        return str(UUID(value))
    except ValueError as error:
        raise ScheduledDigestWorkerError(
            "Scheduled notification candidate data is invalid"
        ) from error


def _required_date(row: dict[str, Any], key: str) -> date:
    value = _required_text(row, key)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ScheduledDigestWorkerError(
            "Scheduled notification candidate data is invalid"
        ) from error


def _dispatch_windows(
    client: SupabaseRestClient,
    *,
    mode: str,
    now: datetime,
) -> tuple[SchoolDispatchWindow, ...]:
    if now.tzinfo is None:
        raise ScheduledDigestWorkerError("Scheduled notification clock must be timezone-aware")
    try:
        payload = client.request(
            "POST",
            "rpc/scheduled_notification_school_windows",
            payload={"target_mode": mode, "target_now": now.isoformat()},
        )
    except SupabaseRestError as error:
        raise ScheduledDigestWorkerError(
            "Scheduled notification school windows are unavailable"
        ) from error

    windows: list[SchoolDispatchWindow] = []
    for row in _records(payload):
        school_id = _required_uuid(row, "school_id")
        timezone_name = _required_text(row, "timezone")
        week_start = _required_date(row, "week_start")
        if week_start != week_start_for_timezone(timezone_name, now):
            raise ScheduledDigestWorkerError(
                "Scheduled notification school window is inconsistent"
            )
        windows.append(
            SchoolDispatchWindow(
                school_id=school_id,
                timezone=timezone_name,
                week_start=week_start,
            )
        )
    return tuple(windows)


def _claim(
    client: SupabaseRestClient,
    *,
    rpc: str,
    school_id: str,
    week_start: date,
) -> list[dict[str, Any]]:
    try:
        payload = client.request(
            "POST",
            f"rpc/{rpc}",
            payload={
                "target_school_id": school_id,
                "target_week_start": week_start.isoformat(),
            },
        )
    except SupabaseRestError as error:
        raise ScheduledDigestWorkerError(
            "Scheduled notification candidates are unavailable"
        ) from error
    rows = _records(payload)
    for row in rows:
        if _required_uuid(row, "school_id") != school_id:
            raise ScheduledDigestWorkerError(
                "Scheduled notification candidate escaped its school scope"
            )
    return rows


def _claim_admin_candidates(
    client: SupabaseRestClient,
    *,
    school_id: str,
    week_start: date,
) -> list[dict[str, Any]]:
    return _claim(
        client,
        rpc="claim_scheduled_admin_weekly_digest_candidates",
        school_id=school_id,
        week_start=week_start,
    )


def _claim_teacher_candidates(
    client: SupabaseRestClient,
    *,
    school_id: str,
    week_start: date,
) -> list[dict[str, Any]]:
    return _claim(
        client,
        rpc="claim_teacher_friday_reminder_candidates",
        school_id=school_id,
        week_start=week_start,
    )


def _complete_delivery(
    client: SupabaseRestClient,
    *,
    delivery_id: str,
    success: bool,
) -> None:
    try:
        client.request(
            "POST",
            "rpc/complete_scheduled_notification_delivery",
            payload={
                "target_delivery_id": delivery_id,
                "target_success": success,
            },
        )
    except SupabaseRestError as error:
        raise ScheduledDigestWorkerError(
            "Scheduled notification delivery status could not be recorded"
        ) from error


def _admin_metrics(
    row: dict[str, Any],
    *,
    week_start: date,
) -> FridayAdminDigestMetrics:
    return FridayAdminDigestMetrics(
        week_start=week_start,
        next_week_start=week_start + timedelta(days=7),
        current_teachers_expected=_positive_int(row, "current_teachers_expected"),
        current_teachers_complete=_positive_int(row, "current_teachers_complete"),
        current_packets_expected=_positive_int(row, "current_packets_expected"),
        current_packets_submitted=_positive_int(row, "current_packets_submitted"),
        next_teachers_expected=_positive_int(row, "next_teachers_expected"),
        next_teachers_complete=_positive_int(row, "next_teachers_complete"),
        next_plans_expected=_positive_int(row, "next_plans_expected"),
        next_plans_submitted=_positive_int(row, "next_plans_submitted"),
        teachers_with_completed_packets=_positive_int(
            row,
            "teachers_with_completed_packets",
        ),
    )


def _teacher_items(row: dict[str, Any]) -> tuple[FridayTeacherReminderItem, ...]:
    raw_items = row.get("outstanding_items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ScheduledDigestWorkerError(
            "Teacher reminder has invalid outstanding-item data"
        )
    items: list[FridayTeacherReminderItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ScheduledDigestWorkerError(
                "Teacher reminder has invalid outstanding-item data"
            )
        course_name = raw.get("course_name")
        current_missing = raw.get("missing_current_closeout")
        next_missing = raw.get("missing_next_plan")
        if (
            not isinstance(course_name, str)
            or not course_name.strip()
            or not isinstance(current_missing, bool)
            or not isinstance(next_missing, bool)
            or not (current_missing or next_missing)
        ):
            raise ScheduledDigestWorkerError(
                "Teacher reminder has invalid outstanding-item data"
            )
        items.append(
            FridayTeacherReminderItem(
                course_name=course_name.strip(),
                missing_current_closeout=current_missing,
                missing_next_plan=next_missing,
            )
        )
    return tuple(items)


def _assert_approved_sender(settings: Settings) -> None:
    if settings.ses_from_email.strip().lower() != APPROVED_SES_FROM_EMAIL:
        raise ScheduledDigestWorkerError(
            "Scheduled notification sender is not the approved TPP address"
        )


def run_teacher_friday_reminders(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Send school-local class-specific reminders only for explicitly enabled schools."""
    effective_settings = settings or Settings()
    _assert_approved_sender(effective_settings)
    dispatch_now = now or datetime.now(UTC)
    client = _service_client(effective_settings)
    windows = _dispatch_windows(client, mode="teacher", now=dispatch_now)

    claimed = 0
    sent = 0
    failed = 0
    for window in windows:
        candidates = _claim_teacher_candidates(
            client,
            school_id=window.school_id,
            week_start=window.week_start,
        )
        claimed += len(candidates)
        for row in candidates:
            delivery_id = _required_text(row, "delivery_id")
            recipient = _required_text(row, "recipient_email").lower()
            display_name = _required_text(row, "recipient_display_name")
            if not effective_settings.email_is_allowed(recipient):
                _complete_delivery(client, delivery_id=delivery_id, success=False)
                failed += 1
                continue
            try:
                send_teacher_friday_reminder(
                    effective_settings,
                    recipient_email=recipient,
                    display_name=display_name,
                    week_start=window.week_start,
                    next_week_start=window.week_start + timedelta(days=7),
                    items=_teacher_items(row),
                )
            except (SesDeliveryError, ScheduledDigestWorkerError):
                _complete_delivery(client, delivery_id=delivery_id, success=False)
                failed += 1
                continue
            _complete_delivery(client, delivery_id=delivery_id, success=True)
            sent += 1

    # Never print recipient addresses, names, course names, message bodies, school IDs, or SES IDs.
    print(
        "teacher_friday_reminder_complete",
        f"school_windows={len(windows)}",
        f"claimed={claimed}",
        f"sent={sent}",
        f"failed={failed}",
    )
    return {
        "school_windows": len(windows),
        "claimed": claimed,
        "sent": sent,
        "failed": failed,
    }


def run_scheduled_admin_digest(
    settings: Settings | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Send school-local aggregate digests only for explicitly enabled schools."""
    effective_settings = settings or Settings()
    _assert_approved_sender(effective_settings)
    dispatch_now = now or datetime.now(UTC)
    client = _service_client(effective_settings)
    windows = _dispatch_windows(client, mode="admin", now=dispatch_now)

    claimed = 0
    sent = 0
    failed = 0
    for window in windows:
        candidates = _claim_admin_candidates(
            client,
            school_id=window.school_id,
            week_start=window.week_start,
        )
        claimed += len(candidates)
        for row in candidates:
            delivery_id = _required_text(row, "delivery_id")
            recipient = _required_text(row, "recipient_email").lower()
            if not effective_settings.email_is_allowed(recipient):
                _complete_delivery(client, delivery_id=delivery_id, success=False)
                failed += 1
                continue
            try:
                send_friday_admin_digest(
                    effective_settings,
                    recipient_email=recipient,
                    metrics=_admin_metrics(row, week_start=window.week_start),
                )
            except (SesDeliveryError, ScheduledDigestWorkerError):
                _complete_delivery(client, delivery_id=delivery_id, success=False)
                failed += 1
                continue
            _complete_delivery(client, delivery_id=delivery_id, success=True)
            sent += 1

    print(
        "scheduled_admin_digest_complete",
        f"school_windows={len(windows)}",
        f"claimed={claimed}",
        f"sent={sent}",
        f"failed={failed}",
    )
    return {
        "school_windows": len(windows),
        "claimed": claimed,
        "sent": sent,
        "failed": failed,
    }


def main() -> int:
    mode = sys.argv[1].strip().lower() if len(sys.argv) > 1 else "admin"
    if mode not in {"teacher", "admin"}:
        print("scheduled_notification_failed unsupported worker mode")
        return 1
    try:
        result = (
            run_teacher_friday_reminders()
            if mode == "teacher"
            else run_scheduled_admin_digest()
        )
    except ScheduledDigestWorkerError as error:
        print("scheduled_notification_failed", str(error))
        return 1
    return 0 if result["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
