import pytest

from app.curriculum_import import CurriculumLessonImport, validate_curriculum_import


def test_curriculum_import_is_sorted_and_preserves_instructional_metadata() -> None:
    lessons = validate_curriculum_import(
        [
            CurriculumLessonImport(
                sequence=2,
                unit_title="Leadership",
                lesson_title="Leadership styles",
                estimated_minutes=90,
                standards=("JROTC-LET1-L1",),
                learning_targets=("Compare leadership styles",),
                can_split=False,
            ),
            CurriculumLessonImport(
                sequence=1,
                unit_title="Foundations",
                lesson_title="Program orientation",
                estimated_minutes=50,
            ),
        ]
    )

    assert [lesson.sequence for lesson in lessons] == [1, 2]
    assert lessons[1].standards == ("JROTC-LET1-L1",)
    assert lessons[1].can_split is False


def test_curriculum_import_rejects_duplicate_sequences() -> None:
    with pytest.raises(ValueError, match="unique"):
        validate_curriculum_import(
            [
                CurriculumLessonImport(1, "Unit", "Lesson A", 50),
                CurriculumLessonImport(1, "Unit", "Lesson B", 50),
            ]
        )


def test_curriculum_import_rejects_missing_required_values() -> None:
    with pytest.raises(ValueError, match="lesson title"):
        validate_curriculum_import([CurriculumLessonImport(1, "Unit", " ", 50)])
