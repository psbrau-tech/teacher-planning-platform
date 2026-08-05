from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Annotated

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from .curriculum_api import router as curriculum_router
from .document_sections import HqiDocument
from .document_service import (
    DEFAULT_TEMPLATE_PATH,
    generate_anniston_hqi,
    generate_anniston_hqi_document,
    generate_anniston_hqi_packet,
)
from .fixtures import (
    ASSIGNMENT_IDS,
    afternoon_block_pattern,
    anniston_exceptions,
    period_pattern,
    synthetic_jrotc_lessons,
)
from .friday_validation_api import router as friday_validation_router
from .identity_api import router as identity_router
from .live_planning_api import router as live_planning_router
from .models import PlannedLesson
from .pdf_fields import ALL_HQI_FIELDS
from .planner import build_weekly_plan
from .readiness_api import router as readiness_router
from .reporting import (
    AdminUsageEvent,
    AiFeature,
    AiUsageRecord,
    summarize_admin_usage,
    summarize_ai_cost,
)
from .teaching_assignment_api import router as teaching_assignment_router
from .weekly_draft_api import router as weekly_draft_router

app = FastAPI(
    title="Teacher Planning Platform API",
    version="0.1.0",
    description="Version 1 pilot API for Anniston City Schools.",
)
app.include_router(identity_router)
app.include_router(readiness_router)
app.include_router(curriculum_router)
app.include_router(teaching_assignment_router)
app.include_router(live_planning_router)
app.include_router(weekly_draft_router)
app.include_router(friday_validation_router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tpp-api"}


@app.get("/api/v1/assignments", tags=["teacher"])
def list_assignments() -> list[dict[str, object]]:
    """Synthetic pilot endpoint until the live teacher workflow replaces it."""
    return [
        {
            "id": assignment_id,
            "course_name": level,
            "schedule_type": "block" if level == "LET 4" else "period",
            "curriculum": f"Army JROTC {level}",
        }
        for level, assignment_id in ASSIGNMENT_IDS.items()
    ]


@app.get("/api/v1/weekly-plan", response_model=list[PlannedLesson], tags=["planning"])
def weekly_plan(
    level: Annotated[str, Query(pattern=r"^LET [1-4]$")],
    week_start: Annotated[date, Query(description="Monday date for the requested week")],
) -> list[PlannedLesson]:
    assignment_id = ASSIGNMENT_IDS.get(level)
    if assignment_id is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")

    patterns = [afternoon_block_pattern()] if level == "LET 4" else [period_pattern()]
    return build_weekly_plan(
        assignment_id=assignment_id,
        week_start=week_start,
        patterns=patterns,
        lessons=synthetic_jrotc_lessons(level),
        exceptions=anniston_exceptions(),
    )


@app.get("/api/v1/templates/anniston-hqi/fields", tags=["documents"])
def anniston_hqi_fields() -> dict[str, object]:
    return {
        "template": "Anniston City Schools HQI Lesson Plan Framework",
        "field_count": len(ALL_HQI_FIELDS),
        "fields": ALL_HQI_FIELDS,
        "template_installed": DEFAULT_TEMPLATE_PATH.exists(),
        "documents": [document.value for document in HqiDocument],
    }


def _require_template() -> None:
    if not DEFAULT_TEMPLATE_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="The approved Anniston HQI PDF template is not installed.",
        )


@app.post("/api/v1/documents/anniston-hqi", tags=["documents"])
def generate_hqi_document_legacy(
    payload: Annotated[dict[str, str], Body()],
    flatten: Annotated[bool, Query()] = False,
) -> StreamingResponse:
    """Legacy three-page export retained temporarily for compatibility."""
    _require_template()
    try:
        document = generate_anniston_hqi(payload, flatten=flatten)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    filename = "anniston-hqi-lesson-plan-flat.pdf" if flatten else "anniston-hqi-lesson-plan.pdf"
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
    filename = f"anniston-hqi-{document.value}{suffix}.pdf"
    return StreamingResponse(
        BytesIO(rendered.pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-TPP-Page-Count": str(rendered.page_count),
            "X-TPP-Continuation-Pages": str(rendered.continuation_page_count),
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
                f'attachment; filename="anniston-hqi-combined-packet{suffix}.pdf"'
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
