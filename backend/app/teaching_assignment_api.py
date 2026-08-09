from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .models import MeetingPattern
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseTeachingAssignmentStore
from .supabase_rest import SupabaseRestClient, SupabaseRestError
from .teaching_assignments import (
    TeachingAssignmentRecord,
    TeachingAssignmentStore,
    teaching_assignment_store,
)

router = APIRouter(prefix="/api/v1/teaching-assignments", tags=["teacher"])


class TeachingAssignmentWrite(BaseModel):
    school_id: str = Field(min_length=1)
    course_name: str = Field(min_length=1, max_length=120)
    course_code: str | None = Field(default=None, max_length=40)
    curriculum_id: str = Field(min_length=1)
    grade_band: str | None = Field(default=None, max_length=40)
    meeting_patterns: list[MeetingPattern] = Field(min_length=1)
    expected_revision: int | None = Field(default=None, ge=0)


class TeachingAssignmentRead(BaseModel):
    id: str
    teacher_id: str
    school_id: str
    course_name: str
    course_code: str | None
    curriculum_id: str
    grade_band: str | None
    meeting_patterns: list[MeetingPattern]
    revision: int
    updated_at: str


def _to_read_model(record: TeachingAssignmentRecord) -> TeachingAssignmentRead:
    return TeachingAssignmentRead(
        id=record.id,
        teacher_id=record.teacher_id,
        school_id=record.school_id,
        course_name=record.course_name,
        course_code=record.course_code,
        curriculum_id=record.curriculum_id,
        grade_band=record.grade_band,
        meeting_patterns=list(record.meeting_patterns),
        revision=record.revision,
        updated_at=record.updated_at.isoformat(),
    )


def _store_for(
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> TeachingAssignmentStore | SupabaseTeachingAssignmentStore:
    if teacher.access_token is None:
        return teaching_assignment_store
    return SupabaseTeachingAssignmentStore(
        client=SupabaseRestClient.from_settings(
            settings,
            access_token=teacher.access_token,
        ),
        authenticated_teacher_id=teacher.subject,
    )


def _school_id(payload_school_id: str, teacher: AuthenticatedTeacher) -> str:
    if teacher.school_id is None:
        return payload_school_id
    if payload_school_id != teacher.school_id:
        raise HTTPException(
            status_code=403,
            detail="Teaching assignments must remain within the governed pilot school",
        )
    return teacher.school_id


@router.get("", response_model=list[TeachingAssignmentRead])
def list_teaching_assignments(
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[TeachingAssignmentRead]:
    try:
        records = _store_for(teacher, settings).list_for_teacher(teacher.subject)
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    return [_to_read_model(record) for record in records]


@router.post("", response_model=TeachingAssignmentRead, status_code=201)
def create_teaching_assignment(
    payload: TeachingAssignmentWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TeachingAssignmentRead:
    try:
        record = _store_for(teacher, settings).save(
            teacher_id=teacher.subject,
            school_id=_school_id(payload.school_id, teacher),
            course_name=payload.course_name,
            course_code=payload.course_code,
            curriculum_id=payload.curriculum_id,
            grade_band=payload.grade_band,
            meeting_patterns=payload.meeting_patterns,
            expected_revision=payload.expected_revision,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(record)


@router.get("/{assignment_id}", response_model=TeachingAssignmentRead)
def get_teaching_assignment(
    assignment_id: str,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TeachingAssignmentRead:
    try:
        record = _store_for(teacher, settings).get(teacher.subject, assignment_id)
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if record is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")
    return _to_read_model(record)


@router.put("/{assignment_id}", response_model=TeachingAssignmentRead)
def update_teaching_assignment(
    assignment_id: str,
    payload: TeachingAssignmentWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TeachingAssignmentRead:
    try:
        record = _store_for(teacher, settings).save(
            teacher_id=teacher.subject,
            school_id=_school_id(payload.school_id, teacher),
            course_name=payload.course_name,
            course_code=payload.course_code,
            curriculum_id=payload.curriculum_id,
            grade_band=payload.grade_band,
            meeting_patterns=payload.meeting_patterns,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        detail = str(error)
        status_code = 404 if detail == "teaching assignment not found" else 409
        raise HTTPException(status_code=status_code, detail=detail) from error
    return _to_read_model(record)


@router.delete("/{assignment_id}", status_code=204)
def archive_teaching_assignment(
    assignment_id: str,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    """Remove a course from active teacher planning while preserving its history."""
    if teacher.access_token is None:
        try:
            teaching_assignment_store.archive(teacher.subject, assignment_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return Response(status_code=204)

    client = SupabaseRestClient.from_settings(settings, access_token=teacher.access_token)
    try:
        rows = client.request(
            "PATCH",
            "teaching_assignments",
            params={
                "id": f"eq.{assignment_id}",
                "teacher_id": f"eq.{teacher.subject}",
                "is_active": "eq.true",
            },
            payload={"is_active": False},
            prefer="return=representation",
        )
    except SupabaseRestError as error:
        if error.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Pilot data access was denied") from error
        raise HTTPException(status_code=503, detail="Course removal is unavailable") from error
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")
    return Response(status_code=204)