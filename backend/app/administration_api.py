from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

from .auth import (
    AuthenticatedTeacher,
    require_platform_admin,
    require_school_reporting_admin,
)
from .document_service import DEFAULT_TEMPLATE_PATH, generate_anniston_hqi_packet
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


class BatchSubmissionItem(BaseModel):
    assignment_id: str
    week_start: date


class BatchSubmissionPacketRequest(BaseModel):
    items: list[BatchSubmissionItem]


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


def _submitted_plan_record(
    assignment_id: str,
    week_start: date,
    identity: AuthenticatedTeacher,
    settings: Settings,
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


def _render_submitted_packet(submitted: WeeklySubmittedPlanRead) -> bytes:
    if not DEFAULT_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=503, detail="The approved planning PDF template is unavailable")
    try:
        packet, _documents = generate_anniston_hqi_packet(submitted.source_data)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Submitted plan PDF could not be generated") from error
    return packet


@router.get("/usage", response_model=SchoolUsageRead)
def school_usage(
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date | None, Query()] = None,
    period_end: Annotated[date | None, Query()] = None,
) -> SchoolUsageRead:
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    if (period_start is None) != (period_end is None):
        raise HTTPException(status_code=422, detail="Both reporting period dates are required")
    if period_start is not None and period_end is not None and period_end < period_start:
        raise HTTPException(status_code=422, detail="Reporting period end must be on or after start")
    try:
        client = _client(identity, settings)
        if period_start is not None and period_end is not None:
            payload = client.request(
                "POST",
                "rpc/admin_usage_for_period",
                payload={
                    "target_start": period_start.isoformat(),
                    "target_end": period_end.isoformat(),
                    "target_school_id": identity.school_id,
                },
            )
        else:
            payload = client.request(
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
    return _submitted_plan_record(assignment_id, week_start, identity, settings)


@router.get("/submissions/{assignment_id}/packet")
def submitted_plan_packet(
    assignment_id: str,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Render the immutable submitted revision as the same combined packet teachers review."""
    submitted = _submitted_plan_record(assignment_id, week_start, identity, settings)
    packet = _render_submitted_packet(submitted)
    safe_week = submitted.week_start.isoformat()
    return StreamingResponse(
        BytesIO(packet),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="submitted-planning-packet-{safe_week}.pdf"',
            "X-TPP-Submitted-Revision": str(submitted.submitted_revision),
            "X-TPP-Document-Count": "3",
        },
    )


@router.post("/submissions/batch-packet")
def submitted_batch_packet(
    request: BatchSubmissionPacketRequest,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Merge selected immutable submitted revisions into one administrator review packet."""
    if not request.items:
        raise HTTPException(status_code=422, detail="Select at least one submitted plan")
    if len(request.items) > 300:
        raise HTTPException(status_code=422, detail="A maximum of 300 submitted plans may be reviewed at once")

    writer = PdfWriter()
    seen: set[tuple[str, date]] = set()
    included = 0
    for item in request.items:
        key = (item.assignment_id, item.week_start)
        if key in seen:
            continue
        seen.add(key)
        submitted = _submitted_plan_record(item.assignment_id, item.week_start, identity, settings)
        packet = _render_submitted_packet(submitted)
        reader = PdfReader(BytesIO(packet))
        for page in reader.pages:
            writer.add_page(page)
        included += 1

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="submitted-planning-batch.pdf"',
            "X-TPP-Submission-Count": str(included),
            "X-TPP-Document-Count": str(included * 3),
        },
    )


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