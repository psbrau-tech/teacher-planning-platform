from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Any, NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import AuthenticatedTeacher, require_teacher
from .carry_forward import lessons_for_next_week
from .models import CurriculumLesson, ScheduleException
from .planner import build_weekly_plan
from .progressive_assignment_store import ProgressiveSupabaseTeachingAssignmentStore
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseFridayValidationStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError
from .week_dates import require_monday

router = APIRouter(prefix="/api/v1/plans", tags=["planning"])


class WeeklyPlanGenerate(BaseModel):
    assignment_id: UUID
    week_start: date


class PlannedLessonRead(BaseModel):
    scheduled_lesson_id: UUID
    curriculum_lesson_id: UUID
    unit_title: str
    lesson_title: str
    lesson_date: date
    sequence: int
    planned_minutes: int
    segment_number: int
    status: str = "planned"


JsonRecord = dict[str, Any]


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise HTTPException(status_code=503, detail="Pilot data service returned invalid data")
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=503, detail=f"Pilot data response is missing {key}")
    return value


def _int(record: JsonRecord, key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise HTTPException(status_code=503, detail=f"Pilot data response is missing {key}")
    return value


def _optional_int(record: JsonRecord, key: str) -> int | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise HTTPException(status_code=503, detail=f"Pilot data response has invalid {key}")
    return value


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _date_range_filter(column: str, start: date, end: date) -> str:
    return f"({column}.gte.{start.isoformat()},{column}.lte.{end.isoformat()})"


def _client(identity: AuthenticatedTeacher, settings: Settings) -> SupabaseRestClient:
    if identity.access_token is None:
        raise HTTPException(status_code=503, detail="Supabase session token is unavailable")
    return SupabaseRestClient.from_settings(settings, access_token=identity.access_token)


def _raise_data_error(error: SupabaseRestError, operation: str) -> NoReturn:
    if error.status_code in {401, 403}:
        raise HTTPException(status_code=403, detail="Pilot data access was denied") from error
    if error.status_code in {400, 409, 422}:
        raise HTTPException(status_code=409, detail=f"{operation} was rejected") from error
    raise HTTPException(status_code=503, detail="Pilot data service is unavailable") from error


def _load_curriculum_lessons(
    client: SupabaseRestClient,
    curriculum_id: str,
) -> list[CurriculumLesson]:
    try:
        units = _records(
            client.request(
                "GET",
                "curriculum_units",
                params={
                    "curriculum_id": f"eq.{curriculum_id}",
                    "select": "id,sequence,title",
                    "order": "sequence.asc",
                },
            )
        )
        lessons: list[CurriculumLesson] = []
        global_sequence = 1
        for unit in units:
            unit_id = _text(unit, "id")
            unit_title = _text(unit, "title")
            lesson_rows = _records(
                client.request(
                    "GET",
                    "lessons",
                    params={
                        "unit_id": f"eq.{unit_id}",
                        "select": (
                            "id,title,estimated_minutes,standards,learning_targets,know,"
                            "understand,do_statement,assessments,resources,can_split"
                        ),
                        "order": "sequence.asc",
                    },
                )
            )
            for row in lesson_rows:
                learning_targets = _string_list(row.get("learning_targets"))
                can_split = row.get("can_split")
                lessons.append(
                    CurriculumLesson(
                        id=UUID(_text(row, "id")),
                        curriculum_id=UUID(curriculum_id),
                        sequence=global_sequence,
                        unit_title=unit_title,
                        lesson_title=_text(row, "title"),
                        estimated_minutes=_optional_int(row, "estimated_minutes"),
                        standards=_string_list(row.get("standards")),
                        learning_target="; ".join(learning_targets),
                        know=[value] if isinstance((value := row.get("know")), str) else [],
                        understand=(
                            [value]
                            if isinstance((value := row.get("understand")), str)
                            else []
                        ),
                        do=(
                            [value]
                            if isinstance((value := row.get("do_statement")), str)
                            else []
                        ),
                        assessment=(
                            "; ".join(_string_list(row.get("assessments"))) or None
                        ),
                        resources=_string_list(row.get("resources")),
                        can_split=can_split if isinstance(can_split, bool) else True,
                    )
                )
                global_sequence += 1
        return lessons
    except SupabaseRestError as error:
        _raise_data_error(error, "Curriculum load")


def _load_exceptions(
    client: SupabaseRestClient,
    *,
    assignment_id: UUID,
    school_id: str,
    week_start: date,
) -> list[ScheduleException]:
    week_end = week_start + timedelta(days=4)
    exceptions: list[ScheduleException] = []
    try:
        years = _records(
            client.request(
                "GET",
                "academic_years",
                params={
                    "school_id": f"eq.{school_id}",
                    "is_active": "eq.true",
                    "select": "id",
                    "limit": "1",
                },
            )
        )
        if years:
            days = _records(
                client.request(
                    "GET",
                    "calendar_days",
                    params={
                        "academic_year_id": f"eq.{_text(years[0], 'id')}",
                        "and": _date_range_filter("school_date", week_start, week_end),
                        "select": "school_date,is_instructional,event_type,event_name",
                    },
                )
            )
            for day in days:
                if day.get("is_instructional") is False:
                    exceptions.append(
                        ScheduleException(
                            date=date.fromisoformat(_text(day, "school_date")),
                            kind="other",
                            instructional_minutes=0,
                            note=(
                                day.get("event_name")
                                if isinstance(day.get("event_name"), str)
                                else None
                            ),
                        )
                    )

        assignment_exceptions = _records(
            client.request(
                "GET",
                "schedule_exceptions",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "and": _date_range_filter("exception_date", week_start, week_end),
                    "select": "exception_date,is_available,instructional_minutes,reason",
                },
            )
        )
        for item in assignment_exceptions:
            available = item.get("is_available") is True
            minutes_value = item.get("instructional_minutes")
            minutes = minutes_value if isinstance(minutes_value, int) else 0
            exceptions.append(
                ScheduleException(
                    date=date.fromisoformat(_text(item, "exception_date")),
                    assignment_id=assignment_id,
                    kind="other",
                    instructional_minutes=minutes if available else 0,
                    note=(item.get("reason") if isinstance(item.get("reason"), str) else None),
                )
            )
        return exceptions
    except (SupabaseRestError, ValueError) as error:
        if isinstance(error, SupabaseRestError):
            _raise_data_error(error, "Schedule exception load")
        raise HTTPException(status_code=503, detail="Pilot calendar data is invalid") from error


