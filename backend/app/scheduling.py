from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Outcome(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    MODIFIED = "modified"
    MISSED = "missed"
    NOT_NEEDED = "not_needed"


class CarryForwardAction(StrEnum):
    NONE = "none"
    CARRY_FORWARD = "carry_forward"
    SKIP = "skip"
    COMBINE = "combine"
    MANUAL_RESEQUENCE = "manual_resequence"


@dataclass(frozen=True, slots=True)
class LessonSegment:
    assignment_id: str
    lesson_id: str
    sequence_position: float
    planned_date: date
    planned_minutes: int

    def __post_init__(self) -> None:
        if self.planned_minutes <= 0:
            raise ValueError("planned_minutes must be positive")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    segment: LessonSegment
    outcome: Outcome
    carry_forward_action: CarryForwardAction = CarryForwardAction.NONE


def remaining_queue(
    segments: list[LessonSegment],
    validations: dict[tuple[str, date], ValidationResult],
) -> list[LessonSegment]:
    """Return unfinished work in deterministic curriculum order.

    Completed, modified, skipped, and not-needed segments leave the queue.
    Missed segments return to the front only when explicitly carried forward.
    Each assignment is processed independently by the caller.
    """
    pending: list[LessonSegment] = []
    for segment in segments:
        result = validations.get((segment.lesson_id, segment.planned_date))
        if result is None or result.outcome is Outcome.PLANNED:
            pending.append(segment)
            continue
        if result.outcome is Outcome.MISSED and result.carry_forward_action in {
            CarryForwardAction.CARRY_FORWARD,
            CarryForwardAction.COMBINE,
            CarryForwardAction.MANUAL_RESEQUENCE,
        }:
            pending.append(segment)
    return sorted(pending, key=lambda item: (item.sequence_position, item.planned_date))
