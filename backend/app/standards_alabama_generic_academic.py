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

GENERIC_ACADEMIC_PARSER_VERSION = "gate-e-alabama-academic-generic-v1"
_EXPLICIT_MARKER = re.compile(r"^(?P<title>.+?)\s+CONTENT STANDARDS$", re.IGNORECASE)
_MAIN = re.compile(r"^(\d+)\.\s+(.+)$")
_DETACHED_MAIN = re.compile(r"^(\d+)$")
_CHILD = re.compile(r"^(?:([a-z])\.|(\d+)([a-z])(?:\.|\s))\s*(.+)$")
_SUPPLEMENT_PREFIXES = (
    "Example:",
    "Examples:",
    "Clarification:",
    "Clarifications:",
    "Note:",
    "Notes:",
    "Suggested Activities:",
)


@dataclass(frozen=True, slots=True)
class _Section:
    display_name: str
    marker_index: int
    end_index: int
    standards: tuple[ParsedStandard, ...]


def parse_alabama_generic_academic(
    parser_key: str,
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    candidates = _candidate_markers(extracted.lines)
    if not candidates:
        raise StandardsIngestError(
            "Generic Alabama academic parser found no explicit content-standards sections"
        )

    sections: list[_Section] = []
    for marker_index, display_name in candidates:
        end_index = _next_marker_index(candidates, marker_index, len(extracted.lines))
        standards = _parse_numbered_standards(extracted.lines[marker_index + 1 : end_index])
        if len(standards) >= 3:
            sections.append(
                _Section(
                    display_name=display_name,
                    marker_index=marker_index,
                    end_index=end_index,
                    standards=standards,
                )
            )

    selected = _deduplicate_sections(sections)
    if not selected:
        raise StandardsIngestError(
            "Generic Alabama academic parser found no complete standards sections"
        )

    courses = tuple(
        ParsedCourse(
            course_key=_slug(section.display_name),
            display_name=_display_name(section.display_name),
            source_course_code=f"{section.display_name} Content Standards",
            grade_band=_grade_band(section.display_name),
            standards=section.standards,
        )
        for section in sorted(selected, key=lambda item: item.marker_index)
    )
    if len({course.course_key for course in courses}) != len(courses):
        raise StandardsIngestError(
            "Generic Alabama academic parser produced duplicate course identifiers"
        )

    return ParsedStandardsDocument(
        parser_key=parser_key,
        parser_version=GENERIC_ACADEMIC_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=courses,
    )


def _candidate_markers(lines: tuple[str, ...]) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _EXPLICIT_MARKER.match(line)
        if match is None:
            continue
        title = _clean_title(match.group("title"))
        if not title or title in {"FOUNDATIONAL", "RECURRING"}:
            continue
        if not _has_numbered_standard(lines, index + 1, min(len(lines), index + 100)):
            continue
        markers.append((index, title))
    return markers


def _has_numbered_standard(lines: tuple[str, ...], start: int, end: int) -> bool:
    return any(
        _MAIN.match(line) is not None or line == "1"
        for line in lines[start:end]
    )


def _next_marker_index(
    candidates: list[tuple[int, str]],
    current_index: int,
    default: int,
) -> int:
    later = [index for index, _ in candidates if index > current_index]
    return min(later) if later else default


def _deduplicate_sections(sections: list[_Section]) -> tuple[_Section, ...]:
    by_key: dict[str, _Section] = {}
    for section in sections:
        key = _slug(section.display_name)
        existing = by_key.get(key)
        if existing is None or len(section.standards) > len(existing.standards):
            by_key[key] = section
        elif len(section.standards) == len(existing.standards):
            raise StandardsIngestError(
                f"Generic Alabama academic parser found ambiguous duplicate section: "
                f"{section.display_name}"
            )
    return tuple(by_key.values())


def _parse_numbered_standards(lines: tuple[str, ...]) -> tuple[ParsedStandard, ...]:
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
        main = _MAIN.match(line)
        if main:
            flush()
            current_main = main.group(1)
            current_code = current_main
            current_parent = None
            current_parts = [main.group(2)]
            skipping_supplement = False
            continue

        detached = _DETACHED_MAIN.match(line)
        if detached:
            flush()
            current_main = detached.group(1)
            current_code = current_main
            current_parent = None
            current_parts = []
            skipping_supplement = False
            continue

        child = _CHILD.match(line)
        if child and current_main is not None:
            if child.group(1) is not None:
                child_letter = child.group(1)
                child_parent = current_main
                child_text = child.group(4)
            elif child.group(2) == current_main and child.group(3) is not None:
                child_letter = child.group(3)
                child_parent = current_main
                child_text = child.group(4)
            else:
                child_letter = None
                child_parent = None
                child_text = ""
            if child_letter is not None and child_parent is not None:
                flush()
                current_code = f"{child_parent}{child_letter}"
                current_parent = child_parent
                current_parts = [child_text]
                skipping_supplement = False
                continue

        if any(line.startswith(prefix) for prefix in _SUPPLEMENT_PREFIXES):
            skipping_supplement = True
            continue
        if skipping_supplement:
            continue
        if current_code is None or _is_heading_noise(line):
            continue
        current_parts.append(line)

    flush()
    return tuple(standards)


def _is_heading_noise(line: str) -> bool:
    if "Alabama Course of Study" in line:
        return True
    if line.upper().endswith("CONTENT STANDARDS"):
        return True
    if len(line) <= 90 and not re.search(r"[.!?;:]$", line):
        if line.isupper() or line.istitle():
            return True
    return False


def _clean_title(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" :-")
    cleaned = re.sub(r"^(GRADE\s+\d+\s*[-—:]\s*)", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _display_name(value: str) -> str:
    if re.fullmatch(r"GRADE\s+\d+", value, flags=re.IGNORECASE):
        return value.title()
    return value.title() if value.isupper() else value


def _grade_band(value: str) -> str | None:
    grade = re.fullmatch(r"GRADE\s+(\d+)", value, flags=re.IGNORECASE)
    if grade:
        return grade.group(1)
    if value.upper() == "KINDERGARTEN":
        return "K"
    return None


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "course"
