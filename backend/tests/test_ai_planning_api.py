from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app import ai_planning_api
from app.ai_openai import AiServiceError, AiUsage, StructuredAiResult
from app.auth import AuthenticatedTeacher, require_teacher
from app.main import app
from app.standards_api import (
    AssignmentStandardsRead,
    StandardCourseRead,
    StandardEntryRead,
    StandardSourceRead,
)

client = TestClient(app)
TEACHER_ID = uuid4()
SCHOOL_ID = uuid4()
ASSIGNMENT_ID = uuid4()
SOURCE_ID = uuid4()
COURSE_ID = uuid4()
SNAPSHOT_ID = uuid4()
ENTRY_ID = uuid4()
USAGE_ID = uuid4()
LESSON_ID = uuid4()


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, object]] = []

    def request(
        self,
        method: str,
        resource: str,
        *,
        params=None,
        payload=None,
        prefer=None,
    ) -> object:
        self.calls.append((method, resource, params, payload))
        if resource == "teaching_assignments":
            return [
                {
                    "id": str(ASSIGNMENT_ID),
                    "school_id": str(SCHOOL_ID),
                    "course_name": "Army JROTC LET 2",
                    "course_code": "JROTC-2",
                    "grade_levels": ["9-12"],
                }
            ]
        if resource == "scheduled_lessons":
            return [
                {
                    "lesson_id": str(LESSON_ID),
                    "school_date": "2026-08-11",
                    "planned_minutes": 50,
                    "sequence_position": "1.0010",
                }
            ]
        if resource == "lessons":
            return [{"id": str(LESSON_ID), "title": "Leadership styles and team roles"}]
        if resource == "act_reference_entries":
            return [{
                "reference_code": "CLR 401",
                "domain": "Reading",
                "category": "CLR",
                "score_range": "20-23",
                "exact_text": "Locate important details in somewhat challenging passages",
                "source_id": str(SOURCE_ID),
                "snapshot_id": str(SNAPSHOT_ID),
            }]
        if resource == "ai_usage_events":
            return [{"id": str(USAGE_ID)}]
        if resource == "rpc/record_ai_suggestion_decision" and isinstance(payload, dict):
            return payload.get("target_decision")
        return []


def _identity() -> AuthenticatedTeacher:
    return AuthenticatedTeacher(
        subject=str(TEACHER_ID),
        email="teacher@example.test",
        display_name="Synthetic Teacher",
        school_id=str(SCHOOL_ID),
        roles=frozenset({"teacher"}),
    )


def _standards(*, selected: bool = True) -> AssignmentStandardsRead:
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
        selected_entry_ids=[ENTRY_ID] if selected else [],
    )


def _suggestion_result() -> StructuredAiResult:
    return StructuredAiResult(
        data={
            "learning_targets": "Compare leadership styles.",
            "know": "Leadership vocabulary.",
            "understand": "Leadership choices affect team performance.",
            "do_statement": "Analyze a leadership scenario.",
            "activities": "Scenario discussion and team-role analysis.",
            "assessments": "Exit ticket.",
            "resources": "JROTC curriculum and scenario cards.",
            "literacy_standards": "Read and cite evidence from an informational scenario.",
            "recommended_act_reference_ids": ["CLR 401"],
            "act_instructional_application": "Identify main ideas and supporting evidence.",
            "alignment_summary": "Suggestions align to the selected Army JROTC lesson.",
        },
        usage=AiUsage(
            model="gpt-5.6-terra",
            provider_response_id="resp_synthetic",
            input_tokens=1000,
            cached_tokens=200,
            cache_write_tokens=100,
            output_tokens=100,
            estimated_cost_usd=Decimal("0.002890"),
            retry_count=0,
        ),
    )


def _install(monkeypatch, fake: FakeClient, *, selected: bool = True) -> None:
    monkeypatch.setattr(ai_planning_api, "_client", lambda identity, settings: fake)
    monkeypatch.setattr(
        ai_planning_api,
        "get_assignment_standards",
        lambda assignment_id, week_start, identity, settings: _standards(
            selected=selected
        ),
    )
    app.dependency_overrides[require_teacher] = _identity


def test_ai_planning_requires_teacher_identity() -> None:
    response = client.post(
        f"/api/v1/ai/planning/{ASSIGNMENT_ID}/week/2026-08-10",
        json={},
    )

    assert response.status_code == 401


