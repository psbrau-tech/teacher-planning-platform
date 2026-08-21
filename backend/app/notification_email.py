from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from .settings import (
    APPROVED_SES_FROM_EMAIL,
    APPROVED_SES_REPLY_TO_EMAIL,
    Settings,
)


class SesDeliveryError(RuntimeError):
    """A bounded SES delivery failure safe to surface without leaking provider details."""

    def __init__(self, message: str, *, provider_code: str) -> None:
        super().__init__(message)
        self.provider_code = provider_code


@dataclass(frozen=True, slots=True)
class WeeklyAdminDigestMetrics:
    """Legacy/manual admin-digest metrics retained for controlled recovery support."""

    week_start: date
    configured_assignments: int
    lesson_plans_submitted: int
    lesson_plans_missing: int
    completed_packets_submitted: int
    completed_packets_missing: int
    teachers_with_completed_packets: int

    @property
    def plc_brief_available(self) -> bool:
        return self.teachers_with_completed_packets >= 2


@dataclass(frozen=True, slots=True)
class FridayTeacherReminderItem:
    course_name: str
    missing_current_closeout: bool
    missing_next_plan: bool


@dataclass(frozen=True, slots=True)
class FridayAdminDigestMetrics:
    week_start: date
    next_week_start: date
    current_teachers_expected: int
    current_teachers_complete: int
    current_packets_expected: int
    current_packets_submitted: int
    next_teachers_expected: int
    next_teachers_complete: int
    next_plans_expected: int
    next_plans_submitted: int
    teachers_with_completed_packets: int

    @property
    def current_packets_missing(self) -> int:
        return max(0, self.current_packets_expected - self.current_packets_submitted)

    @property
    def next_plans_missing(self) -> int:
        return max(0, self.next_plans_expected - self.next_plans_submitted)

    @property
    def plc_brief_available(self) -> bool:
        return self.teachers_with_completed_packets >= 2


def _validated_delivery_addresses(
    settings: Settings,
    recipient_email: str,
) -> tuple[str, str, str]:
    sender = settings.ses_from_email.strip().lower()
    reply_to = settings.ses_reply_to_email.strip().lower()
    recipient = recipient_email.strip().lower()
    if not sender:
        raise SesDeliveryError(
            "Email notifications are not configured for this environment",
            provider_code="SenderNotConfigured",
        )
    if sender != APPROVED_SES_FROM_EMAIL:
        raise SesDeliveryError(
            "Configured email sender does not match the approved TPP sender",
            provider_code="SenderNotApproved",
        )
    if reply_to != APPROVED_SES_REPLY_TO_EMAIL:
        raise SesDeliveryError(
            "Configured email Reply-To does not match the approved TPP mailbox",
            provider_code="ReplyToNotApproved",
        )
    if not recipient or not settings.email_is_allowed(recipient):
        raise SesDeliveryError(
            "Email recipient is outside the governed TPP account boundary",
            provider_code="RecipientNotAllowed",
        )
    return sender, reply_to, recipient


def _send_text_email(
    settings: Settings,
    *,
    recipient_email: str,
    subject: str,
    body: str,
    failure_label: str,
) -> str:
    sender, reply_to, recipient = _validated_delivery_addresses(settings, recipient_email)
    try:
        client = boto3.client("sesv2", region_name=settings.ses_region)
        raw_response = client.send_email(
            FromEmailAddress=sender,
            ReplyToAddresses=[reply_to],
            Destination={"ToAddresses": [recipient]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                }
            },
        )
    except ClientError as error:
        raw_code = error.response.get("Error", {}).get("Code", "SesClientError")
        provider_code = (
            raw_code
            if isinstance(raw_code, str) and raw_code.replace("_", "").isalnum()
            else "SesClientError"
        )
        raise SesDeliveryError(
            f"{failure_label} could not be delivered",
            provider_code=provider_code,
        ) from error
    except BotoCoreError as error:
        raise SesDeliveryError(
            f"{failure_label} could not be delivered",
            provider_code=type(error).__name__,
        ) from error

    response = cast(dict[str, Any], raw_response)
    message_id = response.get("MessageId")
    if not isinstance(message_id, str) or not message_id.strip():
        raise SesDeliveryError(
            f"{failure_label} returned no delivery identifier",
            provider_code="MissingMessageId",
        )
    return message_id.strip()


def weekly_admin_digest_text(
    metrics: WeeklyAdminDigestMetrics,
    *,
    public_base_url: str,
) -> str:
    """Render the legacy/manual content-minimized admin operations email."""
    plc_line = (
        "A school PLC reflection brief can be generated in TPP from aggregate "
        "submitted reflections."
        if metrics.plc_brief_available
        else "A school PLC reflection brief is not yet available from at least two "
        "teacher sources."
    )
    return "\n".join(
        (
            "Teacher Planning Platform weekly admin digest — "
            f"week of {metrics.week_start.isoformat()}",
            "",
            f"Configured course assignments: {metrics.configured_assignments}",
            f"Lesson plans submitted: {metrics.lesson_plans_submitted}",
            f"Lesson plans missing: {metrics.lesson_plans_missing}",
            f"Completed Friday packets submitted: {metrics.completed_packets_submitted}",
            f"Completed Friday packets missing: {metrics.completed_packets_missing}",
            "",
            plc_line,
            "",
            "Open authenticated TPP for teacher-level operational follow-up and PLC insight:",
            public_base_url.rstrip("/"),
            "",
            "This email contains school-scoped operational counts only. It contains no "
            "student data,",
            "teacher reflection text, generated instructional insight, or teacher-quality score.",
        )
    )


