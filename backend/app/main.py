from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from .act_reference_admin_api import router as act_reference_admin_router
from .administration_api import router as administration_router
from .ai_planning_api import router as ai_planning_router
from .ai_planning_resilient_api import router as ai_planning_resilient_router
from .ai_reflection_api import router as ai_reflection_router
from .curriculum_api import router as curriculum_router
from .document_sections import HqiDocument
from .document_service import (
    DEFAULT_TEMPLATE_PATH,
    generate_anniston_hqi,
    generate_anniston_hqi_document,
    generate_anniston_hqi_packet,
    generate_anniston_lesson_plan_packet,
)
from .fixtures import (
    ASSIGNMENT_IDS,
    afternoon_block_pattern,
    anniston_exceptions,
    period_pattern,
    synthetic_jrotc_lessons,
)
from .friday_validation_api import router as friday_validation_router
from .hqi_document_renderer import DOCUMENT_TITLES
from .identity_api import router as identity_router
from .live_planning_api import router as live_planning_router
from .planned_lesson_api import router as planned_lesson_router
from .planner import build_weekly_plan
from .readiness_api import router as readiness_router
from .reporting import (
    AdminUsageEvent,
    AiFeature,
    AiUsageRecord,
    summarize_admin_usage,
    summarize_ai_cost,
)
from .schedule_exception_api import router as schedule_exception_router
from .standards_admin_api import router as standards_admin_router
from .standards_api import router as standards_router
from .standards_catalog_api import router as standards_catalog_router
from .teaching_assignment_api import router as teaching_assignment_router
from .weekly_draft_api import router as weekly_draft_router

DOCUMENT_TITLES[HqiDocument.INSTRUCTIONAL_FRAMEWORK] = "Instructional Planning Framework"

app = FastAPI(
    title="Teacher Planning Platform API",
    version="0.1.0",
    description="Version 1 pilot API for Anniston City Schools.",
)
app.include_router(identity_router)
app.include_router(readiness_router)
app.include_router(administration_router)
app.include_router(act_reference_admin_router)
app.include_router(curriculum_router)
app.include_router(teaching_assignment_router)
app.include_router(live_planning_router)
app.include_router(planned_lesson_router)
app.include_router(schedule_exception_router)
app.include_router(standards_router)
app.include_router(standards_catalog_router)
app.include_router(standards_admin_router)
app.include_router(ai_planning_resilient_router)
app.include_router(ai_planning_router)
app.include_router(ai_reflection_router)
app.include_router(weekly_draft_router)
app.include_router(friday_validation_router)


def _require_template() -> None:
    if not DEFAULT_TEMPLATE_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="The approved planning PDF template is unavailable",
        )


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "teacher-planning-platform"}


@app.get("/api/v1/standards", tags=["standards"])
def standards() -> dict[str, object]:
    return {
        "source": "Anniston pilot controlled catalog",
        "standards": [
            {"code": "JROTC-LET1-U1", "description": "Foundations and citizenship"},
            {"code": "JROTC-LET1-U2", "description": "Leadership and personal growth"},
        ],
    }


@app.get("/api/v1/plan", tags=["planning"])
def generated_plan(
    course: Annotated[str, Query()] = "LET 1",
    week_start: Annotated[date, Query()] = date(2026, 8, 10),
) -> dict[str, object]:
    lessons = synthetic_jrotc_lessons()
    pattern = afternoon_block_pattern() if course == "LET 2" else period_pattern()
    result = build_weekly_plan(
        assignment_id=ASSIGNMENT_IDS.get(course, ASSIGNMENT_IDS["LET 1"]),
        week_start=week_start,
        lessons=lessons,
        meeting_patterns=(pattern,),
        exceptions=anniston_exceptions(),
    )
    return {
        "week_start": week_start.isoformat(),
        "assignment_id": result[0].assignment_id if result else ASSIGNMENT_IDS["LET 1"],
        "lessons": [
            {
                "scheduled_lesson_id": item.scheduled_lesson_id,
                "curriculum_lesson_id": item.curriculum_lesson_id,
                "unit_title": item.unit_title,
                "lesson_title": item.lesson_title,
                "lesson_date": item.lesson_date.isoformat(),
                "sequence": item.sequence,
                "planned_minutes": item.planned_minutes,
                "segment_number": item.segment_number,
                "status": item.status,
            }
            for item in result
        ],
    }


