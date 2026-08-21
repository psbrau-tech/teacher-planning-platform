from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from .ai_openai import AiServiceError, request_structured_response
from .ai_usage import record_ai_usage
from .auth import (
    AuthenticatedTeacher,
    require_platform_admin,
    require_school_reporting_admin,
    require_teacher,
)
from .reflection_intelligence import (
    SCHOOL_BRIEF_SCHEMA,
    SCHOOL_SYNTHESIS_INSTRUCTIONS,
    TEACHER_INSIGHT_SCHEMA,
    TEACHER_SYNTHESIS_INSTRUCTIONS,
    ReflectionBoundaryError,
    SchoolReflectionBrief,
    SchoolReflectionSource,
    TeacherReflectionInsight,
    TeacherReflectionSource,
    record_list,
    school_ai_context,
    teacher_ai_context,
    validate_school_brief,
)
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/reflection-intelligence", tags=["reflection-intelligence"])


class TeacherInsightRead(BaseModel):
    week_start: date
    lookback_weeks: int = Field(ge=4, le=12)
    source_submission_count: int = Field(ge=1)
    source_week_count: int = Field(ge=1)
    insight: TeacherReflectionInsight
    scope: str = "private-teacher"
    evaluation: str = "none"


class SchoolBriefRead(BaseModel):
    week_start: date
    source_teacher_count: int = Field(ge=2)
    source_submission_count: int = Field(ge=2)
    brief: SchoolReflectionBrief
    scope: str = "school-aggregate"
    evaluation: str = "none"


class ReflectionUsageRead(BaseModel):
    period_start: date
    period_end: date
    teacher_recaps_generated: int = 0
    teacher_recap_users: int = 0
    school_plc_briefs_generated: int = 0
    plc_brief_users: int = 0
    plc_handouts_viewed: int = 0
    plc_handout_users: int = 0


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _source_error(error: SupabaseRestError) -> HTTPException:
    if error.status_code in {401, 403}:
        return HTTPException(status_code=403, detail="Reflection Intelligence access is not authorized")
    if error.status_code in {400, 409, 422}:
        return HTTPException(status_code=409, detail="Reflection Intelligence source was rejected")
    return HTTPException(status_code=503, detail="Reflection Intelligence source is unavailable")


def _source_rows(
    client: SupabaseRestClient,
    function_name: str,
    payload: dict[str, object],
) -> list[dict[str, Any]]:
    try:
        return record_list(client.request("POST", f"rpc/{function_name}", payload=payload))
    except SupabaseRestError as error:
        raise _source_error(error) from error
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _record_event(
    client: SupabaseRestClient,
    event_key: str,
    school_id: str | None = None,
) -> None:
    """Content-free adoption telemetry is fail-open and may not block professional work."""
    try:
        client.request(
            "POST",
            "rpc/record_reflection_intelligence_event",
            payload={"target_event_key": event_key, "target_school_id": school_id},
        )
    except SupabaseRestError:
        return


def _boundary_error(error: ReflectionBoundaryError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail=(
            f"{error}. Review the submitted reflection in TPP and keep observations at the "
            "class or group level before using AI synthesis."
        ),
    )


def _require_complete_teacher_week(client: SupabaseRestClient, week_start: date) -> None:
    """Prevent a recap request until every required class packet for the week is submitted."""
    rows = _source_rows(
        client,
        "teacher_friday_submission_status",
        {"target_week_start": week_start.isoformat()},
    )
    required_rows = [row for row in rows if row.get("current_week_required") is True]
    if not required_rows or any(
        row.get("current_packet_submitted") is not True for row in required_rows
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Submit the Friday closeout for every required class before generating the "
                "combined private reflection recap."
            ),
        )


