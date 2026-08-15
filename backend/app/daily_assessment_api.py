from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import AuthenticatedTeacher, require_school_reporting_admin
from .daily_assessment_analytics import (
    ASSESSMENT_TYPE_LABELS,
    DAY_SUFFIXES,
    analyze_daily_assessment_sources,
    analyze_daily_assessment_weekly_trends,
)
from .settings import Settings, get_settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

router = APIRouter(prefix="/api/v1/assessment-analytics", tags=["assessment-analytics"])


class AssessmentTypeCount(BaseModel):
    key: str
    label: str
    count: int


class WeekdayAssessmentCount(BaseModel):
    weekday: str
    count: int


class WeeklyAssessmentTrendRead(BaseModel):
    week_start: date
    submitted_course_weeks: int
    distinct_teachers: int
    daily_assessment_entries: int
    cfu_entries: int
    evidence_entries: int
    assessment_types: list[AssessmentTypeCount]


class DailyAssessmentAnalyticsRead(BaseModel):
    period_start: date
    period_end: date
    submitted_course_weeks: int
    distinct_teachers: int
    daily_assessment_entries: int
    cfu_entries: int
    evidence_entries: int
    assessment_types: list[AssessmentTypeCount]
    weekday_entries: list[WeekdayAssessmentCount]
    weekly_trends: list[WeeklyAssessmentTrendRead]
    source_scope: str = "immutable-submitted-lesson-plans"
    classification_method: str = "deterministic-keyword-v1"
    interpretation: str = "planned-formative-assessment-signals-only"
    evaluation: str = "none"


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Authenticated access token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _records(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Assessment analytics returned invalid data")
    return [cast(dict[str, Any], row) for row in payload if isinstance(row, dict)]


def _source_rows(
    client: SupabaseRestClient,
    *,
    period_start: date,
    period_end: date,
    school_id: str,
) -> list[dict[str, Any]]:
    try:
        payload = client.request(
            "POST",
            "rpc/school_daily_assessment_source",
            payload={
                "target_start": period_start.isoformat(),
                "target_end": period_end.isoformat(),
                "target_school_id": school_id,
            },
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(
                status_code=403,
                detail="Daily assessment analytics are not authorized",
            ) from error
        if error.status_code in {400, 409, 422}:
            raise HTTPException(
                status_code=409,
                detail="Daily assessment analytics source was rejected",
            ) from error
        raise HTTPException(
            status_code=503,
            detail="Daily assessment analytics are unavailable",
        ) from error
    return _records(payload)


def _type_counts(type_counts: dict[str, int]) -> list[AssessmentTypeCount]:
    return [
        AssessmentTypeCount(key=key, label=ASSESSMENT_TYPE_LABELS[key], count=count)
        for key, count in sorted(
            type_counts.items(),
            key=lambda item: (-item[1], ASSESSMENT_TYPE_LABELS[item[0]]),
        )
        if count > 0
    ]


@router.get("/school", response_model=DailyAssessmentAnalyticsRead)
def school_daily_assessment_analytics(
    identity: Annotated[AuthenticatedTeacher, Depends(require_school_reporting_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
    period_start: Annotated[date, Query()],
    period_end: Annotated[date, Query()],
) -> DailyAssessmentAnalyticsRead:
    """Summarize planned daily formative-assessment types from submitted lesson plans."""
    if identity.school_id is None:
        raise HTTPException(status_code=503, detail="Governed school context is unavailable")
    if period_end < period_start:
        raise HTTPException(
            status_code=422,
            detail="Reporting period end must be on or after start",
        )
    if period_end - period_start > timedelta(days=366):
        raise HTTPException(status_code=422, detail="Assessment analytics are limited to 367 days")

    source_rows = _source_rows(
        _client(identity, settings),
        period_start=period_start,
        period_end=period_end,
        school_id=identity.school_id,
    )
    analysis = analyze_daily_assessment_sources(source_rows)
    weekly_analysis = analyze_daily_assessment_weekly_trends(source_rows)
    type_counts = cast(dict[str, int], analysis["type_counts"])
    weekday_counts = cast(dict[str, int], analysis["weekday_counts"])

    weekday_entries = [
        WeekdayAssessmentCount(weekday=label, count=weekday_counts.get(label, 0))
        for _, label in DAY_SUFFIXES
    ]
    weekly_trends = [
        WeeklyAssessmentTrendRead(
            week_start=cast(date, item["week_start"]),
            submitted_course_weeks=cast(int, item["submitted_course_weeks"]),
            distinct_teachers=cast(int, item["distinct_teachers"]),
            daily_assessment_entries=cast(int, item["daily_assessment_entries"]),
            cfu_entries=cast(int, item["cfu_entries"]),
            evidence_entries=cast(int, item["evidence_entries"]),
            assessment_types=_type_counts(cast(dict[str, int], item["type_counts"])),
        )
        for item in weekly_analysis
    ]

    return DailyAssessmentAnalyticsRead(
        period_start=period_start,
        period_end=period_end,
        submitted_course_weeks=cast(int, analysis["submitted_course_weeks"]),
        distinct_teachers=cast(int, analysis["distinct_teachers"]),
        daily_assessment_entries=cast(int, analysis["daily_assessment_entries"]),
        cfu_entries=cast(int, analysis["cfu_entries"]),
        evidence_entries=cast(int, analysis["evidence_entries"]),
        assessment_types=_type_counts(type_counts),
        weekday_entries=weekday_entries,
        weekly_trends=weekly_trends,
    )
