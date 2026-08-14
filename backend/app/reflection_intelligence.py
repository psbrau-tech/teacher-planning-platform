from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

REFLECTION_KEYS = tuple(f"reflect_{index}" for index in range(1, 13))

REFLECTION_PROMPTS = (
    "What knowledge has been building this week?",
    "What understandings are being developed?",
    "What evidence is demonstrating mastery?",
    "What misconceptions emerged?",
    "What standard(s) or parts of the standard need reteaching?",
    "Which students need intervention?",
    "What is the plan for intervention (Tier 2 and Tier 3)?",
    "Which students need enrichment?",
    "What is the plan for enrichment?",
    "Which instructional moves worked?",
    "What instructional adjustments will I make next week?",
    "What are next week's instructional priorities?",
)

# This is a deliberately conservative preflight, not a claim that pattern matching can prove
# content is free of student data. It catches common high-risk markers before any reflection text
# is sent to the approved AI provider. The product UI continues to prohibit all student-specific
# information at reflection entry and again at synthesis time.
_HIGH_RISK_PATTERNS = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:student\s+id|student\s*#|ssn|social\s+security)\b", re.IGNORECASE),
    re.compile(r"\b(?:iep|section\s+504|504\s+plan)\b", re.IGNORECASE),
    re.compile(r"\b(?:[Ss]tudent|[Pp]upil)\s+(?:named\s+)?[A-Z][a-z]{1,}\b"),
    re.compile(r"\b\d{3}[-.)\s]\d{3}[-.\s]\d{4}\b"),
)


class ReflectionBoundaryError(ValueError):
    """Reflection content is not eligible for AI synthesis under the TPP data boundary."""


class TeacherReflectionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: int = Field(ge=1)
    course_name: str = Field(min_length=1, max_length=500)
    week_start: str = Field(min_length=10, max_length=10)
    reflection_text: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class SchoolReflectionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ref: int = Field(ge=1)
    week_start: str = Field(min_length=10, max_length=10)
    reflection_text: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class TeacherReflectionInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weekly_recap: str
    recurring_themes: list[str]
    strategies_that_work: list[str]
    challenges_to_watch: list[str]
    carry_forward_ideas: list[str]

    @field_validator(
        "recurring_themes",
        "strategies_that_work",
        "challenges_to_watch",
        "carry_forward_ideas",
    )
    @classmethod
    def bounded_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()][:6]


class SupportedTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: str
    evidence_summary: str
    source_refs: list[int]

    @field_validator("source_refs")
    @classmethod
    def unique_source_refs(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class SchoolReflectionBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")

    common_successes: list[SupportedTheme]
    common_challenges: list[SupportedTheme]
    emerging_themes: list[SupportedTheme]
    discussion_questions: list[str]
    possible_actions: list[str]
    support_needs: list[str]

    @field_validator("discussion_questions", "possible_actions", "support_needs")
    @classmethod
    def bounded_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()][:8]


TEACHER_INSIGHT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "weekly_recap": {"type": "string"},
        "recurring_themes": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "strategies_that_work": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "challenges_to_watch": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
        "carry_forward_ideas": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
    },
    "required": [
        "weekly_recap",
        "recurring_themes",
        "strategies_that_work",
        "challenges_to_watch",
        "carry_forward_ideas",
    ],
}

_SUPPORTED_THEME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "theme": {"type": "string"},
        "evidence_summary": {"type": "string"},
        "source_refs": {
            "type": "array",
            "items": {"type": "integer"},
            "minItems": 2,
            "maxItems": 100,
        },
    },
    "required": ["theme", "evidence_summary", "source_refs"],
}

SCHOOL_BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "common_successes": {
            "type": "array",
            "items": _SUPPORTED_THEME_SCHEMA,
            "maxItems": 6,
        },
        "common_challenges": {
            "type": "array",
            "items": _SUPPORTED_THEME_SCHEMA,
            "maxItems": 6,
        },
        "emerging_themes": {
            "type": "array",
            "items": _SUPPORTED_THEME_SCHEMA,
            "maxItems": 6,
        },
        "discussion_questions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "possible_actions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "support_needs": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
    },
    "required": [
        "common_successes",
        "common_challenges",
        "emerging_themes",
        "discussion_questions",
        "possible_actions",
        "support_needs",
    ],
}