def teacher_friday_reminder_text(
    *,
    display_name: str,
    week_start: date,
    next_week_start: date,
    items: tuple[FridayTeacherReminderItem, ...],
    public_base_url: str,
) -> str:
    """Render one friendly, class-specific reminder without professional-content bodies."""
    lines = [
        f"Hi {display_name.strip() or 'there'},",
        "",
        "Just a quick Friday reminder so these items do not get lost in a busy week.",
        "TPP still shows the following submissions waiting:",
        "",
    ]
    for item in items:
        missing: list[str] = []
        if item.missing_current_closeout:
            missing.append(
                f"this week's reflection / completed packet ({week_start.isoformat()})"
            )
        if item.missing_next_plan:
            missing.append(f"next week's lesson plan ({next_week_start.isoformat()})")
        if missing:
            lines.append(f"- {item.course_name}: " + "; ".join(missing))
    lines.extend(
        (
            "",
            "If you have already been working on these, no problem. This courtesy reminder "
            "is based",
            "on submitted status at the time it was sent so you do not have to search "
            "through every class.",
            "",
            "Open TPP to finish or submit:",
            public_base_url.rstrip("/"),
            "",
            "This message contains professional course/submission status only. Do not reply with",
            "student information, student work, or other student-specific details.",
            "",
            "Have a good weekend.",
        )
    )
    return "\n".join(lines)


def friday_admin_digest_text(
    metrics: FridayAdminDigestMetrics,
    *,
    public_base_url: str,
) -> str:
    """Render the automatic 3:30 PM aggregate Friday status email."""
    plc_line = (
        "School PLC Reflection Brief: available in TPP."
        if metrics.plc_brief_available
        else "School PLC Reflection Brief: not yet available from at least two submitted "
        "teacher sources."
    )
    current_teacher_line = (
        f"Teachers fully complete: {metrics.current_teachers_complete} "
        f"of {metrics.current_teachers_expected}"
    )
    current_packet_line = (
        f"Completed packets submitted: {metrics.current_packets_submitted} "
        f"of {metrics.current_packets_expected}"
    )
    next_teacher_line = (
        f"Teachers fully complete: {metrics.next_teachers_complete} "
        f"of {metrics.next_teachers_expected}"
    )
    next_plan_line = (
        f"Lesson plans submitted: {metrics.next_plans_submitted} "
        f"of {metrics.next_plans_expected}"
    )
    return "\n".join(
        (
            f"Teacher Planning Platform Friday status — week of {metrics.week_start.isoformat()}",
            "",
            "Current-week closeout",
            current_teacher_line,
            current_packet_line,
            f"Completed packets missing: {metrics.current_packets_missing}",
            "",
            f"Following-week planning — week of {metrics.next_week_start.isoformat()}",
            next_teacher_line,
            next_plan_line,
            f"Lesson plans missing: {metrics.next_plans_missing}",
            "",
            plc_line,
            "",
            "Open authenticated TPP for teacher- and class-level operational follow-up:",
            public_base_url.rstrip("/"),
            "",
            "This email contains school-scoped professional submission counts only. "
            "Teacher names,",
            "course-level exceptions, reflection text, lesson-plan content, student data, "
            "generated",
            "instructional insight, and teacher-quality scores remain out of the email.",
        )
    )


def send_weekly_admin_digest(
    settings: Settings,
    *,
    recipient_email: str,
    metrics: WeeklyAdminDigestMetrics,
) -> str:
    return _send_text_email(
        settings,
        recipient_email=recipient_email,
        subject=f"TPP weekly admin digest — week of {metrics.week_start.isoformat()}",
        body=weekly_admin_digest_text(metrics, public_base_url=str(settings.public_base_url)),
        failure_label="The weekly admin digest",
    )


def send_teacher_friday_reminder(
    settings: Settings,
    *,
    recipient_email: str,
    display_name: str,
    week_start: date,
    next_week_start: date,
    items: tuple[FridayTeacherReminderItem, ...],
) -> str:
    if not items:
        raise SesDeliveryError(
            "Teacher Friday reminder has no outstanding professional submissions",
            provider_code="NoOutstandingItems",
        )
    return _send_text_email(
        settings,
        recipient_email=recipient_email,
        subject="Quick Friday TPP reminder — submission items still waiting",
        body=teacher_friday_reminder_text(
            display_name=display_name,
            week_start=week_start,
            next_week_start=next_week_start,
            items=items,
            public_base_url=str(settings.public_base_url),
        ),
        failure_label="The teacher Friday reminder",
    )


def send_friday_admin_digest(
    settings: Settings,
    *,
    recipient_email: str,
    metrics: FridayAdminDigestMetrics,
) -> str:
    return _send_text_email(
        settings,
        recipient_email=recipient_email,
        subject=f"TPP Friday status — week of {metrics.week_start.isoformat()}",
        body=friday_admin_digest_text(metrics, public_base_url=str(settings.public_base_url)),
        failure_label="The Friday admin digest",
    )
