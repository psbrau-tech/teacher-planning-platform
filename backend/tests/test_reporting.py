from decimal import Decimal

from app.reporting import (
    AdminUsageEvent,
    AiFeature,
    AiUsageRecord,
    summarize_admin_usage,
    summarize_ai_cost,
)


def test_admin_summary_counts_unique_teachers_and_assignments() -> None:
    summary = summarize_admin_usage(
        [
            AdminUsageEvent("teacher-1", "assignment_configured", "let-1"),
            AdminUsageEvent("teacher-1", "assignment_configured", "let-2"),
            AdminUsageEvent("teacher-1", "plan_generated", "let-1"),
            AdminUsageEvent("teacher-2", "friday_validation_completed", "eng-10"),
            AdminUsageEvent("teacher-2", "lesson_carried_forward", "eng-10"),
            AdminUsageEvent("teacher-2", "generation_failed", "eng-10"),
        ]
    )

    assert summary.teachers_active == 2
    assert summary.assignments_configured == 2
    assert summary.plans_generated == 1
    assert summary.friday_validations_completed == 1
    assert summary.lessons_carried_forward == 1
    assert summary.generation_failures == 1


def test_ai_cost_summary_preserves_estimated_cost_and_approval_outcomes() -> None:
    summary = summarize_ai_cost(
        [
            AiUsageRecord(
                organization_id="acs",
                school_id="ahs",
                teacher_id="teacher-1",
                assignment_id="let-1",
                feature=AiFeature.REFLECTION,
                model="test-model",
                input_tokens=100,
                output_tokens=50,
                estimated_cost_usd=Decimal("0.0125"),
                accepted_by_teacher=True,
            ),
            AiUsageRecord(
                organization_id="acs",
                school_id="ahs",
                teacher_id="teacher-1",
                assignment_id="let-1",
                feature=AiFeature.KUD,
                model="test-model",
                input_tokens=80,
                output_tokens=40,
                estimated_cost_usd=Decimal("0.0100"),
                succeeded=False,
                retry_count=1,
                accepted_by_teacher=False,
            ),
        ]
    )

    assert summary.total_requests == 2
    assert summary.successful_requests == 1
    assert summary.failed_requests == 1
    assert summary.total_input_tokens == 180
    assert summary.total_output_tokens == 90
    assert summary.total_estimated_cost_usd == Decimal("0.0225")
    assert summary.accepted_outputs == 1
    assert summary.discarded_outputs == 1
