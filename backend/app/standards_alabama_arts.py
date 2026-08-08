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

ARTS_PARSER_VERSION = "gate-e-alabama-arts-2024-v1"
_MAIN = re.compile(r"^(1[01]|[1-9])\.\s+(.+)$")
_CONTEXT_PREFIXES = (
    "Anchor Standard",
    "Process Component:",
    "Enduring Understanding:",
    "Essential Question:",
    "Essential Questions:",
    "Example:",
    "Examples:",
)
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
_STRAND_BY_NUMBER = {
    1: "Creating",
    2: "Creating",
    3: "Creating",
    4: "Performing / Presenting / Producing",
    5: "Performing / Presenting / Producing",
    6: "Performing / Presenting / Producing",
    7: "Responding",
    8: "Responding",
    9: "Responding",
    10: "Connecting",
    11: "Connecting",
}


@dataclass(frozen=True, slots=True)
class _Lane:
    course_key: str
    display_name: str
    grade_band: str | None


@dataclass(frozen=True, slots=True)
class _SectionSpec:
    discipline: str
    section_name: str
    lanes: tuple[_Lane, ...]
    shared_lanes: tuple[tuple[int, tuple[tuple[int, ...], ...]], ...] = ()
    duplicate_numbers: tuple[int, ...] = ()

    def shared_for(self, number: int) -> tuple[tuple[int, ...], ...] | None:
        return dict(self.shared_lanes).get(number)


def _lane(key: str, name: str, grade_band: str | None) -> _Lane:
    return _Lane(course_key=key, display_name=name, grade_band=grade_band)


def _three_grade_lanes(prefix: str, discipline: str, grades: tuple[int, int, int]) -> tuple[_Lane, ...]:
    return tuple(
        _lane(
            f"{prefix}_grade_{grade}",
            f"{discipline} Grade {grade}",
            str(grade),
        )
        for grade in grades
    )


def _level_lanes(
    prefix: str,
    display_prefix: str,
    count: int,
    grade_band: str,
) -> tuple[_Lane, ...]:
    roman = ("I", "II", "III", "IV")
    return tuple(
        _lane(
            f"{prefix}_level_{index + 1}",
            f"{display_prefix} Level {roman[index]}",
            grade_band,
        )
        for index in range(count)
    )


_K12_SHARED = (
    (0,),
    (1, 2),
)

