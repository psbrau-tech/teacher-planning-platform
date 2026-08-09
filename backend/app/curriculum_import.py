from dataclasses import dataclass


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
