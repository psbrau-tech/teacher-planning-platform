from __future__ import annotations

import re
from collections import deque

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

SOCIAL_STUDIES_PARSER_VERSION = "gate-e-alabama-social-studies-2024-v6"

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
    (
        "grade_9",
        "Grade 9 — World History and Geography: Age of Revolution to Present",
        "9",
    ),
    ("grade_10", "Grade 10", "10"),
    (
        "grade_11",
        "Grade 11 — United States History II: World War I to Present",
        "11",
    ),
    ("grade_12_economics", "Grade 12 — Economics", "12"),
    (
        "grade_12_us_government",
        "Grade 12 — United States Government",
        "12",
    ),
    ("psychology", "Psychology", "9-12"),
    ("sociology", "Sociology", "9-12"),
    ("contemporary_world_issues", "Contemporary World Issues", "9-12"),
    ("human_geography", "Human Geography", "9-12"),
    ("historical_studies", "Historical Studies", "9-12"),
    ("holocaust_studies", "Holocaust Studies", "9-12"),
    ("alabama_studies", "Alabama Studies", "9-12"),
)

_SOURCE_COURSE_ORDER = (
    "kindergarten",
    "grade_1",
    "grade_2",
    "grade_3",
    "grade_4",
    "grade_5",
    "grade_6",
    "grade_7",
    "grade_8",
    "grade_9",
    "grade_10",
    "grade_11",
    "grade_12_us_government",
    "grade_12_economics",
    "psychology",
    "sociology",
    "contemporary_world_issues",
    "human_geography",
    "historical_studies",
    "holocaust_studies",
    "alabama_studies",
)

_MAIN_COMBINED = re.compile(r"^([1-9]\d?)(?:\.\s+|\s+)(.+)$")
_MAIN_DETACHED = re.compile(r"^([1-9]\d?)$")
_CHILD_COMBINED = re.compile(r"^(\d+)([a-z])(?:\.|\s)\s*(.+)$")
_CHILD_LETTER = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = (
    "Example:",
    "Examples:",
    "Clarification:",
    "Suggested Activities:",
)
_DIRECTION_PREFIXES = (
    "Please refer to Directions for Interpreting Standards",
    "Each content standard completes the stem Students will",
)
_SOURCE_FOOTER = "2024 Alabama Course of Study: Social Studies"


