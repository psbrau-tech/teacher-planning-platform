"""Document boundaries and readable pagination rules for the Anniston HQI set."""

from dataclasses import dataclass
from enum import StrEnum

from .pdf_fields import DAILY_FIELDS, PAGE_ONE_FIELDS, REFLECTION_FIELDS


class HqiDocument(StrEnum):
    INSTRUCTIONAL_FRAMEWORK = "instructional-framework"
    WEEK_AT_A_GLANCE = "week-at-a-glance"
    WEEKLY_REFLECTION = "weekly-reflection"


DOCUMENT_FIELDS: dict[HqiDocument, tuple[str, ...]] = {
    HqiDocument.INSTRUCTIONAL_FRAMEWORK: PAGE_ONE_FIELDS,
    HqiDocument.WEEK_AT_A_GLANCE: DAILY_FIELDS,
    HqiDocument.WEEKLY_REFLECTION: REFLECTION_FIELDS,
}

# These are readable-page capacities, not storage limits. Content beyond these
# thresholds must flow to continuation pages at the normal body font size.
READABLE_PAGE_CAPACITY: dict[str, int] = {
    **{field: 260 for field in PAGE_ONE_FIELDS},
    **{field: 145 for field in DAILY_FIELDS},
    **{field: 220 for field in REFLECTION_FIELDS},
}
READABLE_PAGE_CAPACITY.update(
    {
        "teacher": 45,
        "course": 55,
        "grade": 20,
        "week_of": 30,
        "unit_topic": 90,
    }
)


@dataclass(frozen=True, slots=True)
class ContinuationRequirement:
    document: HqiDocument
    field: str
    character_count: int
    first_page_capacity: int


def document_for_field(field: str) -> HqiDocument:
    for document, fields in DOCUMENT_FIELDS.items():
        if field in fields:
            return document
    raise ValueError(f"Unknown HQI field: {field}")


def continuation_requirements(payload: dict[str, str]) -> tuple[ContinuationRequirement, ...]:
    requirements = [
        ContinuationRequirement(
            document=document_for_field(field),
            field=field,
            character_count=len(value),
            first_page_capacity=READABLE_PAGE_CAPACITY[field],
        )
        for field, value in payload.items()
        if field in READABLE_PAGE_CAPACITY and len(value) > READABLE_PAGE_CAPACITY[field]
    ]
    return tuple(sorted(requirements, key=lambda item: (item.document, item.field)))
