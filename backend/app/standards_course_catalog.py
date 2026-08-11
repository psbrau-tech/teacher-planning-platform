from __future__ import annotations

import re
from dataclasses import dataclass

from .standards_ingest import ExtractedDocument, StandardsIngestError

COURSE_CATALOG_PARSER_VERSION = "gate-e-course-catalog-v1"
_ALABAMA_COURSE_CODE = re.compile(r"\b(?P<code>\d{5}G\d{4})\b")
_TRAILING_CREDIT_GRADE = re.compile(
    r"\s+(?P<credit>\d+(?:\.\d+)?)\s+(?P<grade>\d{1,2}(?:-\d{1,2})?)\s*$"
)
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


@dataclass(frozen=True, slots=True)
class ParsedCourseListing:
    course_key: str
    display_name: str
    source_course_code: str
    grade_band: str | None


@dataclass(frozen=True, slots=True)
class ParsedCourseCatalogDocument:
    parser_key: str
    parser_version: str
    normalized_sha256: str
    courses: tuple[ParsedCourseListing, ...]


def parse_course_catalog_document(
    parser_key: str,
    extracted: ExtractedDocument,
) -> ParsedCourseCatalogDocument:
    if parser_key != "alabama_cte_program_generic":
        raise StandardsIngestError(f"Unsupported course-catalog parser: {parser_key}")

    courses = _parse_alabama_cte_program_guide(extracted.lines)
    if not courses:
        raise StandardsIngestError("Alabama CTE Program Guide contained no course listings")
    return ParsedCourseCatalogDocument(
        parser_key=parser_key,
        parser_version=COURSE_CATALOG_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=courses,
    )


def _parse_alabama_cte_program_guide(
    lines: tuple[str, ...],
) -> tuple[ParsedCourseListing, ...]:
    parsed: dict[str, ParsedCourseListing] = {}
    pending_code: str | None = None

    for line in lines:
        matches = list(_ALABAMA_COURSE_CODE.finditer(line))
        if not matches:
            if pending_code is not None:
                course = _course_from_segment(pending_code, line)
                if course is not None:
                    parsed.setdefault(course.source_course_code, course)
                    pending_code = None
            continue

        for index, match in enumerate(matches):
            code = match.group("code")
            segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
            segment = line[match.end() : segment_end].strip(" |:-")
            course = _course_from_segment(code, segment)
            if course is None:
                pending_code = code
                continue
            parsed.setdefault(course.source_course_code, course)
            pending_code = None

    return tuple(sorted(parsed.values(), key=lambda item: item.source_course_code))


def _course_from_segment(code: str, segment: str) -> ParsedCourseListing | None:
    cleaned = re.sub(r"\s+", " ", segment).strip()
    if not cleaned:
        return None

    grade_band: str | None = None
    metadata = _TRAILING_CREDIT_GRADE.search(cleaned)
    if metadata is not None:
        grade_band = metadata.group("grade")
        cleaned = cleaned[: metadata.start()].strip()

    cleaned = _strip_table_noise(cleaned)
    if len(cleaned) < 3 or not re.search(r"[A-Za-z]", cleaned):
        return None

    return ParsedCourseListing(
        course_key=_course_key(code, cleaned),
        display_name=cleaned,
        source_course_code=code,
        grade_band=grade_band,
    )


def _strip_table_noise(value: str) -> str:
    result = value.strip(" |:-")
    result = re.sub(r"\s+(?:Course Credit|Grade Levels?)\s*$", "", result, flags=re.IGNORECASE)
    return result.strip()


def _course_key(code: str, display_name: str) -> str:
    normalized_name = re.sub(r"\s+", " ", display_name).strip()
    army_match = re.search(
        r"Army\s+JROTC\s+Leadership\s+Education\s+and\s+Training\s+(I{1,3}|IV)\b",
        normalized_name,
        flags=re.IGNORECASE,
    )
    if army_match is not None:
        level = _ROMAN.get(army_match.group(1).upper())
        if level is not None:
            return f"army_jrotc_let_{level}"

    air_force_match = re.search(r"Air\s+Force\s+JROTC.*?\b([1-4])\b", normalized_name, re.I)
    if air_force_match is not None:
        return f"air_force_jrotc_{air_force_match.group(1)}"

    marine_match = re.search(r"Marine\s+Corps\s+JROTC.*?\b([1-4])\b", normalized_name, re.I)
    if marine_match is not None:
        return f"marine_corps_jrotc_{marine_match.group(1)}"

    navy_match = re.search(r"Navy\s+JROTC.*?\b([1-4])\b", normalized_name, re.I)
    if navy_match is not None:
        return f"navy_jrotc_{navy_match.group(1)}"

    coast_guard_match = re.search(r"Coast\s+Guard\s+JROTC.*?\b([1-4])\b", normalized_name, re.I)
    if coast_guard_match is not None:
        return f"coast_guard_jrotc_{coast_guard_match.group(1)}"

    slug = re.sub(r"[^a-z0-9]+", "_", normalized_name.lower()).strip("_")
    return slug or f"alabama_course_{code.lower()}"
