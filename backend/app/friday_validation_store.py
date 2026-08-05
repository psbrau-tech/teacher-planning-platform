from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from threading import RLock
from uuid import UUID

from .validation import FridayValidationResult


@dataclass(frozen=True, slots=True)
class FridayValidationRecord:
    teacher_id: str
    assignment_id: UUID
    week_start: date
    result: FridayValidationResult
    revision: int
    validated_at: datetime


@dataclass(slots=True)
class FridayValidationStore:
    """Thread-safe pilot contract for weekly validation persistence."""

    _records: dict[tuple[str, UUID, date], FridayValidationRecord] = field(
        default_factory=dict
    )
    _lock: RLock = field(default_factory=RLock)

    def get(
        self,
        teacher_id: str,
        assignment_id: UUID,
        week_start: date,
    ) -> FridayValidationRecord | None:
        with self._lock:
            return self._records.get((teacher_id, assignment_id, week_start))

    def save(
        self,
        *,
        teacher_id: str,
        assignment_id: UUID,
        week_start: date,
        result: FridayValidationResult,
        expected_revision: int | None = None,
    ) -> FridayValidationRecord:
        key = (teacher_id, assignment_id, week_start)
        with self._lock:
            current = self._records.get(key)
            if current is not None and expected_revision != current.revision:
                raise ValueError("Friday validation revision conflict")
            if current is None and expected_revision not in (None, 0):
                raise ValueError("Friday validation does not exist")

            record = FridayValidationRecord(
                teacher_id=teacher_id,
                assignment_id=assignment_id,
                week_start=week_start,
                result=result,
                revision=(current.revision + 1) if current else 1,
                validated_at=datetime.now(UTC),
            )
            self._records[key] = record
            return record


friday_validation_store = FridayValidationStore()
