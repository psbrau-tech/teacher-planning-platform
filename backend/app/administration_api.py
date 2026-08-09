from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import (
    AuthenticatedTeacher,
    require_platform_admin,
    require_school_reporting_admin,
)
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/administration", tags=["administration"])


class SchoolUsageRead(BaseModel):
    school_id: str
    teachers_configured: int = 0
    teachers_with_assignments: int = 0
    assignments_configured: int = 0
    weekly_plans_created: int = 0
    weekly_plans_approved: int = 0
    instruction_records_validated: int = 0
    lessons_carried_forward: int = 0
    documents_requested: int = 0
    documents_generated: int = 0
    document_generation_failures: int = 0
    data_boundary: str = "teacher-and-curriculum-only"


class SchoolCostRead(BaseModel):
    school_id: str
    usage_month: str
    request_count: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0")
    accepted_outputs: int = 0
    discarded_outputs: int = 0


class WeeklySubmissionRead(BaseModel):
    school_id: str
    school_name: str
    teacher_id: str
    teacher_name: str
    assignment_id: str | None = None
    course_name: str | None = None
    week_start: date
    revision: int | None = None
    submitted_revision: int | None = None
    submission_status: str
    submitted_at: str | None = None


class WeeklySubmittedPlanRead(BaseModel):
    school_id: str
    school_name: str
    teacher_id: str
    teacher_name: str
    assignment_id: str
    course_name: str
    week_start: date
    submitted_revision: int
    submitted_at: str
    source_data: dict[str, str]


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Administration reporting is unavailable")
    return [cast(dict[str, Any], item) for item in payload if isinstance(item, dict)]


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _reporting_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Administration reporting is not authorized")
    return HTTPException(status_code=503, detail="Administration reporting is unavailable")


@router.get("/usage", response_model=SchoolUsageRead)
def school_usage(
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SchoolUsageRead:
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    try:
        payload = _client(identity, settings).request(
            "GET",
            "school_admin_usage_summary",
            params={
                "school_id": f"eq.{identity.school_id}",
                "select": (
                    "school_id,teachers_configured,teachers_with_assignments,"
                    "assignments_configured,weekly_plans_created,weekly_plans_approved,"
                    "instruction_records_validated,lessons_carried_forward,"
                    "documents_requested,documents_generated,document_generation_failures"
                ),
                "limit": "1",
            },
        )
    except (RuntimeError, SupabaseRestError) as error:
        if isinstance(error, SupabaseRestError):
            raise _reporting_error(error) from error
        raise HTTPException(status_code=503, detail=str(error)) from error

    rows = _records(payload)
    if not rows:
        return SchoolUsageRead(school_id=identity.school_id)
    return SchoolUsageRead.model_validate(
        {**rows[0], "data_boundary": "teacher-and-curriculum-only"}
    )


@router.get("/submissions", response_model=list[WeeklySubmissionRead])
def weekly_submissions(
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    school_id: Annotated[str | None, Query()] = None,
) -> list[WeeklySubmissionRead]:
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/admin_weekly_submission_status",
            payload={
                "target_week_start": week_start.isoformat(),
                "target_school_id": school_id,
            },
        )
    except (RuntimeError, SupabaseRestError) as error:
        if isinstance(error, SupabaseRestError):
            raise _reporting_error(error) from error
        raise HTTPException(status_code=503, detail=str(error)) from error

    return [WeeklySubmissionRead.model_validate(row) for row in _records(payload)]


@router.get("/submissions/{assignment_id}", response_model=WeeklySubmittedPlanRead)
def submitted_plan(
    assignment_id: str,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklySubmittedPlanRead:
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/admin_weekly_submission_document",
            payload={
                "target_assignment_id": assignment_id,
                "target_week_start": week_start.isoformat(),
            },
        )
    except (RuntimeError, SupabaseRestError) as error:
        if isinstance(error, SupabaseRestError):
            raise _reporting_error(error) from error
        raise HTTPException(status_code=503, detail=str(error)) from error

    rows = _records(payload)
    if not rows:
        raise HTTPException(status_code=404, detail="Submitted weekly plan was not found")
    return WeeklySubmittedPlanRead.model_validate(rows[0])


@router.get("/costs", response_model=list[SchoolCostRead])
def platform_costs(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[SchoolCostRead]:
    try:
        payload = _client(identity, settings).request(
            "GET",
            "school_ai_cost_summary",
            params={
                "select": (
                    "school_id,usage_month,request_count,successful_requests,failed_requests,"
                    "input_tokens,output_tokens,cached_tokens,estimated_cost_usd,"
                    "accepted_outputs,discarded_outputs"
                ),
                "order": "usage_month.desc",
            },
        )
    except (RuntimeError, SupabaseRestError) as error:
        if isinstance(error, SupabaseRestError):
            raise _reporting_error(error) from error
        raise HTTPException(status_code=503, detail=str(error)) from error

    return [SchoolCostRead.model_validate(row) for row in _records(payload)]