def parse_alabama_social_studies_2024(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    markers = _content_standard_markers(extracted.lines)
    if len(markers) != len(_SOURCE_COURSE_ORDER):
        raise StandardsIngestError(
            "Alabama Social Studies parser did not find exactly one Content Standards "
            "section for every expected grade or named course"
        )

    marker_by_course = dict(zip(_SOURCE_COURSE_ORDER, markers, strict=True))
    courses: list[ParsedCourse] = []
    for course_key, display_name, grade_band in _COURSES:
        marker_index = marker_by_course[course_key]
        next_marker = _next_marker_after(marker_index, markers, len(extracted.lines))
        end = _next_course_boundary(extracted.lines, marker_index, next_marker)
        detached_before = tuple(
            code
            for _, code in _detached_entries_before_marker(
                extracted.lines,
                marker_index,
            )
        )
        standards = _parse_social_studies_standards(
            extracted.lines[marker_index + 1 : end],
            initial_detached=detached_before,
        )
        if len(standards) < 3:
            raise StandardsIngestError(
                f"Alabama Social Studies {display_name} standards structure changed "
                "unexpectedly"
            )
        # Source identifiers are provenance, not generated primary keys. The authoritative
        # 2024 source contains at least one repeated printed identifier (Government 11b).
        # Preserve both entries exactly rather than silently renumbering source text.
        courses.append(
            ParsedCourse(
                course_key=course_key,
                display_name=display_name,
                source_course_code="Content Standards",
                grade_band=grade_band,
                standards=standards,
            )
        )

    return ParsedStandardsDocument(
        parser_key="alabama_social_studies_2024",
        parser_version=SOCIAL_STUDIES_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _content_standard_markers(lines: tuple[str, ...]) -> list[int]:
    return [
        index
        for index, line in enumerate(lines)
        if line.lower().replace(" ", "") in {"contentstandards", "contentstandard"}
    ]


def _next_marker_after(
    marker_index: int,
    markers: list[int],
    document_length: int,
) -> int:
    return next(
        (candidate for candidate in markers if candidate > marker_index),
        document_length,
    )


def _next_course_boundary(
    lines: tuple[str, ...],
    marker_index: int,
    next_marker: int,
) -> int:
    if next_marker >= len(lines):
        return next_marker

    for index in range(marker_index + 1, next_marker):
        if lines[index].strip().lower() == "course topics:":
            return index

    next_prelude = _detached_entries_before_marker(lines, next_marker)
    return next_prelude[0][0] if next_prelude else next_marker


def _detached_entries_before_marker(
    lines: tuple[str, ...],
    marker_index: int,
) -> tuple[tuple[int, str], ...]:
    footer_index: int | None = None
    for index in range(marker_index - 1, max(-1, marker_index - 40), -1):
        if lines[index].startswith(_SOURCE_FOOTER):
            footer_index = index
            break
    if footer_index is None:
        return ()

    entries: list[tuple[int, str]] = []
    for index in range(footer_index + 1, marker_index):
        match = _MAIN_DETACHED.fullmatch(lines[index].strip())
        if match is not None:
            entries.append((index, match.group(1)))
    return tuple(entries)


def _parse_social_studies_standards(
    lines: tuple[str, ...],
    *,
    initial_detached: tuple[str, ...] = (),
) -> tuple[ParsedStandard, ...]:
    standards: list[ParsedStandard] = []
    pending_main: deque[str] = deque(initial_detached)
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

    def begin_pending(line: str) -> bool:
        nonlocal current_main, current_code, current_parent, current_parts
        if current_code is not None or not pending_main:
            return False
        current_main = pending_main.popleft()
        current_code = current_main
        current_parent = None
        current_parts = [line]
        return True

    for raw_line in lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line.startswith(_SOURCE_FOOTER) or line.startswith(_DIRECTION_PREFIXES):
            continue

        child = _CHILD_COMBINED.match(line)
        if child:
            if current_code is None and pending_main:
                current_main = pending_main.popleft()
                current_code = current_main
            if current_main is not None and child.group(1) == current_main:
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

        combined = _MAIN_COMBINED.match(line)
        if combined:
            flush()
            pending_main.clear()
            current_main = combined.group(1)
            current_code = current_main
            current_parent = None
            current_parts = [combined.group(2)]
            skipping_supplement = False
            continue

        detached = _MAIN_DETACHED.fullmatch(line)
        if detached:
            flush()
            pending_main.append(detached.group(1))
            skipping_supplement = False
            continue

        if any(line.startswith(prefix) for prefix in _SUPPLEMENT_PREFIXES):
            skipping_supplement = True
            continue
        if skipping_supplement or _is_heading_noise(line):
            continue

        if begin_pending(line):
            if pending_main and _ends_sentence(line):
                flush()
            continue
        if current_code is None:
            continue
        current_parts.append(line)
        if current_parent is None and pending_main and _ends_sentence(line):
            flush()

    flush()
    if pending_main:
        raise StandardsIngestError(
            "Alabama Social Studies contained detached standards without authoritative text"
        )
    return tuple(standards)


def _ends_sentence(line: str) -> bool:
    return bool(re.search(r"[.!?]$", line))


def _is_heading_noise(line: str) -> bool:
    if line.startswith(_SOURCE_FOOTER):
        return True
    return (
        len(line) <= 90
        and not re.search(r"[.!?;:]$", line)
        and (line.isupper() or line.istitle())
    )