@router.post("/teacher/{week_start}", response_model=TeacherInsightRead)
def generate_teacher_insight(
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
    lookback_weeks: Annotated[int, Query(ge=4, le=12)] = 12,
) -> TeacherInsightRead:
    """Generate a private recap from the teacher's own immutable submitted reflections."""
    client = _client(identity, settings)
    _require_complete_teacher_week(client, week_start)
    rows = _source_rows(
        client,
        "teacher_reflection_intelligence_source",
        {
            "target_week_start": week_start.isoformat(),
            "target_lookback_weeks": lookback_weeks,
        },
    )
    try:
        sources = [TeacherReflectionSource.model_validate(row) for row in rows]
    except ValidationError as error:
        raise HTTPException(status_code=503, detail="Reflection Intelligence source is invalid") from error

    if not sources or not any(source.week_start == week_start.isoformat() for source in sources):
        raise HTTPException(
            status_code=404,
            detail="Submit the completed weekly packet before generating a reflection recap.",
        )

    try:
        context = teacher_ai_context(
            sources,
            selected_week=week_start.isoformat(),
            lookback_weeks=lookback_weeks,
        )
    except ReflectionBoundaryError as error:
        raise _boundary_error(error) from error

    try:
        result = request_structured_response(
            settings=settings,
            teacher_subject=identity.subject,
            instructions=TEACHER_SYNTHESIS_INSTRUCTIONS,
            context=context,
            schema_name="tpp_teacher_reflection_insight",
            schema=TEACHER_INSIGHT_SCHEMA,
        )
        insight = TeacherReflectionInsight.model_validate(result.data)
    except (AiServiceError, ValidationError) as error:
        try:
            record_ai_usage(
                client,
                identity=identity,
                assignment_id=None,
                feature="reflection_intelligence_teacher",
                model=settings.openai_model,
                succeeded=False,
                usage=None,
            )
        except HTTPException:
            pass
        raise HTTPException(
            status_code=503,
            detail="Private reflection synthesis is temporarily unavailable.",
        ) from error

    record_ai_usage(
        client,
        identity=identity,
        assignment_id=None,
        feature="reflection_intelligence_teacher",
        model=result.usage.model,
        succeeded=True,
        usage=result.usage,
    )
    _record_event(client, "teacher_recap_generated")
    return TeacherInsightRead(
        week_start=week_start,
        lookback_weeks=lookback_weeks,
        source_submission_count=len(sources),
        source_week_count=len({source.week_start for source in sources}),
        insight=insight,
    )


@router.post("/school/{week_start}", response_model=SchoolBriefRead)
def generate_school_brief(
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SchoolBriefRead:
    """Generate a school-scoped PLC brief from anonymous submitted reflection sources."""
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    client = _client(identity, settings)
    rows = _source_rows(
        client,
        "school_reflection_intelligence_source",
        {"target_school_id": identity.school_id, "target_week_start": week_start.isoformat()},
    )
    try:
        sources = [SchoolReflectionSource.model_validate(row) for row in rows]
    except ValidationError as error:
        raise HTTPException(status_code=503, detail="Reflection Intelligence source is invalid") from error

    source_refs = {source.source_ref for source in sources}
    if len(source_refs) < 2:
        raise HTTPException(
            status_code=409,
            detail=(
                "A school PLC brief requires submitted reflections from at least two distinct "
                "teachers so the output remains aggregate rather than individual."
            ),
        )

    try:
        context = school_ai_context(sources, week_start=week_start.isoformat())
    except ReflectionBoundaryError as error:
        raise _boundary_error(error) from error

    try:
        result = request_structured_response(
            settings=settings,
            teacher_subject=identity.subject,
            instructions=SCHOOL_SYNTHESIS_INSTRUCTIONS,
            context=context,
            schema_name="tpp_school_reflection_brief",
            schema=SCHOOL_BRIEF_SCHEMA,
        )
        brief = validate_school_brief(result.data, available_source_refs=source_refs)
    except (AiServiceError, ValidationError) as error:
        try:
            record_ai_usage(
                client,
                identity=identity,
                assignment_id=None,
                feature="reflection_intelligence_school",
                model=settings.openai_model,
                succeeded=False,
                usage=None,
            )
        except HTTPException:
            pass
        raise HTTPException(
            status_code=503,
            detail="School reflection synthesis is temporarily unavailable.",
        ) from error

    record_ai_usage(
        client,
        identity=identity,
        assignment_id=None,
        feature="reflection_intelligence_school",
        model=result.usage.model,
        succeeded=True,
        usage=result.usage,
    )
    _record_event(client, "school_plc_brief_generated", identity.school_id)
    return SchoolBriefRead(
        week_start=week_start,
        source_teacher_count=len(source_refs),
        source_submission_count=len(sources),
        brief=brief,
    )


@router.post("/school/{week_start}/handout-viewed", status_code=204)
def record_plc_handout_viewed(
    week_start: date,
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Record a content-free handout-use event; the handout itself remains client-side/transient."""
    del week_start
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    _record_event(_client(identity, settings), "plc_handout_viewed", identity.school_id)


@router.get("/usage", response_model=ReflectionUsageRead)
def reflection_intelligence_usage(
    identity: Annotated[AuthenticatedTeacher, Depends(require_platform_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> ReflectionUsageRead:
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Reporting period end must be on or after start")
    if period_end - period_start > timedelta(days=366):
        raise HTTPException(status_code=422, detail="Reflection Intelligence reporting is limited to 367 days")
    rows = _source_rows(
        _client(identity, settings),
        "platform_reflection_intelligence_usage",
        {"target_start": period_start.isoformat(), "target_end": period_end.isoformat()},
    )
    if not rows:
        return ReflectionUsageRead(period_start=period_start, period_end=period_end)
    try:
        return ReflectionUsageRead.model_validate(rows[0])
    except ValidationError as error:
        raise HTTPException(
            status_code=503,
            detail="Reflection Intelligence usage reporting is invalid",
        ) from error
