from __future__ import annotations

import re
from dataclasses import dataclass

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

SOCIAL_STUDIES_PARSER_VERSION = "gate-e-alabama-social-studies-2024-v1"

_COURSES = (
    ("kindergarten", "Kindergarten", "K", ("KINDERGARTEN",)),
    ("grade_1", "Grade 1", "1", ("GRADE 1",)),
    ("grade_2", "Grade 2", "2", ("GRADE 2",)),
    ("grade_3", "Grade 3", "3", ("GRADE 3",)),
    ("grade_4", "Grade 4", "4", ("GRADE 4",)),
    ("grade_5", "Grade 5", "5", ("GRADE 5",)),
    ("grade_6", "Grade 6", "6", ("GRADE 6",)),
    ("grade_7", "Grade 7", "7", ("GRADE 7",)),
    ("grade_8", "Grade 8", "8", ("GRADE 8",)),
    (
        "grade_9",
        "Grade 9 — World History and Geography: Age of Revolution to Present",
        "9",
        ("GRADE 9",),
    ),
    ("grade_10", "Grade 10", "10", ("GRADE 10",)),
    (
        "grade_11",
        "Grade 11 — United States History II: World War I to Present",
        "11",
        ("GRADE 11",),
    ),
    (
        "grade_12_economics",
        "Grade 12 — Economics",
        "12",
        ("GRADE 12 — ECONOMICS", "GRADE 12 - ECONOMICS", "ECONOMICS"),
    ),
    (
        "grade_12_us_government",
        "Grade 12 — United States Government",
        "12",
        (
            "GRADE 12 — UNITED STATES GOVERNMENT",
            "GRADE 12 - UNITED STATES GOVERNMENT",
            "UNITED STATES GOVERNMENT",
        ),
    ),
    ("psychology", "Psychology", "9-12", ("PSYCHOLOGY",)),
    ("sociology", "Sociology", "9-12", ("SOCIOLOGY",)),
    (
        "contemporary_world_issues",
        "Contemporary World Issues",
        "9-12",
        ("CONTEMPORARY WORLD ISSUES",),
    ),
    ("human_geography", "Human Geography", "9-12", ("HUMAN GEOGRAPHY",)),
    ("historical_studies", "Historical Studies", "9-12", ("HISTORICAL STUDIES",)),
    ("holocaust_studies", "Holocaust Studies", "9-12", ("HOLOCAUST STUDIES",)),
    ("alabama_studies", "Alabama Studies", "9-12", ("ALABAMA STUDIES",)),
)

_MAIN_COMBINED = re.compile(r"^(\d+)\.\s+(.+)$")
_MAIN_DETACHED = re.compile(r"^(\d+)$")
_CHILD_COMBINED = re.compile(r"^(\d+)([a-z])(?:\.|\s)\s*(.+)$")
_CHILD_LETTER = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = (
    "Example:",
    "Examples:",
    "Clarification:",
    "Suggested Activities:",
)


@dataclass(frozen=True, slots=True)
class _CourseSection:
    course_key: str
    display_name: str
    grade_band: str
    heading_index: int


def parse_alabama_social_studies_2024(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    sections = _locate_sections(extracted.lines)
    if len(sections) != len(_COURSES):
        raise StandardsIngestError(
            "Alabama Social Studies parser did not find exactly one standards section for "
            "every expected grade or named course"
        )

    courses: list[ParsedCourse] = []
    for index, section in enumerate(sections):
        end = (
            sections[index + 1].heading_index
            if index + 1 < len(sections)
            else len(extracted.lines)
        )
        standards = _parse_social_studies_standards(
            extracted.lines[section.heading_index + 1 : end]
        )
        if len(standards) < 3:
            raise StandardsIngestError(
                f"Alabama Social Studies {section.display_name} standards structure changed "
                "unexpectedly"
            )
        courses.append(
            ParsedCourse(
                course_key=section.course_key,
                display_name=section.display_name,
                source_course_code=None,
                grade_band=section.grade_band,
                standards=standards,
            )
        )

    return ParsedStandardsDocument(
        parser_key="alabama_social_studies_2024",
        parser_version=SOCIAL_STUDIES_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _locate_sections(lines: tuple[str, ...]) -> tuple[_CourseSection, ...]:
    sections: list[_CourseSection] = []
    used_indexes: set[int] = set()
    for course_key, display_name, grade_band, aliases in _COURSES:
        candidates: list[int] = []
        for index, line in enumerate(lines):
            if index in used_indexes or line not in aliases:
                continue
            if _has_first_standard(lines, index + 1, min(len(lines), index + 90)):
                candidates.append(index)
        if len(candidates) != 1:
            continue
        heading_index = candidates[0]
        used_indexes.add(heading_index)
        sections.append(
            _CourseSection(
                course_key=course_key,
                display_name=display_name,
                grade_band=grade_band,
                heading_index=heading_index,
            )
        )
    return tuple(sorted(sections, key=lambda item: item.heading_index))


def _has_first_standard(lines: tuple[str, ...], start: int, end: int) -> bool:
    return any(
        line == "1" or line.startswith("1. ")
        for line in lines[start:end]
    )


def _parse_social_studies_standards(
    lines: tuple[str, ...],
) -> tuple[ParsedStandard, ...]:
    standards: list[ParsedStandard] = []
    current_main: str | None = None
    current_code: str | None = None
    current_parent: str | None = None
    current_parts: list[str] = []
    skipping_supplement = False

    def flush() -> None:
        nonlocal current_code, current_parent, current_parts
        if current_code is not None:
            text = " ".join(current_parts).strip()
            if text:
                standards.append(
                    ParsedStandard(
                        code=current_code,
                        text=text,
                        parent_code=current_parent,
                        strand="Content Standards",
                    )
                )
        current_code = None
        current_parent = None
        current_parts = []

    for line in lines:
        combined = _MAIN_COMBINED.match(line)
        if combined:
            flush()
            current_main = combined.group(1)
            current_code = current_main
            current_parent = None
            current_parts = [combined.group(2)]
            skipping_supplement = False
            continue

        detached = _MAIN_DETACHED.match(line)
        if detached:
            flush()
            current_main = detached.group(1)
            current_code = current_main
            current_parent = None
            current_parts = []
            skipping_supplement = False
            continue

        child = _CHILD_COMBINED.match(line)
        if child and current_main is not None and child.group(1) == current_main:
            flush()
            current_code = f"{child.group(1)}{child.group(2)}"
            current_parent = current_main
            current_parts = [child.group(3)]
            skipping_supplement = False
            continue

        child_letter = _CHILD_LETTER.match(line)
        if child_letter and current_main is not None:
            flush()
            current_code = f"{current_main}{child_letter.group(1)}"
            current_parent = current_main
            current_parts = [child_letter.group(2)]
            skipping_supplement = False
            continue

        if any(line.startswith(prefix) for prefix in _SUPPLEMENT_PREFIXES):
            skipping_supplement = True
            continue
        if skipping_supplement:
            continue
        if current_code is None or _is_heading_noise(line):
            continue
        current_parts.append(line)

    flush()
    return tuple(standards)


def _is_heading_noise(line: str) -> bool:
    if line.startswith("2024 Alabama Course of Study: Social Studies"):
        return True
    return (
        len(line) <= 90
        and not re.search(r"[.!?;:]$", line)
        and (line.isupper() or line.istitle())
    )
