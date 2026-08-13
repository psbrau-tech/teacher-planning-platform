from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

from .auth import (
    AuthenticatedTeacher,
    require_platform_admin,
    require_school_reporting_admin,
)
from .document_service import (
    DEFAULT_TEMPLATE_PATH,
    generate_anniston_hqi_packet,
    generate_anniston_lesson_plan_packet,
)
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/administration", tags=["administration"])
SubmissionKind = Literal["lesson_plan", "completed_packet"]


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
    lesson_plan_revision: int | None = None
    lesson_plan_submitted_at: str | None = None
    completed_packet_revision: int | None = None
    completed_packet_submitted_at: str | None = None
    # Compatibility fields preserve existing reporting clients while the UI moves to typed columns.
    submitted_revision: int | None = None
    submission_status: str = "not_started"
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
    submission_kind: SubmissionKind
    source_data: dict[str, str]


class BatchSubmissionItem(BaseModel):
    assignment_id: str
    week_start: date


class BatchSubmissionPacketRequest(BaseModel):
    items: list[BatchSubmissionItem]
    submission_kind: SubmissionKind = "completed_packet"


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
    submission_kind: SubmissionKind,
    identity: AuthenticatedTeacher,
    settings: Settings,
) -> WeeklySubmittedPlanRead:
    try:
        payload = _client(identity, settings).request(
            "POST",
            "rpc/admin_weekly_submission_document_by_kind",
            payload={
                "target_assignment_id": assignment_id,
                "target_week_start": week_start.isoformat(),
                "target_submission_kind": submission_kind,
            },
        )
    except (RuntimeError, SupabaseRestError) as error:
        if isinstance(error, SupabaseRestError):
            raise _reporting_error(error) from error
        raise HTTPException(status_code=503, detail=str(error)) from error

    rows = _records(payload)
    if not rows:
        label = "lesson plan" if submission_kind == "lesson_plan" else "completed packet"
        raise HTTPException(status_code=404, detail=f"Submitted {label} was not found")
    return WeeklySubmittedPlanRead.model_validate(rows[0])


def _render_submitted_packet(submitted: WeeklySubmittedPlanRead) -> tuple[bytes, int]:
    if not DEFAULT_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=503, detail="The approved planning PDF template is unavailable")
    try:
        if submitted.submission_kind == "lesson_plan":
            packet, documents = generate_anniston_lesson_plan_packet(submitted.source_data)
        else:
            packet, documents = generate_anniston_hqi_packet(submitted.source_data)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Submitted plan PDF could not be generated") from error
    return packet, len(documents)


@router.get("/usage", response_model=SchoolUsageRead)
def school_usage(
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date | None, Query()] = None,
    period_end: Annotated[date | None, Query()] = None,
    teacher_ids: Annotated[list[UUID] | None, Query(alias="teacher_id")] = None,
) -> SchoolUsageRead:
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    if (period_start is None) != (period_end is None):
        raise HTTPException(status_code=422, detail="Both reporting period dates are required")
    if period_start is not None and period_end is not None and period_end < period_start:
        raise HTTPException(status_code=422, detail="Reporting period end must be on or after start")
    if teacher_ids is not None and len(teacher_ids) > 300:
        raise HTTPException(status_code=422, detail="A maximum of 300 teachers may be selected")
    try:
        client = _client(identity, settings)
        if period_start is not None and period_end is not None:
            if teacher_ids:
                payload = client.request(
                    "POST",
                    "rpc/admin_usage_for_period_selected",
                    payload={
                        "target_start": period_start.isoformat(),
                        "target_end": period_end.isoformat(),
                        "target_school_id": identity.school_id,
                        "target_teacher_ids": [str(teacher_id) for teacher_id in teacher_ids],
                    },
                )
            else:
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
            "rpc/admin_weekly_submission_status_v2",
            payload={
                "target_week_start": week_start.isoformat(),
                "target_school_id": school_id,
            },
        )
    except (RuntimeError, SupabaseRestError) as error:
        if isinstance(error, SupabaseRestError):
            raise _reporting_error(error) from error
        raise HTTPException(status_code=503, detail=str(error)) from error

    result: list[WeeklySubmissionRead] = []
    for row in _records(payload):
        lesson_revision = row.get("lesson_plan_revision")
        lesson_at = row.get("lesson_plan_submitted_at")
        if row.get("assignment_id") is None:
            status = "no_course"
        elif lesson_revision is None and row.get("revision") is None:
            status = "not_started"
        elif lesson_revision is None:
            status = "draft"
        else:
            status = "submitted"
        result.append(
            WeeklySubmissionRead.model_validate(
                {
                    **row,
                    "submitted_revision": lesson_revision,
                    "submitted_at": lesson_at,
                    "submission_status": status,
                }
            )
        )
    return result


