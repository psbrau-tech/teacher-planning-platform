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

ARTS_PARSER_VERSION = "gate-e-alabama-arts-2024-v2"
_EXPECTED_SECTION_COUNT = 33
_DISCIPLINES = ("DANCE", "MEDIA ARTS", "MUSIC", "THEATRE", "VISUAL ARTS")
_NUMBERED = re.compile(r"^(\d+)\.\s+(.+)$")
_NUMBERED_SPLIT = re.compile(r"(?=\d+\.\s)")
_CONTEXT_PREFIXES = (
    "Anchor Standard",
    "Process Component:",
    "Enduring Understanding:",
    "Essential Question:",
    "Essential Questions:",
    "EU:",
    "Example:",
    "Examples:",
)
_STRAND_HEADINGS = {
    "CREATING": "Creating",
    "PERFORMING": "Performing",
    "PRESENTING": "Presenting",
    "PRODUCING": "Producing",
    "RESPONDING": "Responding",
    "CONNECTING": "Connecting",
}
_ANCHOR_TEXT = {
    1: "Generate and conceptualize artistic ideas and work.",
    2: "Organize and develop artistic ideas and work.",
    3: "Refine and complete artistic work.",
    4: "Select, analyze, and interpret artistic work for presentation.",
    5: "Develop and refine artistic techniques and work for presentation.",
    6: "Convey meaning through the presentation of artistic work.",
    7: "Perceive and analyze artistic work.",
    8: "Interpret intent and meaning in artistic work.",
    9: "Apply criteria to evaluate artistic work.",
    10: "Synthesize and relate knowledge and personal experiences to make art.",
    11: (
        "Relate artistic ideas and works with societal, cultural, and historical "
        "context to deepen understanding."
    ),
}
_ANCHOR_TEXT_VALUES = frozenset(_ANCHOR_TEXT.values())
_LANE_TOKEN = re.compile(
    r"Kindergarten|Grade \d+|MS Level [123]|HS Level (?:IV|III|II|I)|"
    r"Level (?:IV|III|II|I)"
)


@dataclass(frozen=True, slots=True)
class _Section:
    marker_index: int
    end_index: int
    discipline: str
    section_name: str
    lanes: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True, slots=True)
class _Entry:
    code: str
    text: str
    strand: str | None


