from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from .models import MeetingPattern


@dataclass(frozen=True, slots=True)
class TeachingAssignmentRecord:
    id: str
    teacher_id: str
    school_id: str
    course_name: str
    course_code: str | None
    curriculum_id: str
    grade_band: str | None
    meeting_patterns: tuple[MeetingPattern, ...]
    revision: int
    updated_at: datetime


@dataclass(slots=True)
class TeachingAssignmentStore:
    """Teacher-scoped pilot store with optimistic revision protection."""

    _assignments: dict[str, TeachingAssignmentRecord] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def list_for_teacher(self, teacher_id: str) -> tuple[TeachingAssignmentRecord, ...]:
        with self._lock:
            records = [
                record
                for record in self._assignments.values()
                if record.teacher_id == teacher_id
            ]
        return tuple(sorted(records, key=lambda record: (record.course_name, record.id)))

    def get(self, teacher_id: str, assignment_id: str) -> TeachingAssignmentRecord | None:
        with self._lock:
            record = self._assignments.get(assignment_id)
            if record is None or record.teacher_id != teacher_id:
                return None
            return record

    def save(
        self,
        *,
        teacher_id: str,
        school_id: str,
        course_name: str,
        course_code: str | None,
        curriculum_id: str,
        grade_band: str | None,
        meeting_patterns: list[MeetingPattern],
        assignment_id: str | None = None,
        expected_revision: int | None = None,
    ) -> TeachingAssignmentRecord:
        normalized_name = course_name.strip()
        if not normalized_name:
            raise ValueError("course name is required")
        if not meeting_patterns:
            raise ValueError("at least one meeting pattern is required")

        with self._lock:
            current = self._assignments.get(assignment_id) if assignment_id else None
            if current is not None and current.teacher_id != teacher_id:
                raise ValueError("teaching assignment not found")
            if current is not None and expected_revision != current.revision:
                raise ValueError("teaching assignment revision conflict")
            if current is None and assignment_id is not None:
                raise ValueError("teaching assignment not found")
            if current is None and expected_revision not in (None, 0):
                raise ValueError("teaching assignment does not exist")

            record = TeachingAssignmentRecord(
                id=current.id if current else str(uuid4()),
                teacher_id=teacher_id,
                school_id=school_id.strip(),
                course_name=normalized_name,
                course_code=course_code.strip() if course_code else None,
                curriculum_id=curriculum_id.strip(),
                grade_band=grade_band.strip() if grade_band else None,
                meeting_patterns=tuple(meeting_patterns),
                revision=(current.revision + 1) if current else 1,
                updated_at=datetime.now(UTC),
            )
            self._assignments[record.id] = record
            return record


teaching_assignment_store = TeachingAssignmentStore()
