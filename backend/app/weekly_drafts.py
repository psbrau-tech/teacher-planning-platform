from dataclasses import dataclass, field
from datetime import date, datetime, timezone
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


@dataclass(slots=True)
class WeeklyDraftStore:
    """Thread-safe pilot store with optimistic revision checks.

    Supabase persistence will replace this implementation without changing
    the API contract used by the teacher workflow.
    """

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
                updated_at=datetime.now(timezone.utc),
            )
            self._drafts[key] = draft
            return draft


weekly_draft_store = WeeklyDraftStore()
