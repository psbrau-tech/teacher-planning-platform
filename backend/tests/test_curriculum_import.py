import pytest

from app.curriculum_import import (
    PACING_ASSESSMENT_MAX,
    PACING_LEARNING_TARGETS_MAX,
    PACING_LESSON_TITLE_MAX,
    PACING_UNIT_TITLE_MAX,
    CurriculumLessonImport,
    validate_curriculum_import,
)


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
            ),
        ]
    )

    assert [lesson.sequence for lesson in lessons] == [1, 2]
    assert lessons[0].estimated_minutes is None
    assert lessons[1].estimated_minutes == 90
    assert lessons[1].standards == ("JROTC-LET1-L1",)
    assert lessons[1].can_split is False


def test_curriculum_import_allows_schedule_derived_minutes() -> None:
    lessons = validate_curriculum_import(
        [CurriculumLessonImport(1, "Drill", "Stationary movements")]
    )

    assert lessons[0].estimated_minutes is None


def test_curriculum_import_rejects_invalid_optional_duration() -> None:
    with pytest.raises(ValueError, match="when provided"):
        validate_curriculum_import(
            [CurriculumLessonImport(1, "Unit", "Lesson A", estimated_minutes=0)]
        )


def test_curriculum_import_rejects_duplicate_sequences() -> None:
    with pytest.raises(ValueError, match="unique"):
        validate_curriculum_import(
            [
                CurriculumLessonImport(1, "Unit", "Lesson A"),
                CurriculumLessonImport(1, "Unit", "Lesson B"),
            ]
        )


def test_curriculum_import_rejects_missing_required_values() -> None:
    with pytest.raises(ValueError, match="lesson title"):
        validate_curriculum_import([CurriculumLessonImport(1, "Unit", " ")])


def test_curriculum_import_accepts_values_at_pacing_character_limits() -> None:
    lesson = CurriculumLessonImport(
        1,
        "U" * PACING_UNIT_TITLE_MAX,
        "L" * PACING_LESSON_TITLE_MAX,
        learning_targets=("T" * PACING_LEARNING_TARGETS_MAX,),
        assessment="A" * PACING_ASSESSMENT_MAX,
    )

    assert validate_curriculum_import([lesson]) == (lesson,)


@pytest.mark.parametrize(
    ("lesson", "message"),
    [
        (
            CurriculumLessonImport(
                1,
                "U" * (PACING_UNIT_TITLE_MAX + 1),
                "Lesson",
            ),
            "Unit / Topic",
        ),
        (
            CurriculumLessonImport(
                2,
                "Unit",
                "L" * (PACING_LESSON_TITLE_MAX + 1),
            ),
            "Lesson / Focus",
        ),
        (
            CurriculumLessonImport(
                3,
                "Unit",
                "Lesson",
                learning_targets=("T" * (PACING_LEARNING_TARGETS_MAX + 1),),
            ),
            "Learning Target",
        ),
        (
            CurriculumLessonImport(
                4,
                "Unit",
                "Lesson",
                assessment="A" * (PACING_ASSESSMENT_MAX + 1),
            ),
            "Assessment / Evidence",
        ),
    ],
)
def test_curriculum_import_rejects_values_over_pacing_character_limits(
    lesson: CurriculumLessonImport,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_curriculum_import([lesson])
