from __future__ import annotations

import re
from collections.abc import Callable

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

ELA_PARSER_VERSION = "gate-e-alabama-ela-2021-v3"
_RECURRING = re.compile(r"^(R\d+)\.\s*(.+)$")
_CONTENT = re.compile(r"^(\d+)\.\s*(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s*(.+)$")


def parse_alabama_ela_2021(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    course_specs = [
        ("kindergarten", "Kindergarten", "KINDERGARTEN CONTENT STANDARDS", "K"),
        *[
            (f"grade_{grade}", f"Grade {grade}", f"GRADE {grade} CONTENT STANDARDS", str(grade))
            for grade in range(1, 13)
        ],
    ]
    marker_positions = _unique_marker_positions(
        extracted.lines,
        tuple(spec[2] for spec in course_specs),
    )
    if len(marker_positions) != len(course_specs):
        raise StandardsIngestError(
            "Alabama ELA parser did not find exactly one content-standards section "
            "for every K-12 grade"
        )

    courses: list[ParsedCourse] = []
    for index, (course_key, display_name, marker, grade_band) in enumerate(course_specs):
        content_start = marker_positions[marker]
        next_content = (
            marker_positions[course_specs[index + 1][2]]
            if index + 1 < len(course_specs)
            else len(extracted.lines)
        )
        lower_bound = marker_positions[course_specs[index - 1][2]] + 1 if index > 0 else 0
        recurring_start = _nearest_recurring_marker(
            extracted.lines,
            content_start,
            lower_bound=lower_bound,
        )
        grade_end = _next_recurring_or_limit(
            extracted.lines,
            content_start + 1,
            next_content,
        )

        # The authoritative 2021 PDF can split the recurring-standards table
        # across a page boundary. In Grade 2, R1-R3 occur before the content
        # heading while R4-R5 occur immediately after it. Collect only R-coded
        # rows across the whole bounded grade section; numeric content rows are
        # parsed independently below.
        recurring = _parse_standards(
            extracted.lines[recurring_start + 1 : grade_end],
            pattern=_RECURRING,
            strand="Recurring Standards",
            noise=_ela_noise,
            strip_lane_prefix=True,
        )
        content = _parse_standards(
            extracted.lines[content_start + 1 : grade_end],
            pattern=_CONTENT,
            strand="Content Standards",
            noise=_ela_noise,
            strip_lane_prefix=False,
        )
        if len(recurring) < 4 or len(content) < 5:
            raise StandardsIngestError(
                f"Alabama ELA {display_name} standards structure changed unexpectedly"
            )
        recurring_codes = [standard.code for standard in recurring]
        if len(recurring_codes) != len(set(recurring_codes)):
            raise StandardsIngestError(
                f"Alabama ELA {display_name} produced duplicate recurring standards identifiers"
            )
        content_codes = [standard.code for standard in content]
        if len(content_codes) != len(set(content_codes)):
            raise StandardsIngestError(
                f"Alabama ELA {display_name} produced duplicate content standards identifiers"
            )
        courses.append(
            ParsedCourse(
                course_key=course_key,
                display_name=display_name,
                source_course_code=marker,
                grade_band=grade_band,
                standards=recurring + content,
            )
        )

    return ParsedStandardsDocument(
        parser_key="alabama_ela_2021",
        parser_version=ELA_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _unique_marker_positions(
    lines: tuple[str, ...],
    markers: tuple[str, ...],
) -> dict[str, int]:
    positions: dict[str, int] = {}
    for marker in markers:
        found = [index for index, line in enumerate(lines) if line == marker]
        if len(found) == 1:
            positions[marker] = found[0]
    return positions


def _nearest_recurring_marker(
    lines: tuple[str, ...],
    content_start: int,
    *,
    lower_bound: int,
) -> int:
    for index in range(content_start - 1, lower_bound - 1, -1):
        if lines[index].startswith("RECURRING STANDARDS FOR"):
            return index
    raise StandardsIngestError(
        "Alabama ELA recurring-standards section was not found for a grade"
    )


def _next_recurring_or_limit(
    lines: tuple[str, ...],
    start: int,
    limit: int,
) -> int:
    for index in range(start, limit):
        if lines[index].startswith("RECURRING STANDARDS FOR"):
            return index
    return limit


def _parse_standards(
    lines: tuple[str, ...],
    *,
    pattern: re.Pattern[str],
    strand: str,
    noise: Callable[[str], bool],
    strip_lane_prefix: bool,
) -> tuple[ParsedStandard, ...]:
    standards: list[ParsedStandard] = []
    current_code: str | None = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_code, current_parts
        if current_code is not None:
            text = " ".join(current_parts).strip()
            if text:
                standards.append(
                    ParsedStandard(
                        code=current_code,
                        text=text,
                        strand=strand,
                    )
                )
        current_code = None
        current_parts = []

    for raw_line in lines:
        line = _strip_ela_lane_prefix(raw_line) if strip_lane_prefix else raw_line
        match = pattern.match(line)
        if match:
            flush()
            current_code = match.group(1)
            current_parts = [match.group(2)]
            continue

        # A different standards family starts a new row. Flush the current
        # standard and ignore that row rather than appending its wording.
        if pattern is _RECURRING and _CONTENT.match(line):
            flush()
            continue
        if pattern is _CONTENT and _RECURRING.match(line):
            flush()
            continue

        if current_code is None or noise(line):
            continue
        child = _CHILD.match(line)
        if child:
            current_parts.append(f"{child.group(1)}. {child.group(2)}")
        elif not re.fullmatch(r"\d+(?:\.\d+)?", line):
            current_parts.append(line)

    flush()
    return tuple(standards)


def _strip_ela_lane_prefix(line: str) -> str:
    prefixes = (
        "RECEPTION READING ",
        "EXPRESSION WRITING ",
        "RECEPTION LISTENING ",
        "EXPRESSION SPEAKING ",
        "READING ",
        "LISTENING ",
        "WRITING ",
        "SPEAKING ",
    )
    for prefix in prefixes:
        if line.startswith(prefix):
            candidate = line[len(prefix) :].strip()
            if re.match(r"^(?:R\d+|\d+)\.", candidate):
                return candidate
    return line


def _ela_noise(line: str) -> bool:
    if line.startswith("2021 Alabama Course of Study:"):
        return True
    if line.startswith("RECURRING STANDARDS FOR"):
        return True
    if line.endswith("CONTENT STANDARDS"):
        return True
    if line.startswith("Standard ") and "continued" in line:
        return True
    normalized = line.strip().casefold()
    if normalized in {
        "reception",
        "expression",
        "reading",
        "listening",
        "writing",
        "speaking",
        "students will:",
        "each content standard completes the stem “ students will…”",
        "each content standard completes the stem “students will…”",
    }:
        return True
    return bool(line.isupper() and len(line) <= 70)
