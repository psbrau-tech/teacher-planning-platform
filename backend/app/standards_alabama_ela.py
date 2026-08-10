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

ELA_PARSER_VERSION = "gate-e-alabama-ela-2021-v4"
_RECURRING = re.compile(r"^(R\d+)\.\s*(.+)$")
_CONTENT = re.compile(r"^(\d+)\.\s*(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s*(.+)$")
_PAGE_GRADE = re.compile(r"^Grade\s+(?:K|[1-9]|1[0-2])$", flags=re.IGNORECASE)
_LANE_LABEL = re.compile(r"^(?:RECEPTION|EXPRESSION|READING|LISTENING|WRITING|SPEAKING)$")
_LANE_STANDARD_PREFIX = re.compile(
    r"^(?:(?:RECEPTION|EXPRESSION|READING|LISTENING|WRITING|SPEAKING)\s+){1,2}"
    r"(?=(?:R\d+|\d+)\.)"
)
_INLINE_LANE_STANDARD = re.compile(
    r"(?=\b(?:(?:RECEPTION|EXPRESSION|READING|LISTENING|WRITING|SPEAKING)\s+){1,2}"
    r"(?:R\d+|\d+)\.\s*)"
)
_EMBEDDED_STANDARD = re.compile(r"\b(?:R\d+|\d{1,2})\.\s+[A-Z]")
_EXPECTED_CONTENT_MAX = {
    "K": 40,
    "1": 43,
    "2": 46,
    "3": 42,
    "4": 42,
    "5": 42,
    "6": 30,
    "7": 33,
    "8": 32,
    "9": 27,
    "10": 27,
    "11": 30,
    "12": 30,
}
_SECTION_BOUNDARIES = {
    "LITERACY FOUNDATIONS",
    "CRITICAL LITERACY",
    "DIGITAL LITERACY",
    "LANGUAGE LITERACY",
    "RESEARCH LITERACY",
    "VOCABULARY LITERACY",
    "Oral Language",
    "Phonological Awareness/Phonemic Awareness",
    "Phonics",
    "Fluency",
    "Vocabulary",
    "Comprehension",
    "Written Expression",
}


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
            strip_lane_prefix=True,
        )
        _validate_grade_materialization(
            display_name=display_name,
            grade_band=grade_band,
            recurring=recurring,
            content=content,
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
        for raw_fragment in _ela_fragments(raw_line):
            line = _strip_ela_lane_prefix(raw_fragment) if strip_lane_prefix else raw_fragment
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

            # Major section and next-grade headings are structural boundaries.
            # They end the preceding standard; following overview prose is then
            # ignored until the next numbered row starts.
            if _ela_boundary(line):
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


def _ela_fragments(line: str) -> tuple[str, ...]:
    """Split table-lane numbered rows that pypdf places inside neighboring lines."""
    starts = [match.start() for match in _INLINE_LANE_STANDARD.finditer(line)]
    if not starts:
        return (line,)
    boundaries = sorted({0, *starts, len(line)})
    fragments = tuple(
        line[boundaries[index] : boundaries[index + 1]].strip()
        for index in range(len(boundaries) - 1)
        if line[boundaries[index] : boundaries[index + 1]].strip()
    )
    return fragments or (line,)


def _strip_ela_lane_prefix(line: str) -> str:
    return _LANE_STANDARD_PREFIX.sub("", line, count=1).strip()


def _ela_boundary(line: str) -> bool:
    if line in _SECTION_BOUNDARIES:
        return True
    if re.fullmatch(r"GRADE (?:[1-9]|1[0-2])", line):
        return True
    if line == "KINDERGARTEN":
        return True
    if line.endswith("CONTENT STANDARDS"):
        return True
    return bool(line.isupper() and "LITERACY" in line and len(line) <= 80)


def _ela_noise(line: str) -> bool:
    if line.startswith("2021 Alabama Course of Study:"):
        return True
    if line.startswith("RECURRING STANDARDS FOR"):
        return True
    if line.startswith("Standard ") and "continued" in line:
        return True
    if _PAGE_GRADE.fullmatch(line):
        return True
    if _LANE_LABEL.fullmatch(line):
        return True
    normalized = line.strip().casefold()
    if normalized in {
        "students will:",
        "each content standard completes the stem “ students will…”",
        "each content standard completes the stem “students will…”",
    }:
        return True
    return False


def _validate_grade_materialization(
    *,
    display_name: str,
    grade_band: str,
    recurring: tuple[ParsedStandard, ...],
    content: tuple[ParsedStandard, ...],
) -> None:
    expected_recurring_max = 5 if grade_band in {"K", "1", "2", "3"} else 6 if grade_band in {
        "4",
        "5",
        "6",
        "7",
        "8",
    } else 7
    expected_recurring = [f"R{number}" for number in range(1, expected_recurring_max + 1)]
    recurring_codes = [standard.code for standard in recurring]
    if recurring_codes != expected_recurring:
        raise StandardsIngestError(
            f"Alabama ELA {display_name} recurring standards are incomplete or out of order"
        )

    expected_content_max = _EXPECTED_CONTENT_MAX[grade_band]
    expected_content = [str(number) for number in range(1, expected_content_max + 1)]
    content_codes = [standard.code for standard in content]
    if content_codes != expected_content:
        raise StandardsIngestError(
            f"Alabama ELA {display_name} content standards are incomplete or out of order"
        )

    for standard in recurring + content:
        _validate_standard_text(display_name, standard)


def _validate_standard_text(display_name: str, standard: ParsedStandard) -> None:
    text = standard.text
    forbidden = (
        "2021 Alabama Course of Study:",
        "Each content standard completes the stem",
    )
    if any(token in text for token in forbidden):
        raise StandardsIngestError(
            f"Alabama ELA {display_name} standard {standard.code} contains page boilerplate"
        )
    if re.search(r"\bGrade\s+(?:K|[1-9]|1[0-2])\b", text):
        raise StandardsIngestError(
            f"Alabama ELA {display_name} standard {standard.code} contains a page-grade header"
        )
    if _INLINE_LANE_STANDARD.search(text) or _EMBEDDED_STANDARD.search(text):
        raise StandardsIngestError(
            f"Alabama ELA {display_name} standard {standard.code} contains another standard row"
        )
