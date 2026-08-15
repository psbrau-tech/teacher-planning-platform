from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DAY_SUFFIXES = (
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
)


@dataclass(frozen=True, slots=True)
class AssessmentTypeDefinition:
    key: str
    label: str
    patterns: tuple[re.Pattern[str], ...]


def _patterns(*values: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(value, re.IGNORECASE) for value in values)


ASSESSMENT_TYPES = (
    AssessmentTypeDefinition(
        "exit_ticket",
        "Exit tickets / slips",
        _patterns(r"\bexit\s+(?:ticket|slip|card)\b", r"\b3[- ]2[- ]1\b"),
    ),
    AssessmentTypeDefinition(
        "quick_write",
        "Quick writes / short written responses",
        _patterns(
            r"\bquick\s*write\b",
            r"\bminute\s+paper\b",
            r"\bshort\s+(?:written\s+)?response\b",
            r"\bwritten\s+response\b",
            r"\bconstructed\s+response\b",
        ),
    ),
    AssessmentTypeDefinition(
        "quiz",
        "Short quizzes",
        _patterns(r"\bmini[- ]?quiz\b", r"\bquiz(?:zes)?\b"),
    ),
    AssessmentTypeDefinition(
        "digital_check",
        "Digital polls / response tools",
        _patterns(
            r"\bkahoot\b",
            r"\bquizizz\b",
            r"\bmentimeter\b",
            r"\bnearpod\b",
            r"\bpear\s*deck\b",
            r"\bgoogle\s+forms?\b",
            r"\bmicrosoft\s+forms?\b",
            r"\bdigital\s+poll\b",
            r"\bpoll(?:ing)?\b",
        ),
    ),
    AssessmentTypeDefinition(
        "whiteboard_response",
        "Whiteboard responses",
        _patterns(
            r"\bmini[- ]?whiteboards?\b",
            r"\bwhiteboards?\b",
            r"\bdry[- ]erase\s+boards?\b",
        ),
    ),
    AssessmentTypeDefinition(
        "response_signal",
        "Response signals",
        _patterns(
            r"\bthumbs?\s+(?:up|down)\b",
            r"\bfist[- ]to[- ]five\b",
            r"\bhand\s+signals?\b",
            r"\bresponse\s+cards?\b",
            r"\btraffic\s+light\b",
        ),
    ),
    AssessmentTypeDefinition(
        "questioning_discussion",
        "Questioning / discussion checks",
        _patterns(
            r"\bquestioning\b",
            r"\bcold\s+call(?:ing)?\b",
            r"\boral\s+(?:question|response)s?\b",
            r"\bturn\s+and\s+talk\b",
            r"\bthink[- ]pair[- ]share\b",
            r"\bdiscussion\b",
        ),
    ),
    AssessmentTypeDefinition(
        "retrieval_warmup",
        "Retrieval / warm-up checks",
        _patterns(
            r"\bretrieval\b",
            r"\bdo[- ]?now\b",
            r"\bbell\s*ringer\b",
            r"\bwarm[- ]?up\b",
            r"\bentrance\s+(?:ticket|slip)\b",
        ),
    ),
    AssessmentTypeDefinition(
        "observation_conference",
        "Observation / conference checks",
        _patterns(
            r"\bteacher\s+observation\b",
            r"\bobservation\b",
            r"\bcirculat(?:e|ing|ion)\b",
            r"\bconference\b",
            r"\bchecklist\b",
            r"\bteacher\s+check\b",
        ),
    ),
    AssessmentTypeDefinition(
        "peer_self_assessment",
        "Peer / self-assessment",
        _patterns(
            r"\bpeer\s+(?:review|assessment|feedback)\b",
            r"\bself[- ]assessment\b",
            r"\bself[- ]check\b",
            r"\bself[- ]rating\b",
        ),
    ),
    AssessmentTypeDefinition(
        "performance_demonstration",
        "Performance / demonstration checks",
        _patterns(
            r"\bdemonstrat(?:e|es|ed|ion)\b",
            r"\bperformance\s+(?:check|task|demonstration)\b",
            r"\bshow\s+me\b",
            r"\bpractice\s+problem\b",
        ),
    ),
)

ASSESSMENT_TYPE_LABELS = {item.key: item.label for item in ASSESSMENT_TYPES} | {
    "other_formative": "Other / not yet classified",
}


def classify_daily_assessment(cfu_text: str, evidence_text: str) -> list[str]:
    """Classify one planned day without sending lesson-plan text to an AI provider.

    The classifier intentionally favors transparent, auditable pattern matching over inferred
    instructional quality. A nonblank daily CFU/evidence entry with no known pattern is retained as
    `other_formative` rather than being guessed into a category.
    """
    combined = "\n".join(value.strip() for value in (cfu_text, evidence_text) if value.strip())
    if not combined:
        return []

    matched = [
        item.key
        for item in ASSESSMENT_TYPES
        if any(pattern.search(combined) for pattern in item.patterns)
    ]
    return matched or ["other_formative"]


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def analyze_daily_assessment_sources(rows: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts = {key: 0 for key in ASSESSMENT_TYPE_LABELS}
    weekday_counts = {label: 0 for _, label in DAY_SUFFIXES}
    daily_entries = 0
    cfu_entries = 0
    evidence_entries = 0
    teacher_refs: set[int] = set()

    for row in rows:
        teacher_ref = row.get("anonymous_teacher_ref")
        if isinstance(teacher_ref, int) and not isinstance(teacher_ref, bool):
            teacher_refs.add(teacher_ref)

        data = row.get("daily_assessment_data")
        if not isinstance(data, dict):
            continue

        for suffix, label in DAY_SUFFIXES:
            cfu_text = _text(data, f"cfu_{suffix}")
            evidence_text = _text(data, f"esl_{suffix}")
            if cfu_text:
                cfu_entries += 1
            if evidence_text:
                evidence_entries += 1
            assessment_types = classify_daily_assessment(cfu_text, evidence_text)
            if not assessment_types:
                continue

            daily_entries += 1
            weekday_counts[label] += 1
            for assessment_type in assessment_types:
                type_counts[assessment_type] += 1

    return {
        "submitted_course_weeks": len(rows),
        "distinct_teachers": len(teacher_refs),
        "daily_assessment_entries": daily_entries,
        "cfu_entries": cfu_entries,
        "evidence_entries": evidence_entries,
        "type_counts": type_counts,
        "weekday_counts": weekday_counts,
    }
