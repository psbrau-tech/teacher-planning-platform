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

ALABAMA_PARSER_VERSION = "gate-e-alabama-comprehensive-v1"


def parse_alabama_ela_k12(extracted: ExtractedDocument) -> ParsedStandardsDocument:
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
            "Alabama ELA parser did not find exactly one content-standards section for every K-12 grade"
        )

    courses: list[ParsedCourse] = []
    for index, (course_key, display_name, marker, grade_band) in enumerate(course_specs):
        content_start = marker_positions[marker]
        next_content = (
            marker_positions[course_specs[index + 1][2]]
            if index + 1 < len(course_specs)
            else len(extracted.lines)
        )
        recurring_start = _nearest_recurring_marker(
            extracted.lines,
            content_start,
            lower_bound=(
                marker_positions[course_specs[index - 1][2]] + 1 if index > 0 else 0
            ),
        )
        recurring = _parse_numbered_standards(
            extracted.lines[recurring_start + 1 : content_start],
            allow_recurring=True,
            strand="Recurring Standards",
            noise=_ela_noise,
        )
        content_end = _next_recurring_or_limit(
            extracted.lines,
            content_start + 1,
            next_content,
        )
        content = _parse_numbered_standards(
            extracted.lines[content_start + 1 : content_end],
            allow_recurring=False,
            strand="Content Standards",
            noise=_ela_noise,
        )
        if len(recurring) < 4 or len(content) < 5:
            raise StandardsIngestError(
                f"Alabama ELA {display_name} standards structure changed unexpectedly"
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
        parser_version=ALABAMA_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def parse_alabama_cte_course_of_study(
    parser_key: str,
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    markers = [
        index for index, line in enumerate(extracted.lines) if line == "CONTENT STANDARDS"
    ]
    courses: list[ParsedCourse] = []
    seen_keys: set[str] = set()

    for marker in markers:
        title = _nearest_uppercase_title(extracted.lines, marker)
        if not title or title in {"MIDDLE SCHOOL COURSES", "HIGH SCHOOL COURSES"}:
            continue

        content_end = _next_course_boundary(extracted.lines, marker + 1)
        content = _parse_numbered_standards(
            extracted.lines[marker + 1 : content_end],
            allow_recurring=False,
            strand="Content Standards",
            noise=_cte_noise,
        )
        if not content:
            continue

        foundational_start = _previous_foundational_marker(extracted.lines, marker)
        foundational: tuple[ParsedStandard, ...] = ()
        if foundational_start is not None:
            foundational = _parse_numbered_standards(
                extracted.lines[foundational_start + 1 : marker],
                allow_recurring=False,
                strand="Foundational Standards",
                noise=_cte_noise,
            )

        course_key = _slug(title)
        if course_key in seen_keys:
            continue
        seen_keys.add(course_key)
        courses.append(
            ParsedCourse(
                course_key=course_key,
                display_name=title.title(),
                source_course_code=None,
                grade_band=_grade_band_before(extracted.lines, marker),
                standards=foundational + content,
            )
        )

    if not courses:
        raise StandardsIngestError(
            "Alabama CTE Course of Study parser found no complete course standards"
        )
    return ParsedStandardsDocument(
        parser_key=parser_key,
        parser_version=ALABAMA_PARSER_VERSION,
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


def _parse_numbered_standards(
    lines: tuple[str, ...],
    *,
    allow_recurring: bool,
    strand: str,
    noise: Callable[[str], bool],
) -> tuple[ParsedStandard, ...]:
    pattern = re.compile(
        r"^(R\d+|\d+)\.\s*(.+)$" if allow_recurring else r"^(\d+)\.\s*(.+)$"
    )
    child_pattern = re.compile(r"^([a-z])\.\s*(.+)$")
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
        line = _strip_ela_lane_prefix(raw_line) if allow_recurring else raw_line
        match = pattern.match(line)
        if match:
            flush()
            current_code = match.group(1)
            current_parts = [match.group(2)]
            continue
        if current_code is None or noise(line):
            continue
        child = child_pattern.match(line)
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
    if line in {
        "RECEPTION",
        "EXPRESSION",
        "READING",
        "LISTENING",
        "WRITING",
        "SPEAKING",
        "Students will:",
        "Each content standard completes the stem “ Students will…”",
        "Each content standard completes the stem “Students will…”",
    }:
        return True
    return bool(line.isupper() and len(line) <= 70)


def _nearest_uppercase_title(lines: tuple[str, ...], marker_index: int) -> str | None:
    candidates: list[str] = []
    for index in range(marker_index - 1, max(-1, marker_index - 10), -1):
        line = lines[index]
        if "FOUNDATIONAL STANDARDS" in line or line == "FOUNDATIONAL":
            continue
        if line.startswith("20") and "Course of Study" in line:
            continue
        if line.isupper() and 2 <= len(line) <= 120:
            candidates.append(line)
            continue
        if candidates:
            break
    if not candidates:
        return None
    return " ".join(reversed(candidates))


def _previous_foundational_marker(lines: tuple[str, ...], marker_index: int) -> int | None:
    for index in range(marker_index - 1, max(-1, marker_index - 100), -1):
        current = lines[index].lower()
        following = lines[index + 1].lower() if index + 1 < len(lines) else ""
        if "foundational standards" in current:
            return index
        if current == "foundational" and following == "standards":
            return index
    return None


def _next_course_boundary(lines: tuple[str, ...], start: int) -> int:
    for index in range(start, len(lines)):
        current = lines[index].lower()
        following = lines[index + 1].lower() if index + 1 < len(lines) else ""
        if "foundational standards" in current:
            return index
        if current == "foundational" and following == "standards":
            return index
    return len(lines)


def _grade_band_before(lines: tuple[str, ...], marker_index: int) -> str | None:
    for index in range(marker_index - 1, max(-1, marker_index - 80), -1):
        line = lines[index]
        match = re.search(r"Grade Levels?\s*(.*)$", line, flags=re.IGNORECASE)
        if match:
            inline = match.group(1).strip()
            if inline:
                return inline
            if index + 1 < marker_index:
                candidate = lines[index + 1]
                if re.fullmatch(r"\d+(?:-\d+)?", candidate):
                    return candidate
    return None


def _cte_noise(line: str) -> bool:
    if line in {
        "CONTENT STANDARDS",
        "FOUNDATIONAL STANDARDS",
        "FOUNDATIONAL",
        "STANDARDS",
        "Students will:",
    }:
        return True
    if line.startswith("20") and "Course of Study" in line:
        return True
    return bool(line.isupper() and len(line) <= 100)


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "course"