TEACHER_SYNTHESIS_INSTRUCTIONS = """
You are the Teacher Planning Platform Reflection Intelligence synthesis engine.
Use only the supplied teacher-authored, explicitly submitted professional reflections.
Do not create, complete, rewrite, or improve a reflection response.
Do not score, rank, evaluate, judge, or infer teacher quality, effort, productivity, or performance.
Do not infer student identities, student outcomes, diagnoses, disability status, or other student-specific facts.
Summarize the selected week's reflection and identify recurring professional patterns across the supplied
4-12 week window. Keep claims grounded in the supplied sources. If evidence is limited, say so plainly.
Return concise professional learning insight that helps the teacher learn from their own practice.
""".strip()

SCHOOL_SYNTHESIS_INSTRUCTIONS = """
You are the Teacher Planning Platform school Reflection Intelligence synthesis engine.
Use only the supplied anonymous source references from teacher-authored, explicitly submitted reflections.
The output is for PLC/faculty professional learning, not personnel evaluation.
Never score, rank, compare, judge, or infer teacher quality, effort, productivity, or performance.
Never infer teacher identity. Never infer student identity or student-specific facts.
A common success, common challenge, or emerging theme may be returned only when supported by at least
TWO DISTINCT source_ref values. Cite those source_ref integers in source_refs. Do not treat multiple
class reflections carrying the same source_ref as multiple teachers. Keep evidence summaries aggregate,
non-identifying, and grounded in the supplied text. Discussion questions and possible actions must be
course-agnostic where practical and may not identify an individual teacher.
""".strip()


def parse_reflection_text(raw: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReflectionBoundaryError("A submitted reflection is not in the governed format") from error
    if not isinstance(parsed, dict):
        raise ReflectionBoundaryError("A submitted reflection is not in the governed format")

    reflection: dict[str, str] = {}
    for key in REFLECTION_KEYS:
        value = parsed.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ReflectionBoundaryError("A submitted reflection is incomplete")
        cleaned = value.strip()
        _require_boundary_safe(cleaned)
        reflection[key] = cleaned
    return reflection


def _require_boundary_safe(value: str) -> None:
    if any(pattern.search(value) for pattern in _HIGH_RISK_PATTERNS):
        raise ReflectionBoundaryError(
            "Reflection Intelligence cannot process content that may contain student-specific information"
        )


def teacher_ai_context(
    sources: Iterable[TeacherReflectionSource],
    *,
    selected_week: str,
    lookback_weeks: int,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for source in sources:
        reflection = parse_reflection_text(source.reflection_text)
        entries.append(
            {
                "source_ref": source.source_ref,
                "course": source.course_name,
                "week_start": source.week_start,
                "responses": [
                    {
                        "prompt_number": index,
                        "prompt": REFLECTION_PROMPTS[index - 1],
                        "response": reflection[f"reflect_{index}"],
                    }
                    for index in range(1, 13)
                ],
            }
        )
    return {
        "selected_week": selected_week,
        "lookback_weeks": lookback_weeks,
        "teacher_authored_sources": entries,
    }


def school_ai_context(sources: Iterable[SchoolReflectionSource], *, week_start: str) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for source in sources:
        reflection = parse_reflection_text(source.reflection_text)
        entries.append(
            {
                "source_ref": source.source_ref,
                "week_start": source.week_start,
                "responses": [
                    {
                        "prompt_number": index,
                        "prompt": REFLECTION_PROMPTS[index - 1],
                        "response": reflection[f"reflect_{index}"],
                    }
                    for index in range(1, 13)
                ],
            }
        )
    return {"week_start": week_start, "anonymous_teacher_sources": entries}


def validate_school_brief(
    raw: dict[str, Any],
    *,
    available_source_refs: set[int],
) -> SchoolReflectionBrief:
    brief = SchoolReflectionBrief.model_validate(raw)

    def supported(items: list[SupportedTheme]) -> list[SupportedTheme]:
        result: list[SupportedTheme] = []
        for item in items:
            refs = [ref for ref in item.source_refs if ref in available_source_refs]
            refs = list(dict.fromkeys(refs))
            if len(refs) < 2:
                continue
            result.append(item.model_copy(update={"source_refs": refs}))
        return result[:6]

    return brief.model_copy(
        update={
            "common_successes": supported(brief.common_successes),
            "common_challenges": supported(brief.common_challenges),
            "emerging_themes": supported(brief.emerging_themes),
        }
    )


def record_list(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("Reflection Intelligence source returned invalid data")
    return [cast(dict[str, Any], row) for row in payload if isinstance(row, dict)]
