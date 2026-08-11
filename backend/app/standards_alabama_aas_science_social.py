from __future__ import annotations

from .standards_alabama_aas import (
    parse_alabama_aas_science_2017 as _parse_science,
)
from .standards_alabama_aas import (
    parse_alabama_aas_social_studies_2017 as _parse_social_studies,
)
from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

_SCIENCE_PARSER_VERSION = "gate-e-alabama-aas-science-2017-v2"
_SOCIAL_STUDIES_PARSER_VERSION = "gate-e-alabama-aas-social-studies-2017-v2"


def parse_alabama_aas_science_2017(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    return _with_exact_duplicate_rows_removed(
        _parse_science(extracted),
        parser_version=_SCIENCE_PARSER_VERSION,
    )


def parse_alabama_aas_social_studies_2017(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    return _with_exact_duplicate_rows_removed(
        _parse_social_studies(extracted),
        parser_version=_SOCIAL_STUDIES_PARSER_VERSION,
    )


def _with_exact_duplicate_rows_removed(
    parsed: ParsedStandardsDocument,
    *,
    parser_version: str,
) -> ParsedStandardsDocument:
    courses: list[ParsedCourse] = []
    for course in parsed.courses:
        standards = _deduplicate_exact_rows(course.standards)
        if len(standards) < 3:
            raise StandardsIngestError(
                "Alabama alternate standards parser found incomplete "
                f"{course.display_name} data after overview-row deduplication"
            )
        courses.append(
            ParsedCourse(
                course_key=course.course_key,
                display_name=course.display_name,
                source_course_code=course.source_course_code,
                grade_band=course.grade_band,
                standards=standards,
            )
        )

    return ParsedStandardsDocument(
        parser_key=parsed.parser_key,
        parser_version=parser_version,
        normalized_sha256=parsed.normalized_sha256,
        courses=tuple(courses),
    )


def _deduplicate_exact_rows(
    standards: tuple[ParsedStandard, ...],
) -> tuple[ParsedStandard, ...]:
    """Suppress extraction duplicates while preserving authoritative code collisions."""

    seen: set[tuple[str, str, str | None, str | None]] = set()
    kept: list[ParsedStandard] = []
    for standard in standards:
        key = (
            standard.code,
            standard.text,
            standard.parent_code,
            standard.strand,
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(standard)
    return tuple(kept)