def test_ai_planning_context_is_server_grounded_and_excludes_identity_pii(
    monkeypatch,
) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    captured: list[dict[str, object]] = []

    def suggest(**kwargs):
        captured.append(kwargs)
        return _suggestion_result()

    monkeypatch.setattr(ai_planning_api, "request_structured_response", suggest)
    try:
        response = client.post(
            f"/api/v1/ai/planning/{ASSIGNMENT_ID}/week/2026-08-10",
            json={
                "unit_topic": "Leadership",
                "learning_targets": "Teacher current target",
                "tuesday": "Leadership scenario discussion",
            },
        )
    finally:
        app.dependency_overrides.pop(require_teacher, None)

    assert response.status_code == 200
    body = response.json()
    assert body["usage_event_id"] == str(USAGE_ID)
    assert body["suggestions"]["learning_targets"] == "Compare leadership styles."
    assert "CLR 401" in body["suggestions"]["act_preparation"]
    assert "Locate important details" in body["suggestions"]["act_preparation"]

    context = captured[0]["context"]
    assert context["selected_authoritative_standards"] == [
        {"code": "U2C1L1", "text": "Leadership styles and team roles"}
    ]
    assert context["scheduled_lessons"] == [
        {
            "date": "2026-08-11",
            "lesson_title": "Leadership styles and team roles",
            "planned_minutes": 50,
        }
    ]
    assert context["current_teacher_plan"]["learning_targets"] == "Teacher current target"
    assert context["approved_act_reference_candidates"][0]["reference_id"] == "CLR 401"
    serialized = str(context).lower()
    assert "teacher@example.test" not in serialized
    assert "synthetic teacher" not in serialized
    assert "student" not in serialized

    usage_call = next(call for call in fake.calls if call[1] == "ai_usage_events")
    assert usage_call[3]["succeeded"] is True
    assert usage_call[3]["provider_response_id"] == "resp_synthetic"
    assert usage_call[3]["cache_write_tokens"] == 100


def test_ai_planning_requires_at_least_one_selected_approved_standard(
    monkeypatch,
) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake, selected=False)

    def fail_if_called(**kwargs):
        raise AssertionError("AI must not be called")

    monkeypatch.setattr(ai_planning_api, "request_structured_response", fail_if_called)
    try:
        response = client.post(
            f"/api/v1/ai/planning/{ASSIGNMENT_ID}/week/2026-08-10",
            json={},
        )
    finally:
        app.dependency_overrides.pop(require_teacher, None)

    assert response.status_code == 409
    assert "Select at least one approved standard" in response.json()["detail"]


def test_ai_failure_is_logged_and_existing_plan_is_not_mutated(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)

    def fail(**kwargs):
        raise AiServiceError("AI planning assistance is temporarily unavailable")

    monkeypatch.setattr(ai_planning_api, "request_structured_response", fail)
    try:
        response = client.post(
            f"/api/v1/ai/planning/{ASSIGNMENT_ID}/week/2026-08-10",
            json={"learning_targets": "Teacher-authored target remains unchanged."},
        )
    finally:
        app.dependency_overrides.pop(require_teacher, None)

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]
    usage_call = next(call for call in fake.calls if call[1] == "ai_usage_events")
    assert usage_call[3]["succeeded"] is False
    assert usage_call[3]["input_tokens"] == 0
    assert not any(call[1] == "weekly_plan_snapshots" for call in fake.calls)


def test_teacher_decision_uses_narrow_rpc(monkeypatch) -> None:
    fake = FakeClient()
    _install(monkeypatch, fake)
    try:
        response = client.put(
            f"/api/v1/ai/usage/{USAGE_ID}/decision/learning_targets",
            json={"decision": "edited"},
        )
    finally:
        app.dependency_overrides.pop(require_teacher, None)

    assert response.status_code == 200
    assert response.json() == {
        "usage_event_id": str(USAGE_ID),
        "field_key": "learning_targets",
        "decision": "edited",
    }
    rpc_call = fake.calls[-1]
    assert rpc_call[1] == "rpc/record_ai_suggestion_decision"
    assert rpc_call[3] == {
        "target_event_id": str(USAGE_ID),
        "target_field_key": "learning_targets",
        "target_decision": "edited",
    }
