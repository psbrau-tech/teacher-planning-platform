from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .weekly_drafts import WeeklyDraft, weekly_draft_store

router = APIRouter(prefix="/api/v1/weekly-drafts", tags=["planning"])


class WeeklyDraftWrite(BaseModel):
    assignment_id: str = Field(min_length=1)
    week_start: date
    content: dict[str, str]
    expected_revision: int | None = Field(default=None, ge=0)


class WeeklyDraftRead(BaseModel):
    id: str
    teacher_id: str
    assignment_id: str
    week_start: date
    content: dict[str, str]
    revision: int
    updated_at: str


def _to_read_model(draft: WeeklyDraft) -> WeeklyDraftRead:
    return WeeklyDraftRead(
        id=draft.id,
        teacher_id=draft.teacher_id,
        assignment_id=draft.assignment_id,
        week_start=draft.week_start,
        content=draft.content,
        revision=draft.revision,
        updated_at=draft.updated_at.isoformat(),
    )


@router.get("", response_model=WeeklyDraftRead)
def get_weekly_draft(
    assignment_id: Annotated[str, Query(min_length=1)],
    week_start: date,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> WeeklyDraftRead:
    draft = weekly_draft_store.get(teacher.subject, assignment_id, week_start)
    if draft is None:
        raise HTTPException(status_code=404, detail="Weekly draft not found")
    return _to_read_model(draft)


@router.put("", response_model=WeeklyDraftRead)
def save_weekly_draft(
    payload: WeeklyDraftWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
) -> WeeklyDraftRead:
    try:
        draft = weekly_draft_store.save(
            teacher_id=teacher.subject,
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            content=payload.content,
            expected_revision=payload.expected_revision,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(draft)
