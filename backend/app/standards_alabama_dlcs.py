from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

DLCS_PARSER_VERSION = "gate-e-alabama-dlcs-2025-v4"
_MAIN_TOKEN = re.compile(r"(?<![A-Za-z0-9])([1-9]\d?)\.\s+")
_DEVELOPMENTAL = re.compile(
    r"developmentally appropriate beginning in Grade\s+(\d+)",
    flags=re.IGNORECASE,
)
_THEMES = {
    "Computational Thinking",
    "Data Science",
    "Computing Systems",
    "Impact of Computing",
    "Digital Proficiency",
}
_FOOTER_SUFFIXES = (
    "Kindergarten - Grade 2",
    "Grades 3 - 5",
    "Grades 6 - 8",
    "Grades 9 - 12",
)


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


@dataclass(frozen=True, slots=True)
class _Band:
    header: str
    course_keys: tuple[str, ...]
    display_names: tuple[str, ...]
    grade_bands: tuple[str, ...]
    expected_final: tuple[int, ...]


@dataclass(slots=True)
class _Event:
    number: int
    minimum_lane: int
    theme: str
    row_id: int
    parts: list[str] = field(default_factory=list)


_BANDS = (
    _Band(
        "Kindergarten Grade 1 Grade 2",
        ("kindergarten", "grade_1", "grade_2"),
        ("Kindergarten", "Grade 1", "Grade 2"),
        ("K", "1", "2"),
        (15, 17, 20),
    ),
    _Band(
        "Grade 3 Grade 4 Grade 5",
        ("grade_3", "grade_4", "grade_5"),
        ("Grade 3", "Grade 4", "Grade 5"),
        ("3", "4", "5"),
        (19, 26, 24),
    ),
    _Band(
        "Grade 6 Grade 7 Grade 8",
        ("grade_6", "grade_7", "grade_8"),
        ("Grade 6", "Grade 7", "Grade 8"),
        ("6", "7", "8"),
        (31, 32, 36),
    ),
    _Band(
        "Grades 9-12",
        ("grades_9_12",),
        ("Grades 9-12",),
        ("9-12",),
        (45,),
    ),
)
_BAND_BY_HEADER = {_normalized(band.header): band for band in _BANDS}