def parse_alabama_arts_2024(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    markers = tuple(
        index for index, line in enumerate(extracted.lines) if line == "Content Standards"
    )
    if len(markers) != _EXPECTED_SECTION_COUNT:
        raise StandardsIngestError(
            "Alabama Arts parser expected exactly "
            f"{_EXPECTED_SECTION_COUNT} authoritative Content Standards sections "
            f"but found {len(markers)}"
        )

    sections = _discover_sections(extracted.lines, markers)
    courses: list[ParsedCourse] = []
    for section in sections:
        courses.extend(_parse_section(extracted.lines, section))

    if not courses:
        raise StandardsIngestError("Alabama Arts parser produced no teacher-facing courses")
    if len({course.course_key for course in courses}) != len(courses):
        raise StandardsIngestError("Alabama Arts parser produced duplicate course identifiers")
    if any(not course.standards for course in courses):
        raise StandardsIngestError("Alabama Arts parser produced a course without standards")

    return ParsedStandardsDocument(
        parser_key="alabama_arts_2024",
        parser_version=ARTS_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _discover_sections(
    lines: tuple[str, ...],
    markers: tuple[int, ...],
) -> tuple[_Section, ...]:
    sections: list[_Section] = []
    for position, marker in enumerate(markers):
        end = markers[position + 1] if position + 1 < len(markers) else len(lines)
        discipline = _nearest_discipline(lines, marker)
        section_name = _section_name(lines, marker, discipline)
        lanes = _discover_lanes(lines[marker + 1 : end], section_name)
        sections.append(
            _Section(
                marker_index=marker,
                end_index=end,
                discipline=discipline,
                section_name=section_name,
                lanes=lanes,
            )
        )
    return tuple(sections)


def _nearest_discipline(lines: tuple[str, ...], marker: int) -> str:
    for index in range(marker - 1, -1, -1):
        if lines[index] in _DISCIPLINES:
            return lines[index]
    raise StandardsIngestError(
        "Alabama Arts parser could not identify the discipline for a Content Standards section"
    )


def _section_name(lines: tuple[str, ...], marker: int, discipline: str) -> str:
    for index in range(marker - 1, max(-1, marker - 6), -1):
        candidate = lines[index]
        if candidate == discipline or candidate == "Content Standards":
            continue
        if candidate.startswith("2024 Alabama Course of Study:"):
            continue
        return candidate
    raise StandardsIngestError("Alabama Arts parser could not identify a section name")


def _discover_lanes(
    lines: tuple[str, ...],
    section_name: str,
) -> tuple[tuple[str, str | None], ...]:
    best: tuple[str, ...] = ()
    for line in lines:
        tokens = _lane_tokens(line)
        if len(tokens) > len(best):
            best = tokens
        if len(best) >= 4:
            break

    if len(best) >= 2:
        return tuple((token, _grade_band(token, section_name)) for token in best)
    return ((section_name, _grade_band(section_name, section_name)),)


def _lane_tokens(line: str) -> tuple[str, ...]:
    tokens = tuple(match.group(0) for match in _LANE_TOKEN.finditer(line))
    if len(tokens) < 2:
        return ()
    compact = " ".join(tokens)
    normalized_line = re.sub(r"\s+", " ", line).strip()
    if compact not in normalized_line:
        return ()
    return tokens


def _grade_band(label: str, section_name: str) -> str | None:
    if label == "Kindergarten":
        return "K"
    grade = re.fullmatch(r"Grade (\d+)", label)
    if grade is not None:
        return grade.group(1)
    context = f"{section_name} {label}"
    if "6-8" in context or "Middle School" in context or label.startswith("MS Level"):
        return "6-8"
    if "9-12" in context or "High School" in context or label.startswith("HS Level"):
        return "9-12"
    return None


def _parse_section(lines: tuple[str, ...], section: _Section) -> list[ParsedCourse]:
    section_lines = lines[section.marker_index + 1 : section.end_index]
    standards_by_lane: list[list[ParsedStandard]] = [[] for _ in section.lanes]
    segments = _extract_segments(section_lines, section)
    for entries in segments:
        _assign_segment(section, entries, standards_by_lane)

    courses: list[ParsedCourse] = []
    for (lane_name, grade_band), standards in zip(
        section.lanes,
        standards_by_lane,
        strict=True,
    ):
        if not standards:
            raise StandardsIngestError(
                f"Alabama Arts {section.discipline} {lane_name} produced no standards"
            )
        display_name = _display_name(section.discipline, section.section_name, lane_name)
        courses.append(
            ParsedCourse(
                course_key=_course_key(
                    section.discipline,
                    section.section_name,
                    lane_name,
                ),
                display_name=display_name,
                source_course_code=section.section_name,
                grade_band=grade_band,
                standards=tuple(standards),
            )
        )
    return courses


def _extract_segments(
    lines: tuple[str, ...],
    section: _Section,
) -> tuple[tuple[_Entry, ...], ...]:
    segments: list[tuple[_Entry, ...]] = []
    current_entries: list[_Entry] = []
    current_code: str | None = None
    current_parts: list[str] = []
    current_strand: str | None = None
    skipping_context = False

    def flush_entry() -> None:
        nonlocal current_code, current_parts
        if current_code is not None:
            text = " ".join(current_parts).strip()
            if text:
                current_entries.append(
                    _Entry(code=current_code, text=text, strand=current_strand)
                )
        current_code = None
        current_parts = []

    def flush_segment() -> None:
        flush_entry()
        if current_entries:
            segments.append(tuple(current_entries))
            current_entries.clear()

    for line in lines:
        lane_tokens = _lane_tokens(line)
        if lane_tokens:
            flush_segment()
            skipping_context = False
            continue

        if line in _STRAND_HEADINGS:
            flush_entry()
            current_strand = _STRAND_HEADINGS[line]
            skipping_context = False
            continue

        if line == "Anchor Standards":
            flush_entry()
            skipping_context = True
            continue
        if line.startswith("Process Component:"):
            flush_entry()
            skipping_context = True
            continue
        if line.startswith(_CONTEXT_PREFIXES):
            flush_entry()
            skipping_context = True
            continue

        pieces = _numbered_pieces(line)
        if pieces:
            for code, text in pieces:
                if text in _ANCHOR_TEXT_VALUES:
                    continue
                flush_entry()
                current_code = code
                current_parts = [text]
                skipping_context = False
            continue

        if skipping_context or current_code is None or _is_noise(line, section):
            continue
        current_parts.append(line)

    flush_segment()
    return tuple(segments)


def _numbered_pieces(line: str) -> tuple[tuple[str, str], ...]:
    pieces = [piece.strip() for piece in _NUMBERED_SPLIT.split(line) if piece.strip()]
    result: list[tuple[str, str]] = []
    for piece in pieces:
        match = _NUMBERED.match(piece)
        if match is not None:
            result.append((match.group(1), match.group(2).strip()))
    return tuple(result)


def _assign_segment(
    section: _Section,
    entries: tuple[_Entry, ...],
    standards_by_lane: list[list[ParsedStandard]],
) -> None:
    lane_count = len(section.lanes)
    if lane_count == 1:
        for entry in entries:
            _append_unique(standards_by_lane[0], entry)
        return

    full_count = len(entries) - (len(entries) % lane_count)
    for index in range(full_count):
        lane_index = index % lane_count
        _append_unique(standards_by_lane[lane_index], entries[index])

    tail = entries[full_count:]
    if not tail:
        return
    if len(tail) == 1:
        for lane_index in range(lane_count):
            _append_unique(standards_by_lane[lane_index], tail[0])
        return

    for lane_index, entry in enumerate(tail[:-1]):
        _append_unique(standards_by_lane[lane_index], entry)
    shared = tail[-1]
    for lane_index in range(len(tail) - 1, lane_count):
        _append_unique(standards_by_lane[lane_index], shared)


def _courses_from_section(
    section: _Section,
    occurrences: dict[int, list[tuple[str, str]]],
) -> list[ParsedCourse]:
    standards_by_lane: list[list[ParsedStandard]] = [[] for _ in section.lanes]
    lane_count = len(section.lanes)
    for number in sorted(occurrences):
        items = occurrences[number]
        if not items:
            continue
        entries = tuple(
            _Entry(code=str(number), text=text, strand=strand)
            for text, strand in items
        )
        if lane_count == 1:
            for entry in entries:
                _append_unique(standards_by_lane[0], entry)
        elif len(entries) == lane_count:
            for lane_index, entry in enumerate(entries):
                _append_unique(standards_by_lane[lane_index], entry)
        elif len(entries) < lane_count:
            for lane_index, entry in enumerate(entries[:-1]):
                _append_unique(standards_by_lane[lane_index], entry)
            shared = entries[-1]
            for lane_index in range(len(entries) - 1, lane_count):
                _append_unique(standards_by_lane[lane_index], shared)
        else:
            for index, entry in enumerate(entries):
                _append_unique(standards_by_lane[index % lane_count], entry)

    courses: list[ParsedCourse] = []
    for (lane_name, grade_band), standards in zip(
        section.lanes,
        standards_by_lane,
        strict=True,
    ):
        courses.append(
            ParsedCourse(
                course_key=_course_key(
                    section.discipline,
                    section.section_name,
                    lane_name,
                ),
                display_name=_display_name(
                    section.discipline,
                    section.section_name,
                    lane_name,
                ),
                source_course_code=section.section_name,
                grade_band=grade_band,
                standards=tuple(standards),
            )
        )
    return courses


def _append_unique(target: list[ParsedStandard], entry: _Entry) -> None:
    same_code = sum(
        1
        for standard in target
        if standard.code == entry.code or standard.code.startswith(f"{entry.code}.")
    )
    code = entry.code if same_code == 0 else f"{entry.code}.{same_code + 1}"
    target.append(ParsedStandard(code=code, text=entry.text, strand=entry.strand))


def _display_name(discipline: str, section_name: str, lane_name: str) -> str:
    discipline_name = discipline.title()
    if lane_name == section_name:
        return f"{discipline_name} {section_name}"
    return f"{discipline_name} {section_name} — {lane_name}"


def _course_key(discipline: str, section_name: str, lane_name: str) -> str:
    value = f"{discipline}_{section_name}_{lane_name}".lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def _is_noise(line: str, section: _Section) -> bool:
    if line.startswith("2024 Alabama Course of Study: Arts Education"):
        return True
    if line in {
        "Content Standards",
        section.discipline,
        section.section_name,
        "Please refer to “Directions for Interpreting Standards” on page 14.",
        "Each content standard completes the stem “Students will…”",
    }:
        return True
    if re.fullmatch(r"\d+", line):
        return True
    return bool(line.isupper() and len(line) <= 80)
