from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, cast
from uuid import UUID

from .friday_validation_store import FridayValidationRecord
from .models import LessonStatus, MeetingPattern, ScheduleType
from .supabase_rest import SupabaseRestClient, SupabaseRestError
from .teaching_assignments import TeachingAssignmentRecord
from .validation import FridayValidationResult, ValidatedLessonRecord
from .weekly_drafts import WeeklyDraft

JsonRecord = dict[str, Any]


class PersistenceError(RuntimeError):
    """Normalized persistence failure suitable for an API response."""

    def __init__(self, detail: str, *, status_code: int) -> None:
        super().__init__(detail)
        self.status_code = status_code


def _records(payload: object) -> list[JsonRecord]:
    if not isinstance(payload, list):
        raise PersistenceError("Supabase returned an invalid data response", status_code=503)
    return [cast(JsonRecord, item) for item in payload if isinstance(item, dict)]


def _required_text(record: JsonRecord, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise PersistenceError(f"Supabase response is missing {key}", status_code=503)
    return value


def _optional_text(record: JsonRecord, key: str) -> str | None:
    value = record.get(key)
    return value if isinstance(value, str) and value else None


def _required_int(record: JsonRecord, key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise PersistenceError(f"Supabase response is missing {key}", status_code=503)
    return value


def _parse_date(value: object, *, key: str) -> date:
    if not isinstance(value, str):
        raise PersistenceError(f"Supabase response is missing {key}", status_code=503)
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise PersistenceError(f"Supabase returned an invalid {key}", status_code=503) from error


def _parse_time(value: object, *, key: str) -> time:
    if not isinstance(value, str):
        raise PersistenceError(f"Supabase response is missing {key}", status_code=503)
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise PersistenceError(f"Supabase returned an invalid {key}", status_code=503) from error


def _parse_datetime(value: object, *, key: str) -> datetime:
    if not isinstance(value, str):
        raise PersistenceError(f"Supabase response is missing {key}", status_code=503)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise PersistenceError(f"Supabase returned an invalid {key}", status_code=503) from error


def _translate_rest_error(error: SupabaseRestError, operation: str) -> PersistenceError:
    if error.status_code in {401, 403}:
        return PersistenceError("Pilot data access was denied", status_code=403)
    if error.status_code in {400, 409, 422}:
        return PersistenceError(f"{operation} was rejected by pilot data rules", status_code=409)
    return PersistenceError("Pilot data service is unavailable", status_code=503)


def _schedule_pattern_type(schedule_type: ScheduleType) -> str:
    return {
        ScheduleType.PERIOD: "daily_period",
        ScheduleType.BLOCK: "daily_block",
        ScheduleType.CUSTOM: "custom",
    }[schedule_type]


def _schedule_type(pattern_type: str) -> ScheduleType:
    if pattern_type == "daily_period":
        return ScheduleType.PERIOD
    if pattern_type in {"daily_block", "alternating_ab"}:
        return ScheduleType.BLOCK
    return ScheduleType.CUSTOM


def _instructional_minutes(pattern: MeetingPattern) -> int:
    reference = date(2000, 1, 1)
    starts_at = datetime.combine(reference, pattern.start_time)
    ends_at = datetime.combine(reference, pattern.end_time)
    return int((ends_at - starts_at).total_seconds() // 60)


def _meeting_pattern_payload(
    assignment_id: str,
    pattern: MeetingPattern,
) -> dict[str, object]:
    return {
        "teaching_assignment_id": assignment_id,
        "pattern_type": _schedule_pattern_type(pattern.schedule_type),
        "label": pattern.rotation_label or pattern.schedule_type.value.title(),
        "weekdays": list(pattern.weekdays),
        "cycle_day": pattern.rotation_label,
        "starts_at": pattern.start_time.isoformat(),
        "ends_at": pattern.end_time.isoformat(),
        "instructional_minutes": _instructional_minutes(pattern),
        "effective_from": pattern.effective_start.isoformat(),
        "effective_to": pattern.effective_end.isoformat(),
        "metadata": {"source_schedule_type": pattern.schedule_type.value},
    }


@dataclass(frozen=True, slots=True)
class SupabaseTeachingAssignmentStore:
    client: SupabaseRestClient
    authenticated_teacher_id: str

    def _assert_teacher(self, teacher_id: str) -> None:
        if teacher_id != self.authenticated_teacher_id:
            raise PersistenceError("Pilot data access was denied", status_code=403)

    def _patterns(self, assignment_id: str) -> tuple[MeetingPattern, ...]:
        try:
            rows = _records(
                self.client.request(
                    "GET",
                    "meeting_patterns",
                    params={
                        "teaching_assignment_id": f"eq.{assignment_id}",
                        "select": (
                            "pattern_type,label,weekdays,starts_at,ends_at,"
                            "effective_from,effective_to"
                        ),
                        "order": "effective_from.asc,starts_at.asc",
                    },
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Teaching assignment schedule load") from error

        patterns: list[MeetingPattern] = []
        for row in rows:
            weekdays_value = row.get("weekdays")
            if not isinstance(weekdays_value, list) or not all(
                isinstance(item, int) and not isinstance(item, bool) for item in weekdays_value
            ):
                raise PersistenceError(
                    "Supabase returned invalid meeting pattern weekdays",
                    status_code=503,
                )
            patterns.append(
                MeetingPattern(
                    schedule_type=_schedule_type(_required_text(row, "pattern_type")),
                    weekdays=cast(list[int], weekdays_value),
                    start_time=_parse_time(row.get("starts_at"), key="starts_at"),
                    end_time=_parse_time(row.get("ends_at"), key="ends_at"),
                    effective_start=_parse_date(
                        row.get("effective_from"),
                        key="effective_from",
                    ),
                    effective_end=_parse_date(row.get("effective_to"), key="effective_to"),
                    rotation_label=_optional_text(row, "label"),
                )
            )
        return tuple(patterns)

    def _record(self, row: JsonRecord) -> TeachingAssignmentRecord:
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
            curriculum_id=_required_text(row, "curriculum_id"),
            grade_band=grade_band,
            meeting_patterns=self._patterns(assignment_id),
            revision=_required_int(row, "revision"),
            updated_at=_parse_datetime(row.get("updated_at"), key="updated_at"),
        )

    def list_for_teacher(self, teacher_id: str) -> tuple[TeachingAssignmentRecord, ...]:
        self._assert_teacher(teacher_id)
        try:
            rows = _records(
                self.client.request(
                    "GET",
                    "teaching_assignments",
                    params={
                        "teacher_id": f"eq.{teacher_id}",
                        "is_active": "eq.true",
                        "select": (
                            "id,teacher_id,school_id,course_name,course_code,curriculum_id,"
                            "grade_levels,revision,updated_at"
                        ),
                        "order": "course_name.asc,id.asc",
                    },
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Teaching assignment load") from error
        return tuple(self._record(row) for row in rows)

    def get(self, teacher_id: str, assignment_id: str) -> TeachingAssignmentRecord | None:
        self._assert_teacher(teacher_id)
        try:
            rows = _records(
                self.client.request(
                    "GET",
                    "teaching_assignments",
                    params={
                        "id": f"eq.{assignment_id}",
                        "teacher_id": f"eq.{teacher_id}",
                        "select": (
                            "id,teacher_id,school_id,course_name,course_code,curriculum_id,"
                            "grade_levels,revision,updated_at"
                        ),
                        "limit": "1",
                    },
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Teaching assignment load") from error
        return self._record(rows[0]) if rows else None

    def _active_academic_year(self, school_id: str) -> JsonRecord:
        try:
            rows = _records(
                self.client.request(
                    "GET",
                    "academic_years",
                    params={
                        "school_id": f"eq.{school_id}",
                        "is_active": "eq.true",
                        "select": "id,starts_on,ends_on",
                        "order": "starts_on.desc",
                        "limit": "1",
                    },
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Academic year load") from error
        if not rows:
            raise PersistenceError(
                "No active academic year is configured for this pilot school",
                status_code=409,
            )
        return rows[0]

    def _replace_patterns(
        self,
        assignment_id: str,
        meeting_patterns: list[MeetingPattern],
        *,
        restore_patterns: tuple[MeetingPattern, ...] = (),
    ) -> None:
        try:
            self.client.request(
                "DELETE",
                "meeting_patterns",
                params={"teaching_assignment_id": f"eq.{assignment_id}"},
            )
            self.client.request(
                "POST",
                "meeting_patterns",
                payload=[
                    _meeting_pattern_payload(assignment_id, pattern)
                    for pattern in meeting_patterns
                ],
                prefer="return=minimal",
            )
        except SupabaseRestError as error:
            if restore_patterns:
                try:
                    self.client.request(
                        "POST",
                        "meeting_patterns",
                        payload=[
                            _meeting_pattern_payload(assignment_id, pattern)
                            for pattern in restore_patterns
                        ],
                        prefer="return=minimal",
                    )
                except SupabaseRestError:
                    pass
            raise _translate_rest_error(error, "Teaching assignment schedule save") from error

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
            "curriculum_id": curriculum_id.strip(),
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
                "starts_on": _parse_date(
                    academic_year.get("starts_on"),
                    key="starts_on",
                ).isoformat(),
                "ends_on": _parse_date(
                    academic_year.get("ends_on"),
                    key="ends_on",
                ).isoformat(),
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
                    raise PersistenceError(
                        "Teaching assignment save returned no record",
                        status_code=503,
                    )
                created_id = _required_text(rows[0], "id")
                try:
                    self._replace_patterns(created_id, meeting_patterns)
                except (PersistenceError, ValueError):
                    try:
                        self.client.request(
                            "DELETE",
                            "teaching_assignments",
                            params={"id": f"eq.{created_id}"},
                        )
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


@dataclass(frozen=True, slots=True)
class SupabaseWeeklyDraftStore:
    client: SupabaseRestClient
    authenticated_teacher_id: str

    def _assert_teacher(self, teacher_id: str) -> None:
        if teacher_id != self.authenticated_teacher_id:
            raise PersistenceError("Pilot data access was denied", status_code=403)

    def _record(self, row: JsonRecord) -> WeeklyDraft:
        source_data = row.get("source_data")
        if not isinstance(source_data, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in source_data.items()
        ):
            raise PersistenceError(
                "Supabase returned invalid weekly draft content",
                status_code=503,
            )
        return WeeklyDraft(
            id=_required_text(row, "id"),
            teacher_id=self.authenticated_teacher_id,
            assignment_id=_required_text(row, "teaching_assignment_id"),
            week_start=_parse_date(row.get("week_start"), key="week_start"),
            content=cast(dict[str, str], source_data),
            revision=_required_int(row, "revision"),
            updated_at=_parse_datetime(row.get("updated_at"), key="updated_at"),
        )

    def get(self, teacher_id: str, assignment_id: str, week_start: date) -> WeeklyDraft | None:
        self._assert_teacher(teacher_id)
        try:
            rows = _records(
                self.client.request(
                    "GET",
                    "weekly_plan_snapshots",
                    params={
                        "teaching_assignment_id": f"eq.{assignment_id}",
                        "week_start": f"eq.{week_start.isoformat()}",
                        "select": (
                            "id,teaching_assignment_id,week_start,source_data,revision,updated_at"
                        ),
                        "limit": "1",
                    },
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Weekly draft load") from error
        return self._record(rows[0]) if rows else None

    def save(
        self,
        *,
        teacher_id: str,
        assignment_id: str,
        week_start: date,
        content: dict[str, str],
        expected_revision: int | None = None,
    ) -> WeeklyDraft:
        self._assert_teacher(teacher_id)
        for required_field, label in (
            ("literacy_standards", "Literacy Standards"),
            ("act_preparation", "ACT Preparation"),
        ):
            if not content.get(required_field, "").strip():
                raise ValueError(f"{label} is required")

        current = self.get(teacher_id, assignment_id, week_start)
        if current is not None and expected_revision != current.revision:
            raise ValueError("weekly draft revision conflict")
        if current is None and expected_revision not in (None, 0):
            raise ValueError("weekly draft does not exist")

        if current is None:
            payload: dict[str, object] = {
                "teaching_assignment_id": assignment_id,
                "week_start": week_start.isoformat(),
                "week_end": (week_start + timedelta(days=6)).isoformat(),
                "source_data": dict(content),
                "updated_by": teacher_id,
                "is_draft": True,
            }
            try:
                rows = _records(
                    self.client.request(
                        "POST",
                        "weekly_plan_snapshots",
                        payload=payload,
                        prefer="return=representation",
                    )
                )
            except SupabaseRestError as error:
                raise _translate_rest_error(error, "Weekly draft save") from error
        else:
            try:
                rows = _records(
                    self.client.request(
                        "PATCH",
                        "weekly_plan_snapshots",
                        params={
                            "id": f"eq.{current.id}",
                            "revision": f"eq.{current.revision}",
                        },
                        payload={
                            "source_data": dict(content),
                            "updated_by": teacher_id,
                            "is_draft": True,
                        },
                        prefer="return=representation",
                    )
                )
            except SupabaseRestError as error:
                raise _translate_rest_error(error, "Weekly draft save") from error
            if not rows:
                raise ValueError("weekly draft revision conflict")

        if not rows:
            raise PersistenceError("Weekly draft save returned no record", status_code=503)
        return self._record(rows[0])


def _serialize_validation(result: FridayValidationResult) -> dict[str, object]:
    return {
        "validated": [
            {
                "scheduled_lesson_id": str(record.scheduled_lesson_id),
                "assignment_id": str(record.assignment_id),
                "curriculum_lesson_id": str(record.curriculum_lesson_id),
                "date": record.date.isoformat(),
                "sequence": record.sequence,
                "status": record.status.value,
                "reason": record.reason,
                "teacher_note": record.teacher_note,
                "carry_forward": record.carry_forward,
            }
            for record in result.validated
        ],
        "carry_forward_curriculum_lesson_ids": [
            str(item) for item in result.carry_forward_curriculum_lesson_ids
        ],
        "completed_count": result.completed_count,
        "modified_count": result.modified_count,
        "missed_count": result.missed_count,
        "skipped_count": result.skipped_count,
    }


def _parse_validation(payload: object) -> FridayValidationResult:
    if not isinstance(payload, dict):
        raise PersistenceError(
            "Supabase returned invalid Friday validation content",
            status_code=503,
        )
    data = cast(JsonRecord, payload)
    validated_value = data.get("validated")
    if not isinstance(validated_value, list):
        raise PersistenceError(
            "Supabase returned invalid Friday validation lessons",
            status_code=503,
        )

    validated: list[ValidatedLessonRecord] = []
    for item in validated_value:
        if not isinstance(item, dict):
            raise PersistenceError(
                "Supabase returned invalid Friday validation lesson",
                status_code=503,
            )
        record = cast(JsonRecord, item)
        carry_forward = record.get("carry_forward")
        if not isinstance(carry_forward, bool):
            raise PersistenceError(
                "Supabase returned invalid carry-forward state",
                status_code=503,
            )
        validated.append(
            ValidatedLessonRecord(
                scheduled_lesson_id=UUID(_required_text(record, "scheduled_lesson_id")),
                assignment_id=UUID(_required_text(record, "assignment_id")),
                curriculum_lesson_id=UUID(_required_text(record, "curriculum_lesson_id")),
                date=_parse_date(record.get("date"), key="date"),
                sequence=_required_int(record, "sequence"),
                status=LessonStatus(_required_text(record, "status")),
                reason=_optional_text(record, "reason"),
                teacher_note=_optional_text(record, "teacher_note"),
                carry_forward=carry_forward,
            )
        )

    carry_value = data.get("carry_forward_curriculum_lesson_ids")
    if not isinstance(carry_value, list) or not all(isinstance(item, str) for item in carry_value):
        raise PersistenceError(
            "Supabase returned invalid carry-forward lesson identifiers",
            status_code=503,
        )

    return FridayValidationResult(
        validated=tuple(validated),
        carry_forward_curriculum_lesson_ids=tuple(UUID(item) for item in carry_value),
        completed_count=_required_int(data, "completed_count"),
        modified_count=_required_int(data, "modified_count"),
        missed_count=_required_int(data, "missed_count"),
        skipped_count=_required_int(data, "skipped_count"),
    )


@dataclass(frozen=True, slots=True)
class SupabaseFridayValidationStore:
    client: SupabaseRestClient
    authenticated_teacher_id: str

    def _assert_teacher(self, teacher_id: str) -> None:
        if teacher_id != self.authenticated_teacher_id:
            raise PersistenceError("Pilot data access was denied", status_code=403)

    def _record(self, row: JsonRecord) -> FridayValidationRecord:
        return FridayValidationRecord(
            teacher_id=self.authenticated_teacher_id,
            assignment_id=UUID(_required_text(row, "teaching_assignment_id")),
            week_start=_parse_date(row.get("week_start"), key="week_start"),
            result=_parse_validation(row.get("result_data")),
            revision=_required_int(row, "revision"),
            validated_at=_parse_datetime(row.get("validated_at"), key="validated_at"),
        )

    def get(
        self,
        teacher_id: str,
        assignment_id: UUID,
        week_start: date,
    ) -> FridayValidationRecord | None:
        self._assert_teacher(teacher_id)
        try:
            rows = _records(
                self.client.request(
                    "GET",
                    "friday_validation_snapshots",
                    params={
                        "teaching_assignment_id": f"eq.{assignment_id}",
                        "week_start": f"eq.{week_start.isoformat()}",
                        "select": (
                            "teaching_assignment_id,week_start,result_data,revision,validated_at"
                        ),
                        "limit": "1",
                    },
                )
            )
        except SupabaseRestError as error:
            raise _translate_rest_error(error, "Friday validation load") from error
        return self._record(rows[0]) if rows else None

    def save(
        self,
        *,
        teacher_id: str,
        assignment_id: UUID,
        week_start: date,
        result: FridayValidationResult,
        expected_revision: int | None = None,
    ) -> FridayValidationRecord:
        self._assert_teacher(teacher_id)
        current = self.get(teacher_id, assignment_id, week_start)
        if current is not None and expected_revision != current.revision:
            raise ValueError("Friday validation revision conflict")
        if current is None and expected_revision not in (None, 0):
            raise ValueError("Friday validation does not exist")

        if current is None:
            try:
                rows = _records(
                    self.client.request(
                        "POST",
                        "friday_validation_snapshots",
                        payload={
                            "teaching_assignment_id": str(assignment_id),
                            "week_start": week_start.isoformat(),
                            "result_data": _serialize_validation(result),
                            "validated_by": teacher_id,
                        },
                        prefer="return=representation",
                    )
                )
            except SupabaseRestError as error:
                raise _translate_rest_error(error, "Friday validation save") from error
        else:
            try:
                rows = _records(
                    self.client.request(
                        "PATCH",
                        "friday_validation_snapshots",
                        params={
                            "teaching_assignment_id": f"eq.{assignment_id}",
                            "week_start": f"eq.{week_start.isoformat()}",
                            "revision": f"eq.{current.revision}",
                        },
                        payload={
                            "result_data": _serialize_validation(result),
                            "validated_by": teacher_id,
                        },
                        prefer="return=representation",
                    )
                )
            except SupabaseRestError as error:
                raise _translate_rest_error(error, "Friday validation save") from error
            if not rows:
                raise ValueError("Friday validation revision conflict")

        if not rows:
            raise PersistenceError(
                "Friday validation save returned no record",
                status_code=503,
            )
        return self._record(rows[0])
