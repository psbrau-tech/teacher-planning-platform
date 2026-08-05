from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .auth import AuthenticatedTeacher, require_teacher
from .settings import Settings, get_settings
from .supabase_persistence import PersistenceError, SupabaseWeeklyDraftStore
from .supabase_rest import SupabaseRestClient
from .weekly_drafts import WeeklyDraft, WeeklyDraftStore, weekly_draft_store

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


def _store_for(
    teacher: AuthenticatedTeacher,
    settings: Settings,
) -> WeeklyDraftStore | SupabaseWeeklyDraftStore:
    if teacher.access_token is None:
        return weekly_draft_store
    return SupabaseWeeklyDraftStore(
        client=SupabaseRestClient.from_settings(
            settings,
            access_token=teacher.access_token,
        ),
        authenticated_teacher_id=teacher.subject,
    )


@router.get("", response_model=WeeklyDraftRead)
def get_weekly_draft(
    assignment_id: Annotated[str, Query(min_length=1)],
    week_start: date,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    try:
        draft = _store_for(teacher, settings).get(
            teacher.subject,
            assignment_id,
            week_start,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    if draft is None:
        raise HTTPException(status_code=404, detail="Weekly draft not found")
    return _to_read_model(draft)


@router.put("", response_model=WeeklyDraftRead)
def save_weekly_draft(
    payload: WeeklyDraftWrite,
    teacher: Annotated[AuthenticatedTeacher, Depends(require_teacher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WeeklyDraftRead:
    try:
        draft = _store_for(teacher, settings).save(
            teacher_id=teacher.subject,
            assignment_id=payload.assignment_id,
            week_start=payload.week_start,
            content=payload.content,
            expected_revision=payload.expected_revision,
        )
    except PersistenceError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _to_read_model(draft)
