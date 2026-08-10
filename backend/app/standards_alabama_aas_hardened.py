from __future__ import annotations

import re

from .standards_alabama_aas import parse_alabama_aas_ela_2021 as _parse_ela
from .standards_alabama_aas import parse_alabama_aas_math_2019 as _parse_math
from .standards_alabama_aas import parse_alabama_aas_science_2017 as _parse_science
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

# The official 2019 Math AAS PDF can place whitespace between the final period
# and numeric identifier when text is extracted from its table layout, e.g.
# ``M.AAS.K. 1`` or ``M.G.AAS.9. 1``. The printed authoritative identifier is
# contiguous. Repair only this narrowly bounded source-extraction artifact.
_SPACED_MATH_FINAL_SEGMENT = re.compile(
    r"(?P<prefix>\bM(?:\.[A-Za-z0-9]+)*\.AAS\.(?:K|[0-9]+))\.\s+"
    r"(?P<tail>[0-9]+[A-Za-z]?)\b",
    flags=re.IGNORECASE,
)

# Every materialized AAS identifier must be structurally complete. This catches
# truncated values such as ``M.AAS.K.`` before they can become a governed
# candidate snapshot.
_CANONICAL_AAS_CODE = re.compile(
    r"^(?:ELA21|ELA|M|SCI|SS)(?:\.[A-Za-z0-9]+)*\.AAS\."
    r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*$",
    flags=re.IGNORECASE,
)

_PARSER_VERSIONS = {
    "alabama_aas_ela_2021": "gate-e-alabama-aas-ela-2021-v2",
    "alabama_aas_math_2019": "gate-e-alabama-aas-math-2019-v2",
    "alabama_aas_science_2017": "gate-e-alabama-aas-science-2017-v2",
    "alabama_aas_social_studies_2017": "gate-e-alabama-aas-social-studies-2017-v2",
}


def parse_alabama_aas_ela_2021(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    return _harden(_parse_ela(extracted))


def parse_alabama_aas_math_2019(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    repaired = ExtractedDocument(
        lines=tuple(_repair_math_line(line) for line in extracted.lines),
        normalized_sha256=extracted.normalized_sha256,
    )
    return _harden(_parse_math(repaired))


def parse_alabama_aas_science_2017(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    return _harden(_parse_science(extracted))


def parse_alabama_aas_social_studies_2017(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    return _harden(_parse_social_studies(extracted))


def _repair_math_line(line: str) -> str:
    return _SPACED_MATH_FINAL_SEGMENT.sub(r"\g<prefix>.\g<tail>", line)


def _harden(parsed: ParsedStandardsDocument) -> ParsedStandardsDocument:
    parser_version = _PARSER_VERSIONS.get(parsed.parser_key)
    if parser_version is None:
        raise StandardsIngestError(
            f"Unsupported Alabama alternate standards parser key: {parsed.parser_key}"
        )

    courses: list[ParsedCourse] = []
    for course in parsed.courses:
        standards = _validated_deduplicated_standards(
            parser_key=parsed.parser_key,
            course=course,
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


def _validated_deduplicated_standards(
    *,
    parser_key: str,
    course: ParsedCourse,
) -> tuple[ParsedStandard, ...]:
    seen_exact_rows: set[tuple[str, str, str | None, str | None]] = set()
    standards: list[ParsedStandard] = []

    for standard in course.standards:
        if _CANONICAL_AAS_CODE.fullmatch(standard.code) is None:
            raise StandardsIngestError(
                "Alabama alternate standards parser produced an incomplete authoritative "
                f"identifier for {parser_key}/{course.course_key}: {standard.code!r}"
            )

        exact_key = (
            standard.code,
            standard.text,
            standard.parent_code,
            standard.strand,
        )
        if exact_key in seen_exact_rows:
            # pypdf can expose the same printed table row twice. Suppress only
            # byte-equivalent semantic rows. Distinct statements that share an
            # official source identifier remain separate authoritative entries.
            continue
        seen_exact_rows.add(exact_key)
        standards.append(standard)

    if len(standards) < 3:
        raise StandardsIngestError(
            f"Alabama alternate standards parser found incomplete {course.display_name} data "
            f"for {parser_key} after authoritative-row validation"
        )
    return tuple(standards)
