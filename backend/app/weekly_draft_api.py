from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

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


def _require_teacher_id(value: str | None) -> str:
    if value is None or not value.strip():
        raise HTTPException(status_code=401, detail="Teacher identity is required")
    return value.strip()


@router.get("", response_model=WeeklyDraftRead)
def get_weekly_draft(
    assignment_id: Annotated[str, Query(min_length=1)],
    week_start: date,
    teacher_id_header: Annotated[str | None, Header(alias="X-TPP-Teacher-ID")] = None,
) -> WeeklyDraftRead:
    teacher_id = _require_teacher_id(teacher_id_header)
    draft = weekly_draft_store.get(teacher_id, assignment_id, week_start)
    if draft is None:
        raise HTTPException(status_code=404, detail="Weekly draft not found")
    return _to_read_model(draft)


@router.put("", response_model=WeeklyDraftRead)
def save_weekly_draft(
    payload: WeeklyDraftWrite,
    teacher_id_header: Annotated[str | None, Header(alias="X-TPP-Teacher-ID")] = None,
) -> WeeklyDraftRead:
    teacher_id = _require_teacher_id(teacher_id_header)
    try:
        draft = weekly_draft_store.save(
            teacher_id=teacher_id,
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            content=payload.content,
            expected_revision=payload.expected_revision,
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(draft)
