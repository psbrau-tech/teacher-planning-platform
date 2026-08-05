from datetime import date

import pytest

from app.weekly_drafts import WeeklyDraftStore


def test_create_and_update_weekly_draft() -> None:
    store = WeeklyDraftStore()
    week_start = date(2026, 8, 10)

    created = store.save(
        teacher_id="teacher-1",
        assignment_id="let-1",
        week_start=week_start,
        content={"unit_topic": "Foundations"},
    )
    updated = store.save(
        teacher_id="teacher-1",
        assignment_id="let-1",
        week_start=week_start,
        content={"unit_topic": "Leadership Foundations"},
        expected_revision=created.revision,
    )

    assert created.revision == 1
    assert updated.id == created.id
    assert updated.revision == 2
    assert updated.content["unit_topic"] == "Leadership Foundations"
    assert store.get("teacher-1", "let-1", week_start) == updated


def test_rejects_stale_weekly_draft_revision() -> None:
    store = WeeklyDraftStore()
    week_start = date(2026, 8, 10)
    store.save(
        teacher_id="teacher-1",
        assignment_id="let-1",
        week_start=week_start,
        content={"unit_topic": "Foundations"},
    )

    with pytest.raises(ValueError, match="revision conflict"):
        store.save(
            teacher_id="teacher-1",
            assignment_id="let-1",
            week_start=week_start,
            content={"unit_topic": "Stale overwrite"},
            expected_revision=0,
        )


def test_keeps_assignments_and_teachers_isolated() -> None:
    store = WeeklyDraftStore()
    week_start = date(2026, 8, 10)
    store.save(
        teacher_id="teacher-1",
        assignment_id="let-1",
        week_start=week_start,
        content={"unit_topic": "LET 1"},
    )

    assert store.get("teacher-1", "let-2", week_start) is None
    assert store.get("teacher-2", "let-1", week_start) is None
