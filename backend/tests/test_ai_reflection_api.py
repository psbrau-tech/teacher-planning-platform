from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import ai_reflection_api
from app.auth import AuthenticatedTeacher

TEACHER_ID = uuid4()
SCHOOL_ID = uuid4()
ASSIGNMENT_ID = uuid4()


def _identity() -> AuthenticatedTeacher:
    return AuthenticatedTeacher(
        subject=str(TEACHER_ID),
        email="teacher@example.test",
        display_name="Synthetic Teacher",
        school_id=str(SCHOOL_ID),
        roles=frozenset({"teacher"}),
    )


def test_ai_reflection_generation_fails_closed() -> None:
    with pytest.raises(HTTPException) as captured:
        ai_reflection_api.suggest_weekly_reflection_disabled(
            ASSIGNMENT_ID,
            date(2026, 8, 10),
            _identity(),
        )

    assert captured.value.status_code == 410
    detail = str(captured.value.detail)
    assert "AI reflection assistance is disabled" in detail
    assert "must be authored by the teacher" in detail