def _lesson_lookup(lessons: list[CurriculumLesson]) -> dict[UUID, CurriculumLesson]:
    return {lesson.id: lesson for lesson in lessons}


def _read_persisted_plan(
    client: SupabaseRestClient,
    *,
    assignment_id: UUID,
    week_start: date,
    lessons: list[CurriculumLesson],
) -> list[PlannedLessonRead]:
    week_end = week_start + timedelta(days=4)
    lookup = _lesson_lookup(lessons)
    try:
        rows = _records(
            client.request(
                "GET",
                "scheduled_lessons",
                params={
                    "teaching_assignment_id": f"eq.{assignment_id}",
                    "and": _date_range_filter("school_date", week_start, week_end),
                    "select": (
                        "id,lesson_id,school_date,segment_index,planned_minutes,sequence_position"
                    ),
                    "order": "school_date.asc,sequence_position.asc,segment_index.asc",
                },
            )
        )
    except SupabaseRestError as error:
        _raise_data_error(error, "Weekly plan load")

    planned: list[PlannedLessonRead] = []
    for row in rows:
        lesson_id = UUID(_text(row, "lesson_id"))
        lesson = lookup.get(lesson_id)
        if lesson is None:
            raise HTTPException(status_code=503, detail="Weekly plan references an unknown lesson")
        planned.append(
            PlannedLessonRead(
                scheduled_lesson_id=UUID(_text(row, "id")),
                curriculum_lesson_id=lesson_id,
                unit_title=lesson.unit_title,
                lesson_title=lesson.lesson_title,
                lesson_date=date.fromisoformat(_text(row, "school_date")),
                sequence=lesson.sequence,
                planned_minutes=_int(row, "planned_minutes"),
                segment_number=_int(row, "segment_index"),
            )
        )
    return planned