_SECTION_SPECS = (
    _SectionSpec(
        "DANCE",
        "Kindergarten Grade 1 Grade 2",
        (
            _lane("dance_kindergarten", "Dance Kindergarten", "K"),
            _lane("dance_grade_1", "Dance Grade 1", "1"),
            _lane("dance_grade_2", "Dance Grade 2", "2"),
        ),
    ),
    _SectionSpec(
        "DANCE",
        "Grade 3 Grade 4 Grade 5",
        _three_grade_lanes("dance", "Dance", (3, 4, 5)),
    ),
    _SectionSpec(
        "DANCE",
        "Grades 6-8",
        _level_lanes("dance_middle", "Dance Grades 6-8", 3, "6-8"),
    ),
    _SectionSpec(
        "DANCE",
        "Grades 9-12",
        _level_lanes("dance_high", "Dance Grades 9-12", 2, "9-12"),
    ),
    _SectionSpec(
        "MEDIA ARTS",
        "Kindergarten Grade 1 Grade 2",
        (
            _lane("media_arts_kindergarten", "Media Arts Kindergarten", "K"),
            _lane("media_arts_grade_1", "Media Arts Grade 1", "1"),
            _lane("media_arts_grade_2", "Media Arts Grade 2", "2"),
        ),
        shared_lanes=((11, _K12_SHARED),),
    ),
    _SectionSpec(
        "MEDIA ARTS",
        "Grade 3 Grade 4 Grade 5",
        _three_grade_lanes("media_arts", "Media Arts", (3, 4, 5)),
        shared_lanes=((11, _K12_SHARED),),
    ),
    _SectionSpec(
        "MEDIA ARTS",
        "Grades 6-8",
        _level_lanes("media_arts_middle", "Media Arts Grades 6-8", 3, "6-8"),
    ),
    _SectionSpec(
        "MEDIA ARTS",
        "Grades 9-12",
        _level_lanes("media_arts_high", "Media Arts Grades 9-12", 2, "9-12"),
    ),
    _SectionSpec(
        "MUSIC",
        "Kindergarten Grade 1 Grade 2",
        (
            _lane("music_kindergarten", "Music Kindergarten", "K"),
            _lane("music_grade_1", "Music Grade 1", "1"),
            _lane("music_grade_2", "Music Grade 2", "2"),
        ),
        shared_lanes=tuple((number, _K12_SHARED) for number in (1, 8, 10, 11)),
    ),
    _SectionSpec(
        "MUSIC",
        "Grades 3-5 General Music",
        (_lane("general_music_3_5", "General Music Grades 3-5", "3-5"),),
        duplicate_numbers=(7,),
    ),
    _SectionSpec(
        "MUSIC",
        "Grades 3-5 Music Technology",
        (_lane("music_technology_3_5", "Music Technology Grades 3-5", "3-5"),),
    ),
    _SectionSpec(
        "MUSIC",
        "Grade 6 General Music",
        (_lane("general_music_6", "General Music Grade 6", "6"),),
        duplicate_numbers=(7,),
    ),
    _SectionSpec(
        "MUSIC",
        "Grade 6 Music Technology",
        (_lane("music_technology_6", "Music Technology Grade 6", "6"),),
    ),
    _SectionSpec(
        "MUSIC",
        "Music Technology",
        _level_lanes("music_technology", "Music Technology", 4, "9-12"),
    ),
    _SectionSpec(
        "MUSIC",
        "Grades 6-8 Vocal and Instrumental Ensemble",
        (
            _lane(
                "vocal_instrumental_ensemble_6_8",
                "Vocal and Instrumental Ensemble Grades 6-8",
                "6-8",
            ),
        ),
        duplicate_numbers=(7,),
    ),
    _SectionSpec(
        "MUSIC",
        "Vocal and Instrumental Ensemble",
        _level_lanes(
            "vocal_instrumental_ensemble",
            "Vocal and Instrumental Ensemble",
            4,
            "9-12",
        ),
    ),
    _SectionSpec(
        "MUSIC",
        "Harmonizing Instruments",
        _level_lanes("harmonizing_instruments", "Harmonizing Instruments", 4, "9-12"),
    ),
    _SectionSpec(
        "THEATRE",
        "Kindergarten Grade 1 Grade 2",
        (
            _lane("theatre_kindergarten", "Theatre Kindergarten", "K"),
            _lane("theatre_grade_1", "Theatre Grade 1", "1"),
            _lane("theatre_grade_2", "Theatre Grade 2", "2"),
        ),
    ),
    _SectionSpec(
        "THEATRE",
        "Grade 3",
        (_lane("theatre_grade_3", "Theatre Grade 3", "3"),),
    ),
    _SectionSpec(
        "THEATRE",
        "Grade 4",
        (_lane("theatre_grade_4", "Theatre Grade 4", "4"),),
    ),
    _SectionSpec(
        "THEATRE",
        "Grade 5",
        (_lane("theatre_grade_5", "Theatre Grade 5", "5"),),
    ),
    _SectionSpec(
        "THEATRE",
        "Grades 6-8",
        _level_lanes("theatre_middle", "Theatre Grades 6-8", 3, "6-8"),
    ),
    _SectionSpec(
        "THEATRE",
        "Grades 9-12",
        _level_lanes("theatre_high", "Theatre Grades 9-12", 4, "9-12"),
    ),
    *tuple(
        _SectionSpec(
            "VISUAL ARTS",
            "Kindergarten" if grade == 0 else f"Grade {grade}",
            (
                _lane(
                    "visual_arts_kindergarten" if grade == 0 else f"visual_arts_grade_{grade}",
                    "Visual Arts Kindergarten" if grade == 0 else f"Visual Arts Grade {grade}",
                    "K" if grade == 0 else str(grade),
                ),
            ),
        )
        for grade in range(0, 6)
    ),
    _SectionSpec(
        "VISUAL ARTS",
        "Grades 6-8",
        _level_lanes("visual_arts_middle", "Visual Arts Grades 6-8", 3, "6-8"),
    ),
    _SectionSpec(
        "VISUAL ARTS",
        "Grades 9-12 Visual Communication",
        _level_lanes(
            "visual_communication",
            "Visual Communication Grades 9-12",
            3,
            "9-12",
        ),
    ),
    _SectionSpec(
        "VISUAL ARTS",
        "Grades 9-12 Visual Art Disciplines",
        _level_lanes(
            "visual_art_disciplines",
            "Visual Art Disciplines Grades 9-12",
            4,
            "9-12",
        ),
    ),
)


