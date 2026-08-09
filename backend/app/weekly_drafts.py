from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from threading import RLock
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class WeeklyDraft:
    id: str
    teacher_id: str
    assignment_id: str
    week_start: date
    content: dict[str, str]
    revision: int
    updated_at: datetime
    is_draft: bool = True
    submitted_at: datetime | None = None

    @property
    def submission_status(self) -> str:
        if not self.is_draft and self.submitted_at is not None:
            return "submitted"
        if self.submitted_at is not None:
            return "revised_after_submission"
        return "not_submitted"


@dataclass(slots=True)
class WeeklyDraftStore:
    """Thread-safe pilot store with optimistic revision and submission checks."""

    _drafts: dict[tuple[str, str, date], WeeklyDraft] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def get(self, teacher_id: str, assignment_id: str, week_start: date) -> WeeklyDraft | None:
        with self._lock:
            return self._drafts.get((teacher_id, assignment_id, week_start))

    def save(
        self,
        *,
        teacher_id: str,
        assignment_id: str,
        week_start: date,
        content: dict[str, str],
        expected_revision: int | None = None,
    ) -> WeeklyDraft:
        key = (teacher_id, assignment_id, week_start)
        with self._lock:
            current = self._drafts.get(key)
            if current is not None and expected_revision != current.revision:
                raise ValueError("weekly draft revision conflict")
            if current is None and expected_revision not in (None, 0):
                raise ValueError("weekly draft does not exist")

            draft = WeeklyDraft(
                id=current.id if current else str(uuid4()),
                teacher_id=teacher_id,
                assignment_id=assignment_id,
                week_start=week_start,
                content=dict(content),
                revision=(current.revision + 1) if current else 1,
                updated_at=datetime.now(UTC),
                is_draft=True,
                submitted_at=current.submitted_at if current else None,
            )
            self._drafts[key] = draft
            return draft

    def submit(
        self,
        *,
        teacher_id: str,
        assignment_id: str,
        week_start: date,
        expected_revision: int,
    ) -> WeeklyDraft:
        key = (teacher_id, assignment_id, week_start)
        with self._lock:
            current = self._drafts.get(key)
            if current is None:
                raise ValueError("weekly draft does not exist")
            if expected_revision != current.revision:
                raise ValueError("weekly draft revision conflict")
            submitted = WeeklyDraft(
                id=current.id,
                teacher_id=current.teacher_id,
                assignment_id=current.assignment_id,
                week_start=current.week_start,
                content=dict(current.content),
                revision=current.revision,
                updated_at=datetime.now(UTC),
                is_draft=False,
                submitted_at=datetime.now(UTC),
            )
            self._drafts[key] = submitted
            return submitted


weekly_draft_store = WeeklyDraftStore()