def parse_alabama_dlcs_2025(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    events_by_band: dict[str, list[_Event]] = {band.header: [] for band in _BANDS}
    active_band: _Band | None = None
    minimum_lane = 0
    current_theme = "Content Standards"
    current_event: _Event | None = None
    skipping_example = False

    for row_id, raw_line in enumerate(extracted.lines):
        line = _clean_line(raw_line)
        if not line:
            continue

        band = _BAND_BY_HEADER.get(_normalized(line))
        if band is not None:
            active_band = band
            minimum_lane = 0
            current_event = None
            skipping_example = False
            continue

        if line in _THEMES:
            current_theme = line
            minimum_lane = 0
            current_event = None
            skipping_example = False
            continue

        developmental = _DEVELOPMENTAL.search(line)
        if developmental is not None and active_band is not None:
            minimum_lane = _minimum_lane_for_grade(
                active_band,
                developmental.group(1),
            )
            line = line[developmental.end() :].lstrip(" .:-")
            if not line:
                current_event = None
                continue

        if line.startswith(("Example:", "Examples:")):
            skipping_example = True
            current_event = None
            continue

        tokens = list(_MAIN_TOKEN.finditer(line))
        if tokens and active_band is not None:
            prefix = line[: tokens[0].start()].strip()
            if prefix and not skipping_example and current_event is not None:
                current_event.parts.append(prefix)
            skipping_example = False

            for token_index, token in enumerate(tokens):
                if token_index > 0 and current_event is not None:
                    prior_end = tokens[token_index - 1].end()
                    prior_text = line[prior_end : token.start()].strip()
                    if prior_text:
                        current_event.parts.append(prior_text)

                current_event = _Event(
                    number=int(token.group(1)),
                    minimum_lane=minimum_lane,
                    theme=current_theme,
                    row_id=row_id,
                )
                events_by_band[active_band.header].append(current_event)

            tail = line[tokens[-1].end() :].strip()
            if tail and current_event is not None:
                current_event.parts.append(tail)
            continue

        if skipping_example or current_event is None or _noise(line):
            continue
        current_event.parts.append(line)

    standards_by_course: dict[str, list[ParsedStandard]] = {
        course_key: [] for band in _BANDS for course_key in band.course_keys
    }
    for band in _BANDS:
        events = events_by_band[band.header]
        lanes = _solve_band_lanes(band, events)
        for event, lane in zip(events, lanes, strict=True):
            text = " ".join(event.parts).strip()
            if not text:
                raise StandardsIngestError(
                    f"Alabama DLCS {band.display_names[lane]} standard "
                    f"{event.number} has no authoritative text"
                )
            standards_by_course[band.course_keys[lane]].append(
                ParsedStandard(
                    code=str(event.number),
                    text=text,
                    parent_code=None,
                    strand=event.theme,
                )
            )

    courses: list[ParsedCourse] = []
    for band in _BANDS:
        for lane, course_key in enumerate(band.course_keys):
            standards = tuple(standards_by_course[course_key])
            expected_final = band.expected_final[lane]
            codes = [int(standard.code) for standard in standards]
            if codes != list(range(1, expected_final + 1)):
                raise StandardsIngestError(
                    f"Alabama DLCS {band.display_names[lane]} expected "
                    f"standards 1 through {expected_final}"
                )
            courses.append(
                ParsedCourse(
                    course_key=course_key,
                    display_name=band.display_names[lane],
                    source_course_code=None,
                    grade_band=band.grade_bands[lane],
                    standards=standards,
                )
            )

    return ParsedStandardsDocument(
        parser_key="alabama_dlcs_2025",
        parser_version=DLCS_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _solve_band_lanes(band: _Band, events: list[_Event]) -> tuple[int, ...]:
    terminal = tuple(final + 1 for final in band.expected_final)

    @lru_cache(maxsize=None)
    def solve(
        index: int,
        state: tuple[int, ...],
        previous_lane: int,
    ) -> tuple[int, ...] | None:
        if index == len(events):
            return () if state == terminal else None

        event = events[index]
        same_row = index > 0 and events[index - 1].row_id == event.row_id
        lane_floor = max(event.minimum_lane, previous_lane + 1 if same_row else 0)

        for lane in range(lane_floor, len(band.course_keys)):
            if state[lane] != event.number:
                continue
            next_state = list(state)
            next_state[lane] += 1
            suffix = solve(index + 1, tuple(next_state), lane)
            if suffix is not None:
                return (lane, *suffix)
        return None

    assignment = solve(0, tuple(1 for _ in band.course_keys), -1)
    if assignment is None:
        raise StandardsIngestError(
            f"Alabama DLCS could not reconstruct complete grade lanes within {band.header}"
        )
    return assignment


def _minimum_lane_for_grade(band: _Band, grade: str) -> int:
    for lane, grade_band in enumerate(band.grade_bands):
        if grade_band == grade:
            return lane
    raise StandardsIngestError(
        f"Alabama DLCS developmental-grade notice {grade} does not match "
        f"{band.header}"
    )


def _clean_line(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    for suffix in _FOOTER_SUFFIXES:
        if cleaned.endswith(suffix) and cleaned != suffix:
            cleaned = cleaned[: -len(suffix)].rstrip()
    return cleaned


def _noise(line: str) -> bool:
    if line.startswith("2025 Alabama Course of Study: Digital Literacy and"):
        return True
    if line in {
        "Each content standard completes the stem, “Students will…”",
        'Each content standard completes the stem, "Students will…"',
    }:
        return True
    if line.isupper() and len(line) <= 100:
        return True
    return bool(re.fullmatch(r"Computer Science \d+", line))
