from __future__ import annotations

import re

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

MATH_PARSER_VERSION = "gate-e-alabama-math-2019-v1"
_COURSES = (
    ("kindergarten", "Kindergarten", "K"),
    ("grade_1", "Grade 1", "1"),
    ("grade_2", "Grade 2", "2"),
    ("grade_3", "Grade 3", "3"),
    ("grade_4", "Grade 4", "4"),
    ("grade_5", "Grade 5", "5"),
    ("grade_6", "Grade 6", "6"),
    ("grade_7", "Grade 7", "7"),
    ("grade_7_accelerated", "Grade 7 Accelerated", "7"),
    ("grade_8", "Grade 8", "8"),
    ("grade_8_accelerated", "Grade 8 Accelerated", "8"),
    ("geometry_data_analysis", "Geometry with Data Analysis", "9-12"),
    ("algebra_i_probability", "Algebra I with Probability", "9-12"),
    ("algebra_ii_statistics", "Algebra II with Statistics", "9-12"),
    ("mathematical_modeling", "Mathematical Modeling", "9-12"),
    (
        "applications_finite_mathematics",
        "Applications of Finite Mathematics",
        "9-12",
    ),
    ("precalculus", "Precalculus", "9-12"),
)
_MAIN = re.compile(r"^(\d+)\.\s+(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = (
    "Example:",
    "Examples:",
    "Note:",
    "Notes:",
    "Clarification:",
)


def parse_alabama_math_2019(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    markers = {
        display_name: _unique_index(extracted.lines, f"{display_name} Content Standards")
        for _, display_name, _ in _COURSES
    }
    if any(index is None for index in markers.values()):
        raise StandardsIngestError(
            "Alabama Mathematics parser did not find exactly one content-standards section "
            "for every expected K-12 mathematics course"
        )

    practices = _parse_student_mathematical_practices(extracted.lines)
    if len(practices) != 8:
        raise StandardsIngestError(
            "Alabama Mathematics parser did not find all eight Student Mathematical "
            "Practices"
        )

    ordered_markers = [
        int(markers[display_name]) for _, display_name, _ in _COURSES
    ]
    courses: list[ParsedCourse] = []
    for index, (course_key, display_name, grade_band) in enumerate(_COURSES):
        start = ordered_markers[index] + 1
        end = (
            ordered_markers[index + 1]
            if index + 1 < len(ordered_markers)
            else len(extracted.lines)
        )
        content = _parse_math_content(extracted.lines[start:end])
        if len(content) < 3:
            raise StandardsIngestError(
                f"Alabama Mathematics {display_name} standards structure changed "
                "unexpectedly"
            )
        courses.append(
            ParsedCourse(
                course_key=course_key,
                display_name=display_name,
                source_course_code=f"{display_name} Content Standards",
                grade_band=grade_band,
                standards=practices + content,
            )
        )

    return ParsedStandardsDocument(
        parser_key="alabama_math_2019",
        parser_version=MATH_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _parse_student_mathematical_practices(
    lines: tuple[str, ...],
) -> tuple[ParsedStandard, ...]:
    marker_indexes = [
        index
        for index, line in enumerate(lines)
        if "STUDENT MATHEMATICAL PRACTICES" in line.upper()
    ]
    for marker in marker_indexes:
        raw = _parse_numbered_block(
            lines[marker + 1 : min(len(lines), marker + 160)],
            strand="Student Mathematical Practices",
            stop_after=8,
        )
        expected_codes = [str(number) for number in range(1, 9)]
        if len(raw) == 8 and [item.code for item in raw] == expected_codes:
            return tuple(
                ParsedStandard(
                    code=f"SMP{item.code}",
                    text=item.text,
                    parent_code=None,
                    strand="Student Mathematical Practices",
                )
                for item in raw
            )
    return ()


def _parse_math_content(lines: tuple[str, ...]) -> tuple[ParsedStandard, ...]:
    return _parse_numbered_block(lines, strand="Content Standards")


def _parse_numbered_block(
    lines: tuple[str, ...],
    *,
    strand: str,
    stop_after: int | None = None,
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
                        strand=strand,
                    )
                )
        current_code = None
        current_parent = None
        current_parts = []

    for line in lines:
        main = _MAIN.match(line)
        if main:
            if stop_after is not None and int(main.group(1)) > stop_after:
                flush()
                break
            flush()
            current_main = main.group(1)
            current_code = current_main
            current_parent = None
            current_parts = [main.group(2)]
            skipping_supplement = False
            continue

        child = _CHILD.match(line)
        if child and current_main is not None:
            flush()
            current_code = f"{current_main}{child.group(1)}"
            current_parent = current_main
            current_parts = [child.group(2)]
            skipping_supplement = False
            continue

        if any(line.startswith(prefix) for prefix in _SUPPLEMENT_PREFIXES):
            skipping_supplement = True
            continue
        if skipping_supplement:
            continue
        if current_code is None or _is_math_heading(line):
            continue
        current_parts.append(line)

    flush()
    if stop_after is not None:
        standards = [
            item
            for item in standards
            if item.parent_code is not None or int(item.code) <= stop_after
        ]
    return tuple(standards)


def _is_math_heading(line: str) -> bool:
    if line.startswith("2019 Alabama Course of Study: Mathematics"):
        return True
    if line.endswith("Content Standards"):
        return True
    return (
        len(line) <= 85
        and not re.search(r"[.!?;:]$", line)
        and (line.isupper() or line.istitle())
    )


def _unique_index(lines: tuple[str, ...], marker: str) -> int | None:
    positions = [index for index, line in enumerate(lines) if line == marker]
    return positions[0] if len(positions) == 1 else None
