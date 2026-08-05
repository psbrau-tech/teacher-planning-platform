from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .models import MeetingPattern
from .teaching_assignments import TeachingAssignmentRecord, teaching_assignment_store

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


@router.get("", response_model=list[TeachingAssignmentRead])
def list_teaching_assignments(
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> list[TeachingAssignmentRead]:
    return [
        _to_read_model(record)
        for record in teaching_assignment_store.list_for_teacher(teacher.subject)
    ]


@router.post("", response_model=TeachingAssignmentRead, status_code=201)
def create_teaching_assignment(
    payload: TeachingAssignmentWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> TeachingAssignmentRead:
    try:
        record = teaching_assignment_store.save(
            teacher_id=teacher.subject,
            school_id=payload.school_id,
            course_name=payload.course_name,
            course_code=payload.course_code,
            curriculum_id=payload.curriculum_id,
            grade_band=payload.grade_band,
            meeting_patterns=payload.meeting_patterns,
            expected_revision=payload.expected_revision,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(record)


@router.get("/{assignment_id}", response_model=TeachingAssignmentRead)
def get_teaching_assignment(
    assignment_id: str,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> TeachingAssignmentRead:
    record = teaching_assignment_store.get(teacher.subject, assignment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Teaching assignment not found")
    return _to_read_model(record)


@router.put("/{assignment_id}", response_model=TeachingAssignmentRead)
def update_teaching_assignment(
    assignment_id: str,
    payload: TeachingAssignmentWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> TeachingAssignmentRead:
    try:
        record = teaching_assignment_store.save(
            teacher_id=teacher.subject,
            school_id=payload.school_id,
            course_name=payload.course_name,
            course_code=payload.course_code,
            curriculum_id=payload.curriculum_id,
            grade_band=payload.grade_band,
            meeting_patterns=payload.meeting_patterns,
            assignment_id=assignment_id,
            expected_revision=payload.expected_revision,
        )
    except ValueError as error:
        detail = str(error)
        status_code = 404 if detail == "teaching assignment not found" else 409
        raise HTTPException(status_code=status_code, detail=detail) from error
    return _to_read_model(record)
