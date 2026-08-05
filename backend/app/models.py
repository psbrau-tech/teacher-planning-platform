from __future__ import annotations

from datetime import date, time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ScheduleType(StrEnum):
    PERIOD = "period"
    BLOCK = "block"
    CUSTOM = "custom"


class LessonStatus(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    MODIFIED = "modified"
    MISSED = "missed"
    SKIPPED = "skipped"


class MeetingPattern(BaseModel):
    schedule_type: ScheduleType
    weekdays: list[int] = Field(min_length=1, description="ISO weekday values 1-7")
    start_time: time
    end_time: time
    effective_start: date
    effective_end: date
    rotation_label: str | None = None

    @model_validator(mode="after")
    def validate_pattern(self) -> MeetingPattern:
        if any(day < 1 or day > 7 for day in self.weekdays):
            raise ValueError("weekdays must contain ISO values from 1 through 7")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be later than start_time")
        if self.effective_end < self.effective_start:
            raise ValueError("effective_end must not precede effective_start")
        return self


class TeachingAssignmentCreate(BaseModel):
    teacher_id: UUID
    school_id: UUID
    course_name: str = Field(min_length=1, max_length=120)
    course_code: str | None = Field(default=None, max_length=40)
    curriculum_id: UUID
    grade_band: str | None = Field(default=None, max_length=40)
    meeting_patterns: list[MeetingPattern] = Field(min_length=1)


class CurriculumLesson(BaseModel):
    id: UUID
    curriculum_id: UUID
    sequence: int = Field(ge=1)
    unit_title: str
    lesson_title: str
    estimated_minutes: int = Field(gt=0)
    standards: list[str] = []
    learning_target: str
    know: list[str] = []
    understand: list[str] = []
    do: list[str] = []
    assessment: str | None = None
    resources: list[str] = []
    can_split: bool = True
    requires_special_resource: str | None = None


class ScheduleException(BaseModel):
    date: date
    assignment_id: UUID | None = None
    kind: Literal[
        "holiday",
        "testing",
        "assembly",
        "rally",
        "weather",
        "teacher_absence",
        "shortened_day",
        "other",
    ]
    instructional_minutes: int = Field(default=0, ge=0)
    note: str | None = None


class WeeklyPlanRequest(BaseModel):
    assignment_id: UUID
    week_start: date


class PlannedLesson(BaseModel):
    assignment_id: UUID
    curriculum_lesson_id: UUID
    date: date
    planned_minutes: int = Field(gt=0)
    segment_number: int = Field(ge=1)
    status: LessonStatus = LessonStatus.PLANNED
    note: str | None = None


class ValidationUpdate(BaseModel):
    status: LessonStatus
    reason: str | None = None
    teacher_note: str | None = None
    carry_forward: bool = False

    @model_validator(mode="after")
    def validate_status(self) -> ValidationUpdate:
        if self.status == LessonStatus.MISSED and not self.reason:
            raise ValueError("reason is required when a lesson is missed")
        if self.status in {LessonStatus.COMPLETED, LessonStatus.SKIPPED} and self.carry_forward:
            raise ValueError("completed or skipped lessons cannot be carried forward")
        return self