@app.post("/api/v1/documents/anniston-hqi", tags=["documents"])
def generate_hqi_document(
    payload: Annotated[dict[str, str], Body()],
    flatten: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    _require_template()
    try:
        document = generate_anniston_hqi(payload, flatten=flatten)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    filename = (
        "anniston-planning-document-set-flat.pdf"
        if flatten
        else "anniston-planning-document-set.pdf"
    )
    return StreamingResponse(
        BytesIO(document),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/v1/documents/anniston-hqi/{document}", tags=["documents"])
def generate_hqi_section_document(
    document: HqiDocument,
    payload: Annotated[dict[str, str], Body()],
    flatten: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    _require_template()
    try:
        rendered = generate_anniston_hqi_document(payload, document, flatten=flatten)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    suffix = "-flat" if flatten else ""
    filename = f"anniston-planning-{document.value}{suffix}.pdf"
    return StreamingResponse(
        BytesIO(rendered.pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-TPP-Page-Count": str(rendered.page_count),
            "X-TPP-Continuation-Pages": str(rendered.continuation_page_count),
        },
    )


@app.post("/api/v1/documents/anniston-lesson-plan-packet", tags=["documents"])
def generate_lesson_plan_packet(
    payload: Annotated[dict[str, str], Body()],
    flatten: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    _require_template()
    try:
        packet, documents = generate_anniston_lesson_plan_packet(payload, flatten=flatten)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    continuation_pages = sum(item.continuation_page_count for item in documents)
    suffix = "-flat" if flatten else ""
    filename = f'anniston-weekly-lesson-plan{suffix}.pdf'
    return StreamingResponse(
        BytesIO(packet),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-TPP-Document-Count": str(len(documents)),
            "X-TPP-Continuation-Pages": str(continuation_pages),
        },
    )


@app.post("/api/v1/documents/anniston-hqi-packet", tags=["documents"])
def generate_hqi_packet(
    payload: Annotated[dict[str, str], Body()],
    flatten: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    _require_template()
    try:
        packet, documents = generate_anniston_hqi_packet(payload, flatten=flatten)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    continuation_pages = sum(item.continuation_page_count for item in documents)
    suffix = "-flat" if flatten else ""
    return StreamingResponse(
        BytesIO(packet),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="anniston-planning-combined-packet{suffix}.pdf"'
            ),
            "X-TPP-Document-Count": str(len(documents)),
            "X-TPP-Continuation-Pages": str(continuation_pages),
        },
    )


@app.get("/api/v1/admin/summary", tags=["administration"])
def admin_summary() -> dict[str, object]:
    summary = summarize_admin_usage(
        [
            AdminUsageEvent("synthetic-teacher", "assignment_configured", assignment_id)
            for assignment_id in ASSIGNMENT_IDS.values()
        ]
        + [
            AdminUsageEvent("synthetic-teacher", "plan_generated", ASSIGNMENT_IDS["LET 1"]),
            AdminUsageEvent(
                "synthetic-teacher",
                "friday_validation_completed",
                ASSIGNMENT_IDS["LET 1"],
            ),
        ]
    )
    return {
        "teachers_active": summary.teachers_active,
        "assignments_configured": summary.assignments_configured,
        "plans_generated": summary.plans_generated,
        "friday_validations_completed": summary.friday_validations_completed,
        "lessons_carried_forward": summary.lessons_carried_forward,
        "generation_failures": summary.generation_failures,
        "data_boundary": "synthetic-only",
    }


@app.get("/api/v1/admin/costs", tags=["administration"])
def cost_summary() -> dict[str, object]:
    summary = summarize_ai_cost(
        [
            AiUsageRecord(
                organization_id="anniston-city-schools",
                school_id="anniston-high-school",
                teacher_id="synthetic-teacher",
                assignment_id=ASSIGNMENT_IDS["LET 1"],
                feature=AiFeature.REFLECTION,
                model="synthetic-model",
                input_tokens=420,
                output_tokens=160,
                estimated_cost_usd=Decimal("0.0042"),
                accepted_by_teacher=True,
            )
        ]
    )
    return {
        "total_requests": summary.total_requests,
        "successful_requests": summary.successful_requests,
        "failed_requests": summary.failed_requests,
        "total_input_tokens": summary.total_input_tokens,
        "total_output_tokens": summary.total_output_tokens,
        "total_estimated_cost_usd": str(summary.total_estimated_cost_usd),
        "accepted_outputs": summary.accepted_outputs,
        "discarded_outputs": summary.discarded_outputs,
        "cost_basis": "estimated synthetic usage",
    }
