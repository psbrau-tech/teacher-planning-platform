from __future__ import annotations

from .models import MeetingPattern
from .supabase_persistence import (
    PersistenceError,
    SupabaseTeachingAssignmentStore,
    _optional_text,
    _parse_date,
    _parse_datetime,
    _records,
    _required_int,
    _required_text,
    _translate_rest_error,
)
from .supabase_rest import SupabaseRestError
from .teaching_assignments import TeachingAssignmentRecord


class ProgressiveSupabaseTeachingAssignmentStore(SupabaseTeachingAssignmentStore):
    """Teaching-assignment persistence that permits Course Setup before curriculum attachment."""

    def _record(self, row: dict[str, object]) -> TeachingAssignmentRecord:
        assignment_id = _required_text(row, "id")
        grade_levels = row.get("grade_levels")
        grade_band = None
        if isinstance(grade_levels, list):
            normalized = [item for item in grade_levels if isinstance(item, str) and item]
            grade_band = ", ".join(normalized) or None
        return TeachingAssignmentRecord(
            id=assignment_id,
            teacher_id=_required_text(row, "teacher_id"),
            school_id=_required_text(row, "school_id"),
            course_name=_required_text(row, "course_name"),
            course_code=_optional_text(row, "course_code"),
            curriculum_id=_optional_text(row, "curriculum_id"),
            grade_band=grade_band,
            meeting_patterns=self._patterns(assignment_id),
            revision=_required_int(row, "revision"),
            updated_at=_parse_datetime(row.get("updated_at"), key="updated_at"),
        )

    def save(
        self,
        *,
        teacher_id: str,
        school_id: str,
        course_name: str,
        course_code: str | None,
        curriculum_id: str | None,
        grade_band: str | None,
        meeting_patterns: list[MeetingPattern],
        assignment_id: str | None = None,
        expected_revision: int | None = None,
    ) -> TeachingAssignmentRecord:
        self._assert_teacher(teacher_id)
        normalized_name = course_name.strip()
        if not normalized_name:
            raise ValueError("course name is required")
        if not meeting_patterns:
            raise ValueError("at least one meeting pattern is required")

        current = self.get(teacher_id, assignment_id) if assignment_id else None
        if current is not None and expected_revision != current.revision:
            raise ValueError("teaching assignment revision conflict")
        if current is None and assignment_id is not None:
            raise ValueError("teaching assignment not found")
        if current is None and expected_revision not in (None, 0):
            raise ValueError("teaching assignment does not exist")

        base_payload: dict[str, object] = {
            "school_id": school_id.strip(),
            "curriculum_id": curriculum_id.strip() if curriculum_id else None,
            "course_name": normalized_name,
            "course_code": course_code.strip() if course_code else None,
            "grade_levels": [grade_band.strip()] if grade_band and grade_band.strip() else [],
        }

        if current is None:
            academic_year = self._active_academic_year(school_id)
            create_payload = {
                **base_payload,
                "teacher_id": teacher_id,
                "academic_year_id": _required_text(academic_year, "id"),
                "starts_on": _parse_date(academic_year.get("starts_on"), key="starts_on").isoformat(),
                "ends_on": _parse_date(academic_year.get("ends_on"), key="ends_on").isoformat(),
                "is_active": True,
            }
            try:
                rows = _records(
                    self.client.request(
                        "POST",
                        "teaching_assignments",
                        payload=create_payload,
                        prefer="return=representation",
                    )
                )
                if not rows:
                    raise PersistenceError("Teaching assignment save returned no record", status_code=503)
                created_id = _required_text(rows[0], "id")
                try:
                    self._replace_patterns(created_id, meeting_patterns)
                except (PersistenceError, ValueError):
                    try:
                        self.client.request("DELETE", "teaching_assignments", params={"id": f"eq.{created_id}"})
                    except SupabaseRestError:
                        pass
                    raise
                created = self.get(teacher_id, created_id)
                if created is None:
                    raise PersistenceError(
                        "Teaching assignment could not be reopened after save",
                        status_code=503,
                    )
                return created
            except SupabaseRestError as error:
                raise _translate_rest_error(error, "Teaching assignment save") from error

        try:
            rows = _records(
                self.client.request(
                    "PATCH",
                    "teaching_assignments",
                    params={
                        "id": f"eq.{current.id}",
                        "teacher_id": f"eq.{teacher_id}",
                        "revision": f"eq.{current.revision}",
                    },
                    payload=base_payload,
                    prefer="return=representation",
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Teaching assignment save") from error
        if not rows:
            raise ValueError("teaching assignment revision conflict")

        self._replace_patterns(
            current.id,
            meeting_patterns,
            restore_patterns=current.meeting_patterns,
        )
        updated = self.get(teacher_id, current.id)
        if updated is None:
            raise PersistenceError(
                "Teaching assignment could not be reopened after save",
                status_code=503,
            )
        return updated