def _require_curriculum(curriculum_id: str | None) -> str:
    if not curriculum_id:
        raise HTTPException(
            status_code=409,
            detail="Complete Course Setup Step 2 by adding Curriculum & Pacing before building a week.",
        )
    return curriculum_id


@router.get("", response_model=list[PlannedLessonRead])
def get_weekly_plan(
    assignment_id: UUID,
    week_start: Annotated[date, Query()],
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[PlannedLessonRead]:
    require_monday(week_start)
    client = _client(identity, settings)
    assignment_store = ProgressiveSupabaseTeachingAssignmentStore(client, identity.subject)
    try:
        assignment = assignment_store.get(identity.subject, str(assignment_id))
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")
    lessons = _load_curriculum_lessons(client, _require_curriculum(assignment.curriculum_id))
    return _read_persisted_plan(
        client,
        assignment_id=assignment_id,
        week_start=week_start,
        lessons=lessons,
    )


@router.post("/generate", response_model=list[PlannedLessonRead])
def generate_weekly_plan(
    payload: WeeklyPlanGenerate,
    identity: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[PlannedLessonRead]:
    require_monday(payload.week_start)
    client = _client(identity, settings)
    assignment_store = ProgressiveSupabaseTeachingAssignmentStore(client, identity.subject)
    try:
        assignment = assignment_store.get(identity.subject, str(payload.assignment_id))
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if assignment is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")

    lessons = _load_curriculum_lessons(client, _require_curriculum(assignment.curriculum_id))
    validation_store = SupabaseFridayValidationStore(client, identity.subject)
    try:
        previous_validation = validation_store.get(
            identity.subject,
            payload.assignment_id,
            payload.week_start - timedelta(days=7),
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    queue = lessons_for_next_week(
        lessons,
        previous_validation.result if previous_validation is not None else None,
    )
    exceptions = _load_exceptions(
        client,
        assignment_id=payload.assignment_id,
        school_id=assignment.school_id,
        week_start=payload.week_start,
    )
    try:
        generated = build_weekly_plan(
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            patterns=list(assignment.meeting_patterns),
            lessons=queue,
            exceptions=exceptions,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    week_end = payload.week_start + timedelta(days=4)
    try:
        client.request(
            "DELETE",
            "scheduled_lessons",
            params={
                "teaching_assignment_id": f"eq.{payload.assignment_id}",
                "and": _date_range_filter("school_date", payload.week_start, week_end),
            },
        )
        if generated:
            sequence_by_id = {lesson.id: lesson.sequence for lesson in lessons}
            client.request(
                "POST",
                "scheduled_lessons",
                payload=[
                    {
                        "teaching_assignment_id": str(item.assignment_id),
                        "lesson_id": str(item.curriculum_lesson_id),
                        "school_date": item.date.isoformat(),
                        "segment_index": item.segment_number,
                        "planned_minutes": item.planned_minutes,
                        "sequence_position": (
                            sequence_by_id[item.curriculum_lesson_id]
                            + item.segment_number / 1000
                        ),
                        "is_teacher_override": False,
                    }
                    for item in generated
                ],
                prefer="return=minimal",
            )
    except SupabaseRestError as error:
        _raise_data_error(error, "Weekly plan save")

    return _read_persisted_plan(
        client,
        assignment_id=payload.assignment_id,
        week_start=payload.week_start,
        lessons=lessons,
    )
