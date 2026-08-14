from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from .settings import Settings


class SesDeliveryError(RuntimeError):
    """A bounded SES delivery failure safe to surface without leaking provider details."""


@dataclass(frozen=True, slots=True)
class WeeklyAdminDigestMetrics:
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


def weekly_admin_digest_text(metrics: WeeklyAdminDigestMetrics, *, public_base_url: str) -> str:
    """Render a deliberately content-minimized school operations email.

    Email carries counts and a link only. Named teacher exceptions, reflection text, and generated
    instructional insight remain behind authenticated TPP access.
    """
    plc_line = (
        "A school PLC reflection brief can be generated in TPP from aggregate "
        "submitted reflections."
        if metrics.plc_brief_available
        else "A school PLC reflection brief is not yet available from at least two teacher sources."
    )
    digest_title = (
        "Teacher Planning Platform weekly admin digest — "
        f"week of {metrics.week_start.isoformat()}"
    )
    return "\n".join(
        (
            digest_title,
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


def send_weekly_admin_digest(
    settings: Settings,
    *,
    recipient_email: str,
    metrics: WeeklyAdminDigestMetrics,
) -> str:
    sender = settings.ses_from_email.strip()
    recipient = recipient_email.strip().lower()
    if not sender:
        raise SesDeliveryError("Email notifications are not configured for this environment")
    if not recipient or not settings.email_is_allowed(recipient):
        raise SesDeliveryError("Email recipient is outside the governed TPP account boundary")

    subject = f"TPP weekly admin digest — week of {metrics.week_start.isoformat()}"
    body = weekly_admin_digest_text(metrics, public_base_url=str(settings.public_base_url))

    try:
        client = boto3.client("sesv2", region_name=settings.ses_region)
        raw_response = client.send_email(
            FromEmailAddress=sender,
            Destination={"ToAddresses": [recipient]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                }
            },
        )
    except (BotoCoreError, ClientError) as error:
        raise SesDeliveryError("The weekly admin digest could not be delivered") from error

    response = cast(dict[str, Any], raw_response)
    message_id = response.get("MessageId")
    if not isinstance(message_id, str) or not message_id.strip():
        raise SesDeliveryError("The weekly admin digest returned no delivery identifier")
    return message_id.strip()
