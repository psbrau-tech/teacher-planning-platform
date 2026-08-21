from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.models import LessonStatus, ValidationUpdate
from app.planned_lesson_api import PlannedLessonReplacement
from app.validation import ScheduledLessonRecord, apply_friday_validation

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260821180000_weekly_lesson_replacements.sql"
)
FIX_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260821194800_fix_weekly_lesson_replacement_week_start.sql"
)
SHELL = ROOT / "frontend" / "src" / "TeacherPlanningShell.tsx"
LIVE_PLANNING = ROOT / "backend" / "app" / "live_planning_api.py"
AI_PLANNING = ROOT / "backend" / "app" / "ai_planning_api.py"


def test_replacement_rpc_preserves_manual_source_and_displaced_lesson_decision() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "alter column lesson_id drop not null" in source
    assert "source_type in ('curriculum', 'manual')" in source
    assert "replacement_disposition in ('skip', 'postpone')" in source
    assert "create or replace function public.replace_weekly_scheduled_lesson" in source
    assert "Only a scheduled curriculum lesson can be replaced" in source
    assert "Reopen is unavailable after Friday validation has been finalized" in source
    assert "order by sl.school_date, sl.sequence_position, sl.segment_index" in source
    assert "ol.global_sequence > coalesce(week_max_sequence, 0)" in source
    assert "coalesce(final_minutes, target.planned_minutes)" in source
    assert "ta.teacher_id = (select auth.uid())" in source


def test_replacement_rpc_week_boundary_does_not_collide_with_snapshot_column() -> None:
    source = FIX_MIGRATION.read_text(encoding="utf-8")
    assert "target_week_start date" in source
    assert "fvs.week_start = target_week_start" in source
    assert "fvs.week_start = week_start" not in source


def test_manual_replacement_requires_teacher_to_choose_skip_or_postpone() -> None:
    with pytest.raises(ValueError, match="skip or postpone"):
        PlannedLessonReplacement(
            replacement_kind="manual",
            manual_unit_title="Leadership lab",
            manual_lesson_title="Team problem-solving exercise",
        )

    accepted = PlannedLessonReplacement(
        replacement_kind="manual",
        manual_unit_title="Leadership lab",
        manual_lesson_title="Team problem-solving exercise",
        original_disposition="postpone",
    )
    assert accepted.original_disposition == "postpone"

    with pytest.raises(ValueError, match="no more than 20 learning targets"):
        PlannedLessonReplacement(
            replacement_kind="manual",
            manual_unit_title="Leadership lab",
            manual_lesson_title="Team problem-solving exercise",
            manual_learning_targets=["target"] * 21,
            original_disposition="skip",
        )


def test_manual_class_can_be_friday_validated_without_curriculum_carry_forward() -> None:
    scheduled_id = uuid4()
    result = apply_friday_validation(
        [
            ScheduledLessonRecord(
                id=scheduled_id,
                assignment_id=uuid4(),
                curriculum_lesson_id=None,
                date=date(2026, 8, 21),
                sequence=4,
            )
        ],
        {scheduled_id: ValidationUpdate(status=LessonStatus.COMPLETED)},
    )
    assert result.validated[0].curriculum_lesson_id is None
    assert result.carry_forward_curriculum_lesson_ids == ()


def test_teacher_ui_exposes_two_clear_replacement_paths_and_boundary_notice() -> None:
    source = SHELL.read_text(encoding="utf-8")
    assert "Replace scheduled lesson" in source
    assert "Use the next pacing lesson and move the remaining sequence forward" in source
    assert "Add a manual class" in source
    assert "Replace and skip the original" in source
    assert "Insert the manual class and postpone the original" in source
    assert "Do not enter student names" in source


def test_postponed_manual_replacement_returns_to_queue_and_reaches_ai_context() -> None:
    live = LIVE_PLANNING.read_text(encoding="utf-8")
    ai = AI_PLANNING.read_text(encoding="utf-8")
    assert "def _load_postponed_lessons" in live
    assert '"replacement_disposition": "eq.postpone"' in live
    assert "postponed + [lesson for lesson in queue" in live
    assert 'if row.get("source_type") == "manual"' in ai
    assert '"source_type": "teacher_manual"' in ai