def parse_alabama_arts_2024(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    content_markers = tuple(
        index for index, line in enumerate(extracted.lines) if line == "Content Standards"
    )
    if len(content_markers) != len(_SECTION_SPECS):
        raise StandardsIngestError(
            "Alabama Arts parser expected exactly 33 authoritative Content Standards sections"
        )

    courses: list[ParsedCourse] = []
    for spec in _SECTION_SPECS:
        marker = _find_section_marker(extracted.lines, spec)
        end = min(
            (index for index in content_markers if index > marker),
            default=len(extracted.lines),
        )
        occurrences = _extract_occurrences(extracted.lines[marker + 1 : end])
        courses.extend(_courses_from_section(spec, occurrences))

    if len(courses) != 71:
        raise StandardsIngestError(
            "Alabama Arts parser expected exactly 71 teacher-facing course views"
        )
    if len({course.course_key for course in courses}) != len(courses):
        raise StandardsIngestError("Alabama Arts parser produced duplicate course identifiers")

    return ParsedStandardsDocument(
        parser_key="alabama_arts_2024",
        parser_version=ARTS_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _find_section_marker(lines: tuple[str, ...], spec: _SectionSpec) -> int:
    matches = [
        index
        for index, line in enumerate(lines)
        if line == "Content Standards"
        and index >= 2
        and lines[index - 2] == spec.discipline
        and lines[index - 1] == spec.section_name
    ]
    if len(matches) != 1:
        raise StandardsIngestError(
            f"Alabama Arts parser could not uniquely locate {spec.discipline} "
            f"{spec.section_name}"
        )
    return matches[0]


def _extract_occurrences(
    lines: tuple[str, ...],
) -> dict[int, list[tuple[str, str]]]:
    occurrences = {number: [] for number in range(1, 12)}
    current_number: int | None = None
    current_parts: list[str] = []
    skipping_context = False

    def flush() -> None:
        nonlocal current_number, current_parts
        if current_number is not None:
            text = " ".join(current_parts).strip()
            if text:
                occurrences[current_number].append(
                    (text, _STRAND_BY_NUMBER[current_number])
                )
        current_number = None
        current_parts = []

    for line in lines:
        match = _MAIN.match(line)
        if match is not None:
            number = int(match.group(1))
            text = match.group(2).strip()
            if text == _ANCHOR_TEXT[number]:
                flush()
                skipping_context = True
                continue
            flush()
            current_number = number
            current_parts = [text]
            skipping_context = False
            continue

        if line.startswith(_CONTEXT_PREFIXES):
            skipping_context = True
            continue
        if skipping_context or current_number is None or _is_noise(line):
            continue
        current_parts.append(line)

    flush()
    return occurrences


def _courses_from_section(
    spec: _SectionSpec,
    occurrences: dict[int, list[tuple[str, str]]],
) -> list[ParsedCourse]:
    standards_by_lane: list[list[ParsedStandard]] = [[] for _ in spec.lanes]

    for number in range(1, 12):
        items = occurrences[number]
        shared = spec.shared_for(number)
        if len(spec.lanes) == 1:
            expected = 2 if number in spec.duplicate_numbers else 1
            if len(items) != expected:
                _raise_count_error(spec, number, expected, len(items))
            for item_index, (text, strand) in enumerate(items):
                code = str(number) if item_index == 0 else f"{number}.{item_index + 1}"
                standards_by_lane[0].append(
                    ParsedStandard(code=code, text=text, strand=strand)
                )
            continue

        lane_spans = shared or tuple((lane,) for lane in range(len(spec.lanes)))
        if len(items) != len(lane_spans):
            _raise_count_error(spec, number, len(lane_spans), len(items))
        for (text, strand), lanes in zip(items, lane_spans, strict=True):
            for lane in lanes:
                standards_by_lane[lane].append(
                    ParsedStandard(code=str(number), text=text, strand=strand)
                )

    courses: list[ParsedCourse] = []
    for lane, standards in zip(spec.lanes, standards_by_lane, strict=True):
        main_codes = [standard.code for standard in standards]
        if main_codes != [str(number) for number in range(1, 12)]:
            raise StandardsIngestError(
                f"Alabama Arts {lane.display_name} did not reconstruct standards 1 through 11"
            )
        courses.append(
            ParsedCourse(
                course_key=lane.course_key,
                display_name=lane.display_name,
                source_course_code=None,
                grade_band=lane.grade_band,
                standards=tuple(standards),
            )
        )
    return courses


def _raise_count_error(
    spec: _SectionSpec,
    number: int,
    expected: int,
    observed: int,
) -> None:
    raise StandardsIngestError(
        f"Alabama Arts {spec.discipline} {spec.section_name} standard {number} "
        f"expected {expected} source cells but found {observed}"
    )


def _is_noise(line: str) -> bool:
    if line.startswith("2024 Alabama Course of Study: Arts Education"):
        return True
    if line == "Content Standards":
        return True
    if re.fullmatch(r"\d+", line):
        return True
    return (
        len(line) <= 110
        and not re.search(r"[.!?;:]$", line)
        and (line.isupper() or line.istitle())
    )
