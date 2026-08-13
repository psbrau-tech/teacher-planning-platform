from __future__ import annotations

from datetime import date
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import AuthenticatedTeacher, require_platform_admin, require_teacher
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(tags=["product-usage"])


class ProductUsageWrite(BaseModel):
    event_key: str


class ProductUsageRead(BaseModel):
    recorded: bool = True


class ProductOwnerUsageRead(BaseModel):
    period_start: date
    period_end: date
    teachers_authorized: int = 0
    teachers_authenticated: int = 0
    teachers_pilot_cohort: int = 0
    teachers_active: int = 0
    classes_configured: int = 0
    shared_curriculum_teachers: int = 0
    shared_curriculum_classes: int = 0
    curriculum_excel_saves: int = 0
    curriculum_excel_teachers: int = 0
    curriculum_builder_saves: int = 0
    curriculum_builder_teachers: int = 0
    curriculum_reuse_events: int = 0
    curriculum_reuse_teachers: int = 0
    curriculum_copy_events: int = 0
    curriculum_copy_teachers: int = 0
    curriculum_export_events: int = 0
    curriculum_export_teachers: int = 0
    weekly_plan_generate_events: int = 0
    weekly_plan_generate_teachers: int = 0
    weekly_plans_saved: int = 0
    weekly_plan_teachers: int = 0
    ai_requests: int = 0
    ai_teachers: int = 0
    ai_fields_accepted: int = 0
    ai_fields_edited: int = 0
    ai_fields_rejected: int = 0
    lesson_plan_pdf_views: int = 0
    lesson_plan_pdf_view_teachers: int = 0
    lesson_plan_submissions: int = 0
    lesson_plan_submission_teachers: int = 0
    completed_packet_submissions: int = 0
    completed_packet_teachers: int = 0
    completed_packet_views: int = 0
    completed_packet_view_teachers: int = 0
    pilot_feedback_responses: int = 0


class ProductOwnerActiveTimeRead(BaseModel):
    period_start: date
    period_end: date
    active_time_teachers: int = 0
    course_setup_total_seconds: int = 0
    weekly_planning_total_seconds: int = 0
    reflection_total_seconds: int = 0
    friday_closeout_total_seconds: int = 0
    other_friday_closeout_total_seconds: int = 0
    median_course_setup_seconds_per_teacher: int = 0
    median_weekly_planning_seconds_per_teacher_week: int = 0
    median_reflection_seconds_per_teacher_week: int = 0
    median_friday_closeout_seconds_per_teacher_week: int = 0
    median_other_friday_closeout_seconds_per_teacher_week: int = 0
    onboarding_weekly_planning_teacher_weeks: int = 0
    median_onboarding_weekly_planning_seconds: int = 0
    steady_state_weekly_planning_teacher_weeks: int = 0
    median_steady_state_weekly_planning_seconds: int = 0
    onboarding_reflection_teacher_weeks: int = 0
    median_onboarding_reflection_seconds: int = 0
    steady_state_reflection_teacher_weeks: int = 0
    median_steady_state_reflection_seconds: int = 0


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Product usage service returned invalid data")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _usage_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {400, 409, 422}:
        return HTTPException(status_code=422, detail="Product usage event was not accepted")
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Product usage access is not authorized")
    return HTTPException(status_code=503, detail="Product usage service is unavailable")


def _validate_period(period_start: date, period_end: date) -> None:
    if period_end < period_start:
        raise HTTPException(
            status_code=422,
            detail="Reporting period end must be on or after start",
        )


@router.post("/api/v1/product-usage", response_model=ProductUsageRead)
def record_product_usage(
    payload: ProductUsageWrite,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProductUsageRead:
    try:
        _client(identity, settings).request(
            "POST",
            "rpc/record_product_usage_event",
            payload={"target_event_key": payload.event_key},
        )
    except SupabaseRestError as error:
        raise _usage_error(error) from error
    return ProductUsageRead()


@router.get("/api/v1/product-owner/usage", response_model=ProductOwnerUsageRead)
def product_owner_usage(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> ProductOwnerUsageRead:
    _validate_period(period_start, period_end)
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/platform_product_usage_summary",
            payload={
                "target_start": period_start.isoformat(),
                "target_end": period_end.isoformat(),
            },
        )
    except SupabaseRestError as error:
        raise _usage_error(error) from error
    rows = _records(payload)
    if not rows:
        raise HTTPException(status_code=403, detail="Product Owner reporting is not authorized")
    return ProductOwnerUsageRead.model_validate(rows[0])


@router.get("/api/v1/product-owner/active-time", response_model=ProductOwnerActiveTimeRead)
def product_owner_active_time(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> ProductOwnerActiveTimeRead:
    _validate_period(period_start, period_end)
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/platform_product_active_time_summary",
            payload={
                "target_start": period_start.isoformat(),
                "target_end": period_end.isoformat(),
            },
        )
    except SupabaseRestError as error:
        raise _usage_error(error) from error
    rows = _records(payload)
    if not rows:
        raise HTTPException(status_code=403, detail="Product Owner reporting is not authorized")
    return ProductOwnerActiveTimeRead.model_validate(rows[0])
