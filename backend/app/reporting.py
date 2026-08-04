from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Iterable


class AiFeature(StrEnum):
    LEARNING_TARGET = "learning_target"
    KUD = "know_understand_do"
    CHECK_FOR_UNDERSTANDING = "check_for_understanding"
    REFLECTION = "weekly_reflection"
    SHORTENED_CLASS = "shortened_class_adjustment"
    PDF_NARRATIVE = "pdf_narrative"


@dataclass(frozen=True, slots=True)
class AiUsageRecord:
    organization_id: str
    school_id: str
    teacher_id: str
    assignment_id: str | None
    feature: AiFeature
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    estimated_cost_usd: Decimal = Decimal("0")
    succeeded: bool = True
    retry_count: int = 0
    accepted_by_teacher: bool | None = None


@dataclass(frozen=True, slots=True)
class AdminUsageEvent:
    teacher_id: str
    event_type: str
    assignment_id: str | None = None


@dataclass(frozen=True, slots=True)
class AdminSummary:
    teachers_active: int
    assignments_configured: int
    plans_generated: int
    friday_validations_completed: int
    lessons_carried_forward: int
    generation_failures: int


@dataclass(frozen=True, slots=True)
class CostSummary:
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_estimated_cost_usd: Decimal
    accepted_outputs: int
    discarded_outputs: int


def summarize_admin_usage(events: Iterable[AdminUsageEvent]) -> AdminSummary:
    event_list = list(events)
    active_teachers = {event.teacher_id for event in event_list}
    assignments = {
        event.assignment_id
        for event in event_list
        if event.assignment_id is not None and event.event_type == "assignment_configured"
    }
    return AdminSummary(
        teachers_active=len(active_teachers),
        assignments_configured=len(assignments),
        plans_generated=sum(event.event_type == "plan_generated" for event in event_list),
        friday_validations_completed=sum(
            event.event_type == "friday_validation_completed" for event in event_list
        ),
        lessons_carried_forward=sum(
            event.event_type == "lesson_carried_forward" for event in event_list
        ),
        generation_failures=sum(event.event_type == "generation_failed" for event in event_list),
    )


def summarize_ai_cost(records: Iterable[AiUsageRecord]) -> CostSummary:
    record_list = list(records)
    return CostSummary(
        total_requests=len(record_list),
        successful_requests=sum(record.succeeded for record in record_list),
        failed_requests=sum(not record.succeeded for record in record_list),
        total_input_tokens=sum(record.input_tokens for record in record_list),
        total_output_tokens=sum(record.output_tokens for record in record_list),
        total_estimated_cost_usd=sum(
            (record.estimated_cost_usd for record in record_list), start=Decimal("0")
        ),
        accepted_outputs=sum(record.accepted_by_teacher is True for record in record_list),
        discarded_outputs=sum(record.accepted_by_teacher is False for record in record_list),
    )
