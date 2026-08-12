from dataclasses import dataclass

PACING_UNIT_TITLE_MAX = 300
PACING_LESSON_TITLE_MAX = 1000
PACING_LEARNING_TARGETS_MAX = 3000
PACING_ASSESSMENT_MAX = 2000


@dataclass(frozen=True, slots=True)
class CurriculumLessonImport:
    sequence: int
    unit_title: str
    lesson_title: str
    estimated_minutes: int | None = None
    standards: tuple[str, ...] = ()
    learning_targets: tuple[str, ...] = ()
    assessment: str = ""
    can_split: bool = True

    def validate(self) -> None:
        if self.sequence < 1:
            raise ValueError("sequence must be at least 1")
        if not self.unit_title.strip():
            raise ValueError("unit title is required")
        if not self.lesson_title.strip():
            raise ValueError("lesson title is required")
        if len(self.unit_title) > PACING_UNIT_TITLE_MAX:
            raise ValueError(
                f"lesson {self.sequence} Unit / Topic exceeds the "
                f"{PACING_UNIT_TITLE_MAX} character limit"
            )
        if len(self.lesson_title) > PACING_LESSON_TITLE_MAX:
            raise ValueError(
                f"lesson {self.sequence} Lesson / Focus exceeds the "
                f"{PACING_LESSON_TITLE_MAX} character limit"
            )
        learning_targets_length = sum(len(target) for target in self.learning_targets)
        if self.learning_targets:
            learning_targets_length += len(self.learning_targets) - 1
        if learning_targets_length > PACING_LEARNING_TARGETS_MAX:
            raise ValueError(
                f"lesson {self.sequence} Learning Target(s) exceeds the "
                f"{PACING_LEARNING_TARGETS_MAX} character limit"
            )
        if len(self.assessment) > PACING_ASSESSMENT_MAX:
            raise ValueError(
                f"lesson {self.sequence} Assessment / Evidence exceeds the "
                f"{PACING_ASSESSMENT_MAX} character limit"
            )
        if self.estimated_minutes is not None and self.estimated_minutes < 1:
            raise ValueError("estimated minutes must be at least 1 when provided")


def validate_curriculum_import(
    rows: list[CurriculumLessonImport],
) -> tuple[CurriculumLessonImport, ...]:
    """Validate and normalize a teacher-owned curriculum import before persistence."""
    for row in rows:
        row.validate()
    sequences = [row.sequence for row in rows]
    if len(sequences) != len(set(sequences)):
        raise ValueError("lesson sequence values must be unique")
    return tuple(sorted(rows, key=lambda row: row.sequence))