@router.get("/submissions/{assignment_id}", response_model=WeeklySubmittedPlanRead)
def submitted_plan(
    assignment_id: str,
    week_start: date,
    submission_kind: SubmissionKind,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklySubmittedPlanRead:
    return _submitted_plan_record(
        assignment_id, week_start, submission_kind, identity, settings
    )


def _single_packet_response(
    assignment_id: str,
    week_start: date,
    submission_kind: SubmissionKind,
    identity: AuthenticatedTeacher,
    settings: Settings,
) -> StreamingResponse:
    submitted = _submitted_plan_record(
        assignment_id, week_start, submission_kind, identity, settings
    )
    packet, document_count = _render_submitted_packet(submitted)
    safe_week = submitted.week_start.isoformat()
    filename_label = "lesson-plan" if submission_kind == "lesson_plan" else "completed-packet"
    return StreamingResponse(
        BytesIO(packet),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="submitted-{filename_label}-{safe_week}.pdf"'
            ),
            "X-TPP-Submitted-Revision": str(submitted.submitted_revision),
            "X-TPP-Submission-Kind": submission_kind,
            "X-TPP-Document-Count": str(document_count),
        },
    )


@router.get("/submissions/{assignment_id}/lesson-plan-packet")
def submitted_lesson_plan_packet(
    assignment_id: str,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    return _single_packet_response(
        assignment_id, week_start, "lesson_plan", identity, settings
    )


@router.get("/submissions/{assignment_id}/completed-packet")
def submitted_completed_packet(
    assignment_id: str,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    return _single_packet_response(
        assignment_id, week_start, "completed_packet", identity, settings
    )


@router.get("/submissions/{assignment_id}/packet")
def submitted_plan_packet(
    assignment_id: str,
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Compatibility route: completed packet after Friday closeout."""
    return _single_packet_response(
        assignment_id, week_start, "completed_packet", identity, settings
    )


@router.post("/submissions/batch-packet")
def submitted_batch_packet(
    request: BatchSubmissionPacketRequest,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Merge selected immutable submissions of one kind into one administrator review PDF."""
    if not request.items:
        raise HTTPException(status_code=422, detail="Select at least one submitted plan")
    if len(request.items) > 300:
        raise HTTPException(
            status_code=422,
            detail="A maximum of 300 submitted plans may be reviewed at once",
        )

    writer = PdfWriter()
    seen: set[tuple[str, date]] = set()
    included = 0
    document_count = 0
    for item in request.items:
        key = (item.assignment_id, item.week_start)
        if key in seen:
            continue
        seen.add(key)
        submitted = _submitted_plan_record(
            item.assignment_id,
            item.week_start,
            request.submission_kind,
            identity,
            settings,
        )
        packet, packet_document_count = _render_submitted_packet(submitted)
        reader = PdfReader(BytesIO(packet))
        for page in reader.pages:
            writer.add_page(page)
        included += 1
        document_count += packet_document_count

    output = BytesIO()
    writer.write(output)
    output.seek(0)
    filename_label = (
        "lesson-plans" if request.submission_kind == "lesson_plan" else "completed-packets"
    )
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="submitted-{filename_label}-batch.pdf"',
            "X-TPP-Submission-Count": str(included),
            "X-TPP-Submission-Kind": request.submission_kind,
            "X-TPP-Document-Count": str(document_count),
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
