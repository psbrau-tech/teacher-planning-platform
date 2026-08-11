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

SCIENCE_PARSER_VERSION = "gate-e-alabama-science-2023-v2"
_STEM_PREFIX = "Each content standard completes the stem"
_COURSE_HEADING_LOOKBACK = 30
_COURSES = (
    ("kindergarten", "Kindergarten", "K"),
    ("grade_1", "Grade 1", "1"),
    ("grade_2", "Grade 2", "2"),
    ("grade_3", "Grade 3", "3"),
    ("grade_4", "Grade 4", "4"),
    ("grade_5", "Grade 5", "5"),
    ("grade_6", "Grade 6", "6"),
    ("grade_7", "Grade 7", "7"),
    ("grade_8", "Grade 8", "8"),
    ("biology", "Biology", "9-12"),
    ("chemistry", "Chemistry", "9-12"),
    ("earth_space_science", "Earth and Space Science", "9-12"),
    ("environmental_science", "Environmental Science", "9-12"),
    ("human_anatomy_physiology", "Human Anatomy and Physiology", "9-12"),
    ("physical_science", "Physical Science", "9-12"),
    ("physics", "Physics", "9-12"),
)

_MAIN_STANDARD = re.compile(r"^(\d+)\.\s+(.+)$")
_CHILD_STANDARD = re.compile(r"^([a-z])\.\s+(.+)$")
_EXAMPLE_PREFIXES = ("Example:", "Examples:", "Clarification:")
_CROSSCUTTING_PHRASES = frozenset(
    {
        "patterns",
        "cause and effect",
        "mechanism and prediction",
        "scale, proportion, and quantity",
        "systems and system models",
        "energy and matter",
        "flows, cycles, and conservation",
        "structure and function",
        "stability and change",
        "cause",
        "and effect",
        "scale",
        "proportion",
        "and quantity",
        "systems",
        "and system",
        "models",
        "energy",
        "and matter",
        "structure",
        "and function",
        "stability",
        "and change",
    }
)


@dataclass(frozen=True, slots=True)
class _CourseSection:
    course_key: str
    display_name: str
    grade_band: str
    marker_index: int


def parse_alabama_science_2023(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    sections = _locate_course_sections(extracted.lines)
    if len(sections) != len(_COURSES):
        raise StandardsIngestError(
            "Alabama Science parser did not find exactly one standards section for every "
            "expected K-12 grade or high-school science course"
        )

    courses: list[ParsedCourse] = []
    for index, section in enumerate(sections):
        end = (
            sections[index + 1].marker_index
            if index + 1 < len(sections)
            else len(extracted.lines)
        )
        standards = _parse_science_standards(
            extracted.lines[section.marker_index + 1 : end]
        )
        if len(standards) < 3:
            raise StandardsIngestError(
                f"Alabama Science {section.display_name} standards structure changed "
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
        parser_key="alabama_science_2023",
        parser_version=SCIENCE_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _locate_course_sections(lines: tuple[str, ...]) -> tuple[_CourseSection, ...]:
    markers = tuple(
        index for index, line in enumerate(lines) if line.startswith(_STEM_PREFIX)
    )
    if len(markers) != len(_COURSES):
        return ()

    sections: list[_CourseSection] = []
    for (course_key, display_name, grade_band), marker_index in zip(
        _COURSES,
        markers,
        strict=True,
    ):
        context = lines[max(0, marker_index - _COURSE_HEADING_LOOKBACK) : marker_index]
        if display_name not in context:
            return ()
        sections.append(
            _CourseSection(
                course_key=course_key,
                display_name=display_name,
                grade_band=grade_band,
                marker_index=marker_index,
            )
        )
    return tuple(sections)


def _parse_science_standards(lines: tuple[str, ...]) -> tuple[ParsedStandard, ...]:
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
        main = _MAIN_STANDARD.match(line)
        if main:
            flush()
            current_main = main.group(1)
            current_code = current_main
            current_parent = None
            current_parts = [main.group(2)]
            skipping_supplement = False
            continue

        child = _CHILD_STANDARD.match(line)
        if child and current_main is not None:
            flush()
            current_code = f"{current_main}{child.group(1)}"
            current_parent = current_main
            current_parts = [child.group(2)]
            skipping_supplement = False
            continue

        if any(line.startswith(prefix) for prefix in _EXAMPLE_PREFIXES):
            skipping_supplement = True
            continue
        if skipping_supplement:
            continue
        if current_code is None or _is_science_table_noise(line):
            continue
        current_parts.append(line)

    flush()
    return tuple(standards)


def _is_science_table_noise(line: str) -> bool:
    normalized = re.sub(r"\s+", " ", line).strip().lower().rstrip(":")
    if normalized in _CROSSCUTTING_PHRASES:
        return True
    if line.startswith("2023 Alabama Course of Study: Science"):
        return True
    if line.startswith(_STEM_PREFIX):
        return True
    return len(line) <= 55 and line.istitle() and not re.search(r"[.!?]$", line)
