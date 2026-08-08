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

WORLD_LANGUAGES_PARSER_VERSION = "gate-e-alabama-world-languages-2017-v2"
_MAIN = re.compile(r"^(\d+)\.\s+(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = ("Example:", "Examples:")
_APPENDIX_MARKER = "Appendix A"
_PROFICIENCY_RANGES = (
    ("novice_low", "Novice Low Proficiency Range"),
    ("novice_mid", "Novice Mid Proficiency Range"),
    ("novice_high", "Novice High Proficiency Range"),
    ("intermediate_low", "Intermediate Low Proficiency Range"),
    ("intermediate_mid", "Intermediate Mid Proficiency Range"),
    ("intermediate_high", "Intermediate High Proficiency Range"),
)
_LEVELS_WORLD = (
    ("level_i", "Level I"),
    ("level_ii", "Level II"),
    ("level_iii", "Level III"),
    ("level_iv", "Level IV"),
    ("level_v", "Level V"),
)
_LEVELS_FOUR = _LEVELS_WORLD[:4]
_GOAL_HEADINGS = {
    "COMMUNICATION": "Communication",
    "CULTURES": "Cultures",
    "CULTURE": "Cultures",
    "CONNECTIONS": "Connections",
    "COMPARISONS": "Comparisons",
    "COMMUNITIES": "Communities",
}


@dataclass(frozen=True, slots=True)
class _SectionSpec:
    course_key: str
    display_name: str
    program: str
    heading: str
    grade_band: str
    requires_k8: bool = False


@dataclass(frozen=True, slots=True)
class _Section:
    spec: _SectionSpec
    marker_index: int


def parse_alabama_world_languages_2017(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    sections = _locate_sections(extracted.lines)
    specs = _specs()
    if len(sections) != len(specs):
        missing = sorted(
            spec.display_name
            for spec in specs
            if spec.course_key not in {section.spec.course_key for section in sections}
        )
        raise StandardsIngestError(
            "Alabama World Languages parser did not find every expected standards section: "
            + ", ".join(missing)
        )

    appendix_index = _unique_index_after(
        extracted.lines,
        _APPENDIX_MARKER,
        sections[-1].marker_index,
    )
    if appendix_index is None:
        raise StandardsIngestError(
            "Alabama World Languages parser did not find the authoritative Appendix A boundary"
        )

    courses: list[ParsedCourse] = []
    for index, section in enumerate(sections):
        end = (
            sections[index + 1].marker_index
            if index + 1 < len(sections)
            else appendix_index
        )
        standards = _parse_section(
            extracted.lines[section.marker_index + 1 : end]
        )
        _validate_section_sequence(section.spec.display_name, standards)
        courses.append(
            ParsedCourse(
                course_key=section.spec.course_key,
                display_name=section.spec.display_name,
                source_course_code=None,
                grade_band=section.spec.grade_band,
                standards=standards,
            )
        )

    return ParsedStandardsDocument(
        parser_key="alabama_world_languages_2017",
        parser_version=WORLD_LANGUAGES_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _specs() -> tuple[_SectionSpec, ...]:
    specs: list[_SectionSpec] = []
    for key, heading in _PROFICIENCY_RANGES:
        specs.append(
            _SectionSpec(
                course_key=f"world_languages_k8_{key}",
                display_name=f"World Languages K-8 — {heading}",
                program="world_languages",
                heading=heading,
                grade_band="K-8",
                requires_k8=True,
            )
        )
    for key, heading in _LEVELS_WORLD:
        specs.append(
            _SectionSpec(
                course_key=f"world_languages_{key}",
                display_name=f"World Languages {heading}",
                program="world_languages",
                heading=heading,
                grade_band="7-12",
            )
        )
    for key, heading in _LEVELS_FOUR:
        specs.append(
            _SectionSpec(
                course_key=f"latin_{key}",
                display_name=f"Latin {heading}",
                program="latin",
                heading=heading,
                grade_band="7-12",
            )
        )
    for key, heading in _PROFICIENCY_RANGES:
        specs.append(
            _SectionSpec(
                course_key=f"asl_k8_{key}",
                display_name=f"American Sign Language K-8 — {heading}",
                program="asl",
                heading=heading,
                grade_band="K-8",
                requires_k8=True,
            )
        )
    for key, heading in _LEVELS_FOUR:
        specs.append(
            _SectionSpec(
                course_key=f"asl_{key}",
                display_name=f"American Sign Language {heading}",
                program="asl",
                heading=heading,
                grade_band="7-12",
            )
        )
    return tuple(specs)


def _locate_sections(lines: tuple[str, ...]) -> tuple[_Section, ...]:
    found: list[_Section] = []
    used_indexes: set[int] = set()
    for spec in _specs():
        candidates = [
            index
            for index, line in enumerate(lines)
            if index not in used_indexes
            and _normalized(line) == _normalized(spec.heading)
            and _matches_context(lines, index, spec)
        ]
        if len(candidates) != 1:
            continue
        marker_index = candidates[0]
        used_indexes.add(marker_index)
        found.append(_Section(spec=spec, marker_index=marker_index))
    return tuple(sorted(found, key=lambda item: item.marker_index))


def _matches_context(
    lines: tuple[str, ...],
    marker_index: int,
    spec: _SectionSpec,
) -> bool:
    start = max(0, marker_index - 5)
    nearby = [_normalized(line) for line in lines[start:marker_index]]
    if spec.program == "latin":
        return "latin" in nearby
    if spec.program == "asl":
        if "american sign language" not in nearby:
            return False
    elif spec.program == "world_languages":
        if "world languages" not in nearby:
            return False
        if "american sign language" in nearby:
            return False
    if spec.requires_k8:
        return any(value in {"grades k-8", "grades k–8"} for value in nearby)
    return not any(value in {"grades k-8", "grades k–8"} for value in nearby)


def _parse_section(lines: tuple[str, ...]) -> tuple[ParsedStandard, ...]:
    standards: list[ParsedStandard] = []
    current_main: str | None = None
    current_code: str | None = None
    current_parent: str | None = None
    current_strand = "Content Standards"
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
                        strand=current_strand,
                    )
                )
        current_code = None
        current_parent = None
        current_parts = []

    for line in lines:
        goal = _GOAL_HEADINGS.get(line.upper())
        if goal is not None:
            flush()
            current_main = None
            current_strand = goal
            skipping_supplement = False
            continue

        main = _MAIN.match(line)
        if main is not None:
            flush()
            current_main = main.group(1)
            current_code = current_main
            current_parent = None
            current_parts = [main.group(2)]
            skipping_supplement = False
            continue

        child = _CHILD.match(line)
        if child is not None and current_main is not None:
            flush()
            current_code = f"{current_main}{child.group(1)}"
            current_parent = current_main
            current_parts = [child.group(2)]
            skipping_supplement = False
            continue

        if any(line.startswith(prefix) for prefix in _SUPPLEMENT_PREFIXES):
            skipping_supplement = True
            continue
        if skipping_supplement or current_code is None or _noise(line):
            continue
        current_parts.append(line)

    flush()
    return tuple(standards)


def _validate_section_sequence(
    display_name: str,
    standards: tuple[ParsedStandard, ...],
) -> None:
    main_codes = [
        int(standard.code)
        for standard in standards
        if standard.parent_code is None and standard.code.isdigit()
    ]
    if len(main_codes) < 8 or main_codes != list(range(1, len(main_codes) + 1)):
        raise StandardsIngestError(
            f"Alabama World Languages {display_name} has an invalid main-standard sequence"
        )
    codes = [standard.code for standard in standards]
    if len(codes) != len(set(codes)):
        raise StandardsIngestError(
            f"Alabama World Languages {display_name} produced duplicate standards identifiers"
        )


def _unique_index_after(
    lines: tuple[str, ...],
    marker: str,
    after: int,
) -> int | None:
    positions = [
        index
        for index, line in enumerate(lines)
        if index > after and _normalized(line) == _normalized(marker)
    ]
    return positions[0] if len(positions) == 1 else None


def _noise(line: str) -> bool:
    normalized = _normalized(line)
    if normalized.startswith("alabama course of study: world languages"):
        return True
    if normalized in {
        "students can:",
        "interpersonal mode",
        "interpretive mode",
        "presentational mode",
    }:
        return True
    return bool(re.fullmatch(r"\d+", normalized))


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()
