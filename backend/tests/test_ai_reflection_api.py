from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import ai_reflection_api
from app.ai_openai import AiServiceError, AiUsage, StructuredAiResult
from app.auth import AuthenticatedTeacher
from app.settings import Settings
from app.standards_api import (
    AssignmentStandardsRead,
    StandardCourseRead,
    StandardEntryRead,
    StandardSourceRead,
)

TEACHER_ID = uuid4()
SCHOOL_ID = uuid4()
ASSIGNMENT_ID = uuid4()
SOURCE_ID = uuid4()
COURSE_ID = uuid4()
SNAPSHOT_ID = uuid4()
ENTRY_ID = uuid4()
USAGE_ID = uuid4()


class FakeValidation:
    def model_dump(self, *, mode: str) -> dict[str, object]:
        assert mode == "json"
        return {
            "revision": 1,
            "completed_count": 1,
            "modified_count": 0,
            "missed_count": 1,
            "skipped_count": 0,
            "validated": [
                {
                    "date": "2026-08-11",
                    "status": "completed",
                    "teacher_note": "Lesson completed as planned.",
                    "carry_forward": False,
                },
                {
                    "date": "2026-08-13",
                    "status": "missed",
                    "teacher_note": "Synthetic rally",
                    "carry_forward": True,
                },
            ],
        }


def _identity() -> AuthenticatedTeacher:
    return AuthenticatedTeacher(
        subject=str(TEACHER_ID),
        email="teacher@example.test",
        display_name="Synthetic Teacher",
        school_id=str(SCHOOL_ID),
        roles=frozenset({"teacher"}),
    )


def _standards() -> AssignmentStandardsRead:
    return AssignmentStandardsRead(
        assignment_id=ASSIGNMENT_ID,
        week_start="2026-08-10",
        mapped=True,
        source=StandardSourceRead(
            id=SOURCE_ID,
            source_key="army_jrotc_v12",
            authority="U.S. Army Cadet Command",
            title="Army JROTC Curriculum Guide",
            edition="JROTC Curriculum Guide v12 (25 JUN 2025)",
            landing_url="https://usarmyjrotc.army.mil/jsocc-course-documents/",
            snapshot_id=SNAPSHOT_ID,
            source_version="v12",
            retrieved_at="2026-08-07T20:00:00+00:00",
            resolved_document_url=(
                "https://usarmyjrotc.army.mil/wp-content/uploads/2025/07/"
                "JROTC-Curriculum-Guide-25JUN25-4.docx"
            ),
        ),
        course=StandardCourseRead(
            id=COURSE_ID,
            source_id=SOURCE_ID,
            course_key="army_jrotc_let_2",
            display_name="Army JROTC LET 2",
            source_course_code="LET 2",
            grade_band="9-12",
            is_pilot_allowed=True,
        ),
        standards=[
            StandardEntryRead(
                id=ENTRY_ID,
                code="U2C1L1",
                text="Leadership styles and team roles",
                parent_code=None,
                strand=None,
                sequence=1,
            )
        ],
        selected_entry_ids=[ENTRY_ID],
    )


def _result() -> StructuredAiResult:
    return StructuredAiResult(
        data={
            "weekly_reflection": (
                "Leadership instruction was completed as planned; map-reading instruction "
                "was interrupted and should carry forward. Prioritize the missed map lesson "
                "before adding new content next week."
            )
        },
        usage=AiUsage(
            model="gpt-5.6-terra",
            provider_response_id="resp_reflection_synthetic",
            input_tokens=700,
            cached_tokens=100,
            cache_write_tokens=0,
            output_tokens=80,
            estimated_cost_usd=Decimal("0.002180"),
            retry_count=0,
        ),
    )


def _install_context(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_reflection_api,
        "get_weekly_draft",
        lambda assignment_id, week_start, identity, settings: SimpleNamespace(
            content={
                "unit_topic": "Leadership and Map Reading",
                "tuesday": "Leadership styles and team roles",
                "thursday": "Map symbols and terrain features",
            },
            revision=4,
        ),
    )
    monkeypatch.setattr(
        ai_reflection_api,
        "get_friday_validation",
        lambda assignment_id, week_start, identity, settings: FakeValidation(),
    )
    monkeypatch.setattr(
        ai_reflection_api,
        "get_assignment_standards",
        lambda assignment_id, week_start, identity, settings: _standards(),
    )
    monkeypatch.setattr(ai_reflection_api, "_client", lambda identity, settings: object())


def test_reflection_context_uses_saved_plan_and_finalized_validation(monkeypatch) -> None:
    _install_context(monkeypatch)
    captured: list[dict[str, object]] = []
    logged: list[dict[str, object]] = []

    def suggest(**kwargs):
        captured.append(kwargs)
        return _result()

    monkeypatch.setattr(ai_reflection_api, "request_structured_response", suggest)
    monkeypatch.setattr(
        ai_reflection_api,
        "record_ai_usage",
        lambda client, **kwargs: logged.append(kwargs) or USAGE_ID,
    )

    response = ai_reflection_api.suggest_weekly_reflection(
        ASSIGNMENT_ID,
        __import__("datetime").date(2026, 8, 10),
        _identity(),
        Settings(openai_api_key="synthetic-key"),
    )

    assert response.usage_event_id == USAGE_ID
    context = captured[0]["context"]
    assert context["saved_weekly_plan_revision"] == 4
    assert context["finalized_friday_validation"]["missed_count"] == 1
    assert context["selected_authoritative_standards"] == [
        {"code": "U2C1L1", "text": "Leadership styles and team roles"}
    ]
    serialized = str(context).lower()
    assert "teacher@example.test" not in serialized
    assert "synthetic teacher" not in serialized
    assert logged[0]["feature"] == "weekly_reflection"
    assert logged[0]["succeeded"] is True


def test_reflection_ai_failure_is_logged_without_mutating_saved_records(monkeypatch) -> None:
    _install_context(monkeypatch)
    logged: list[dict[str, object]] = []

    def fail(**kwargs):
        raise AiServiceError("AI reflection assistance is temporarily unavailable")

    monkeypatch.setattr(ai_reflection_api, "request_structured_response", fail)
    monkeypatch.setattr(
        ai_reflection_api,
        "record_ai_usage",
        lambda client, **kwargs: logged.append(kwargs) or USAGE_ID,
    )

    with pytest.raises(HTTPException) as captured:
        ai_reflection_api.suggest_weekly_reflection(
            ASSIGNMENT_ID,
            __import__("datetime").date(2026, 8, 10),
            _identity(),
            Settings(openai_api_key="synthetic-key"),
        )

    assert captured.value.status_code == 503
    assert logged[0]["succeeded"] is False
    assert logged[0]["feature"] == "weekly_reflection"
