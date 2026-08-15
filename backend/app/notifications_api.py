from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError

from .auth import (
    AuthenticatedTeacher,
    require_platform_admin,
    require_school_reporting_admin,
)
from .notification_email import (
    SesDeliveryError,
    WeeklyAdminDigestMetrics,
    send_weekly_admin_digest,
)
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class WeeklyDigestMetricsRead(BaseModel):
    configured_assignments: int = 0
    lesson_plans_submitted: int = 0
    lesson_plans_missing: int = 0
    completed_packets_submitted: int = 0
    completed_packets_missing: int = 0
    teachers_with_completed_packets: int = 0
    plc_brief_available: bool = False


class WeeklyDigestDeliveryRead(BaseModel):
    week_start: date
    status: str = "sent"
    recipient_scope: str = "requesting-admin"
    metrics: WeeklyDigestMetricsRead
    content_boundary: str = "counts-and-authenticated-link-only"


class NotificationUsageRead(BaseModel):
    period_start: date
    period_end: date
    admin_weekly_digests_sent: int = 0
    admin_digest_senders: int = 0
    scheduled_admin_weekly_digests_sent: int = 0
    scheduled_digest_recipient_admins: int = 0
    scheduled_digest_schools: int = 0


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Notification reporting returned invalid data")
    return [cast(dict[str, Any], row) for row in payload if isinstance(row, dict)]


def _source_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Notification reporting is not authorized")
    if error.status_code in {400, 409, 422}:
        return HTTPException(status_code=409, detail="Notification reporting source was rejected")
    return HTTPException(status_code=503, detail="Notification reporting is unavailable")


def _submission_rows(
    client: SupabaseRestClient,
    *,
    week_start: date,
    school_id: str,
) -> list[dict[str, Any]]:
    try:
        payload = client.request(
            "POST",
            "rpc/admin_weekly_submission_status_v2",
            payload={
                "target_week_start": week_start.isoformat(),
                "target_school_id": school_id,
            },
        )
    except SupabaseRestError as error:
        raise _source_error(error) from error
    return _records(payload)


def _digest_metrics(rows: list[dict[str, Any]], *, week_start: date) -> WeeklyAdminDigestMetrics:
    assignments = [row for row in rows if isinstance(row.get("assignment_id"), str)]
    lesson_submitted = [
        row for row in assignments if row.get("lesson_plan_revision") is not None
    ]
    packet_submitted = [
        row for row in assignments if row.get("completed_packet_revision") is not None
    ]
    teacher_ids = {
        teacher_id
        for row in packet_submitted
        if isinstance((teacher_id := row.get("teacher_id")), str) and teacher_id
    }
    return WeeklyAdminDigestMetrics(
        week_start=week_start,
        configured_assignments=len(assignments),
        lesson_plans_submitted=len(lesson_submitted),
        lesson_plans_missing=len(assignments) - len(lesson_submitted),
        completed_packets_submitted=len(packet_submitted),
        completed_packets_missing=len(assignments) - len(packet_submitted),
        teachers_with_completed_packets=len(teacher_ids),
    )


def _record_delivery_event(client: SupabaseRestClient, school_id: str) -> None:
    """Content-free analytics are fail-open and may never turn a sent email into an error."""
    try:
        client.request(
            "POST",
            "rpc/record_notification_delivery_event",
            payload={
                "target_notification_key": "admin_weekly_digest_sent",
                "target_school_id": school_id,
            },
        )
    except SupabaseRestError:
        return


@router.post("/admin-weekly-digest/{week_start}", response_model=WeeklyDigestDeliveryRead)
def send_admin_weekly_digest(
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDigestDeliveryRead:
    """Email minimized school operations counts to the requesting administrator's own account."""
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    if week_start.weekday() != 0:
        raise HTTPException(status_code=422, detail="Weekly digest week_start must be a Monday")

    client = _client(identity, settings)
    metrics = _digest_metrics(
        _submission_rows(client, week_start=week_start, school_id=identity.school_id),
        week_start=week_start,
    )

    try:
        send_weekly_admin_digest(
            settings,
            recipient_email=identity.email,
            metrics=metrics,
        )
    except SesDeliveryError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    _record_delivery_event(client, identity.school_id)
    return WeeklyDigestDeliveryRead(
        week_start=week_start,
        metrics=WeeklyDigestMetricsRead(
            configured_assignments=metrics.configured_assignments,
            lesson_plans_submitted=metrics.lesson_plans_submitted,
            lesson_plans_missing=metrics.lesson_plans_missing,
            completed_packets_submitted=metrics.completed_packets_submitted,
            completed_packets_missing=metrics.completed_packets_missing,
            teachers_with_completed_packets=metrics.teachers_with_completed_packets,
            plc_brief_available=metrics.plc_brief_available,
        ),
    )


@router.get("/usage", response_model=NotificationUsageRead)
def notification_usage(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> NotificationUsageRead:
    if period_end < period_start:
        raise HTTPException(
            status_code=422,
            detail="Reporting period end must be on or after start",
        )
    if period_end - period_start > timedelta(days=366):
        raise HTTPException(
            status_code=422,
            detail="Notification reporting is limited to 367 days",
        )

    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/platform_notification_usage",
            payload={
                "target_start": period_start.isoformat(),
                "target_end": period_end.isoformat(),
            },
        )
    except SupabaseRestError as error:
        raise _source_error(error) from error

    rows = _records(payload)
    if not rows:
        return NotificationUsageRead(period_start=period_start, period_end=period_end)
    try:
        return NotificationUsageRead.model_validate(rows[0])
    except ValidationError as error:
        raise HTTPException(
            status_code=503,
            detail="Notification usage reporting is invalid",
        ) from error
