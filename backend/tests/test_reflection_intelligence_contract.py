import json
from datetime import date
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.reflection_intelligence import (
    ReflectionBoundaryError,
    SchoolReflectionSource,
    TeacherReflectionSource,
    parse_reflection_text,
    school_ai_context,
    teacher_ai_context,
    validate_school_brief,
)
from app.reflection_intelligence_api import _require_complete_teacher_week

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260814190000_reflection_intelligence_foundation.sql"
)
AI_POLICY_MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260814190100_ai_usage_actor_policy.sql"
)
AI_REFLECTION_API = ROOT / "backend" / "app" / "ai_reflection_api.py"
REFLECTION_API = ROOT / "backend" / "app" / "reflection_intelligence_api.py"
REFLECTION_ENGINE = ROOT / "backend" / "app" / "reflection_intelligence.py"


def reflection_json(**overrides: str) -> str:
    values = {f"reflect_{index}": f"Class-level response {index}" for index in range(1, 13)}
    values.update(overrides)
    return json.dumps(values)


class FridayStatusClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object],
    ) -> list[dict[str, object]]:
        assert method == "POST"
        assert path == "rpc/teacher_friday_submission_status"
        assert payload == {"target_week_start": "2026-08-17"}
        return self.rows


def test_teacher_recap_waits_for_every_required_class_packet() -> None:
    complete = FridayStatusClient(
        [
            {"current_week_required": True, "current_packet_submitted": True},
            {"current_week_required": True, "current_packet_submitted": True},
            {"current_week_required": False, "current_packet_submitted": False},
        ]
    )
    _require_complete_teacher_week(complete, date(2026, 8, 17))  # type: ignore[arg-type]

    incomplete = FridayStatusClient(
        [
            {"current_week_required": True, "current_packet_submitted": True},
            {"current_week_required": True, "current_packet_submitted": False},
        ]
    )
    with pytest.raises(HTTPException, match="every required class"):
        _require_complete_teacher_week(incomplete, date(2026, 8, 17))  # type: ignore[arg-type]


def test_reflection_source_is_immutable_submitted_teacher_content_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "public.weekly_plan_submissions" in source
    assert "submission_kind = 'completed_packet'" in source
    assert "public.weekly_plan_snapshots" not in source
    assert "teacher_reflection_intelligence_source" in source
    assert "join authorized a on a.actor = wps.teacher_id" in source
    assert "school_reflection_intelligence_source" in source
    assert "dense_rank() over (order by latest.teacher_id)" in source
    assert "teacher identity is not returned" in source
    assert "reflection_intelligence_events" in source
    assert "no planning text, reflection text, generated insight text" in source


def test_ai_authored_reflection_remains_fail_closed() -> None:
    source = AI_REFLECTION_API.read_text(encoding="utf-8")

    assert "AI reflection assistance is disabled" in source
    assert "must be authored by the teacher" in source
    assert "router.include_router(reflection_intelligence_router)" in source


def test_reflection_intelligence_prompts_prohibit_evaluation_and_identity_inference() -> None:
    source = REFLECTION_ENGINE.read_text(encoding="utf-8")

    assert "Do not score, rank, evaluate, judge" in source
    assert "Never infer teacher identity" in source
    assert "Never infer student identity" in source
    assert "TWO DISTINCT source_ref" in source
    assert "teacher quality" in source.lower()


def test_school_brief_requires_two_distinct_teacher_sources() -> None:
    source = REFLECTION_API.read_text(encoding="utf-8")

    assert "len(source_refs) < 2" in source
    assert "at least two distinct" in source
    assert "scope: str = \"school-aggregate\"" in source
    assert "evaluation: str = \"none\"" in source


def test_ai_usage_actor_policy_preserves_teacher_semantics() -> None:
    source = AI_POLICY_MIGRATION.read_text(encoding="utf-8")

    assert "actor_id = (select auth.uid())" in source
    assert "teacher_id = (select auth.uid())" in source
    assert "teacher_id is null" in source
    assert "school_admin" in source
    assert "platform_admin" in source


def test_parse_reflection_requires_all_twelve_teacher_responses() -> None:
    parsed = parse_reflection_text(reflection_json())
    assert list(parsed) == [f"reflect_{index}" for index in range(1, 13)]

    incomplete = json.loads(reflection_json())
    incomplete["reflect_12"] = ""
    with pytest.raises(ReflectionBoundaryError, match="incomplete"):
        parse_reflection_text(json.dumps(incomplete))


def test_reflection_preflight_rejects_common_student_specific_markers() -> None:
    with pytest.raises(ReflectionBoundaryError, match="student-specific"):
        parse_reflection_text(reflection_json(reflect_6="Student named Jordan needs intervention."))

    with pytest.raises(ReflectionBoundaryError, match="student-specific"):
        parse_reflection_text(reflection_json(reflect_7="Review the student's IEP before reteaching."))

    with pytest.raises(ReflectionBoundaryError, match="student-specific"):
        parse_reflection_text(reflection_json(reflect_8="Contact learner@example.org about enrichment."))


def test_teacher_context_contains_no_teacher_identity() -> None:
    source = TeacherReflectionSource(
        source_ref=1,
        course_name="Biology",
        week_start="2026-08-10",
        reflection_text=reflection_json(),
        submitted_at="2026-08-14T20:00:00Z",
    )
    context = teacher_ai_context([source], selected_week="2026-08-10", lookback_weeks=12)
    serialized = json.dumps(context)

    assert "teacher_id" not in serialized
    assert "teacher_name" not in serialized
    assert "email" not in serialized
    assert "Class-level response 12" in serialized


def test_school_context_uses_anonymous_source_refs_only() -> None:
    sources = [
        SchoolReflectionSource(
            source_ref=1,
            week_start="2026-08-10",
            reflection_text=reflection_json(reflect_10="Retrieval practice worked well."),
            submitted_at="2026-08-14T20:00:00Z",
        ),
        SchoolReflectionSource(
            source_ref=2,
            week_start="2026-08-10",
            reflection_text=reflection_json(reflect_10="Frequent checks for understanding worked."),
            submitted_at="2026-08-14T20:05:00Z",
        ),
    ]
    context = school_ai_context(sources, week_start="2026-08-10")
    serialized = json.dumps(context)

    assert "teacher_id" not in serialized
    assert "teacher_name" not in serialized
    assert '"source_ref": 1' in serialized
    assert '"source_ref": 2' in serialized


def test_school_brief_drops_single_source_claims_even_if_model_returns_them() -> None:
    brief = validate_school_brief(
        {
            "common_successes": [
                {
                    "theme": "Checks for understanding",
                    "evidence_summary": "Multiple teachers described useful checks.",
                    "source_refs": [1, 2],
                },
                {
                    "theme": "Single-source strategy",
                    "evidence_summary": "Only one anonymous source mentioned this.",
                    "source_refs": [1, 999],
                },
            ],
            "common_challenges": [],
            "emerging_themes": [],
            "discussion_questions": ["Which checks are easiest to reuse next week?"],
            "possible_actions": ["Share one reusable check-for-understanding routine."],
            "support_needs": [],
        },
        available_source_refs={1, 2},
    )

    assert [item.theme for item in brief.common_successes] == ["Checks for understanding"]
    assert brief.common_successes[0].source_refs == [1, 2]
