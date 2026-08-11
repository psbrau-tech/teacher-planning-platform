from __future__ import annotations

import re

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

PHYSICAL_EDUCATION_PARSER_VERSION = "gate-e-alabama-physical-education-2019-v3"
_MAIN = re.compile(
    r"^(K|[1-8]|BK|AK|SO|AC|SC|LS|VA)\s*-\s*(\d+)\s*\.\s*(\d+)([a-z])?\.?(?:\s+(.*))?$",
    flags=re.IGNORECASE,
)
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = (
    "Example:",
    "Examples:",
    "Accommodation:",
    "Accommodations:",
    "Accommodation Suggestions:",
    "Modification:",
    "Modifications:",
    "Modification Suggestions:",
    "Technology:",
    "Technology Suggestions:",
)
_LEVEL_EXAMPLE_START = "Example of Level 1 vs. Level 2"
_LEVEL_EXAMPLE_END = "Beginning Kinesiology"
_COURSES = {
    "K": ("kindergarten", "Kindergarten", "K"),
    "1": ("grade_1", "Grade 1", "1"),
    "2": ("grade_2", "Grade 2", "2"),
    "3": ("grade_3", "Grade 3", "3"),
    "4": ("grade_4", "Grade 4", "4"),
    "5": ("grade_5", "Grade 5", "5"),
    "6": ("grade_6", "Grade 6", "6"),
    "7": ("grade_7", "Grade 7", "7"),
    "8": ("grade_8", "Grade 8", "8"),
    "BK": ("beginning_kinesiology", "Beginning Kinesiology", "9-12"),
    "AK": ("advanced_kinesiology", "Advanced Kinesiology", "9-12"),
    "SO": ("sports_officiating", "Sports Officiating", "9-12"),
    "AC": (
        "adventure_cooperative_activities",
        "Adventure and Cooperative Activities",
        "9-12",
    ),
    "SC": ("strength_conditioning", "Strength and Conditioning", "9-12"),
    "LS": (
        "life_sports_individual_dual_team",
        "Life Sports: Individual, Dual, and Team",
        "9-12",
    ),
    "VA": ("varsity_athletics", "Varsity Athletics", "9-12"),
}


def parse_alabama_physical_education_2019(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    grouped: dict[str, list[ParsedStandard]] = {prefix: [] for prefix in _COURSES}
    current_prefix: str | None = None
    current_code: str | None = None
    current_parent: str | None = None
    current_parts: list[str] = []
    skipping_supplement = False
    skipping_level_example = False

    def flush() -> None:
        nonlocal current_prefix, current_code, current_parent, current_parts
        if current_prefix is not None and current_code is not None:
            text = " ".join(current_parts).strip()
            if text:
                grouped[current_prefix].append(
                    ParsedStandard(
                        code=current_code,
                        text=text,
                        parent_code=current_parent,
                        strand="Content Standards",
                    )
                )
        current_prefix = None
        current_code = None
        current_parent = None
        current_parts = []

    for raw_line in extracted.lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        if line.startswith(_LEVEL_EXAMPLE_START):
            flush()
            skipping_level_example = True
            continue
        if skipping_level_example:
            if line == _LEVEL_EXAMPLE_END:
                skipping_level_example = False
            else:
                continue

        main = _MAIN.match(line)
        if main is not None:
            flush()
            prefix = main.group(1).upper()
            anchor = main.group(2)
            item = main.group(3)
            suffix = (main.group(4) or "").lower()
            base_code = f"{prefix}-{anchor}.{item}"
            current_prefix = prefix
            current_code = f"{base_code}{suffix}"
            current_parent = base_code if suffix else None
            text = (main.group(5) or "").strip()
            current_parts = [text] if text else []
            skipping_supplement = False
            continue

        child = _CHILD.match(line)
        if child is not None and current_prefix is not None and current_code is not None:
            parent_code = current_code
            prefix = current_prefix
            flush()
            current_prefix = prefix
            current_code = f"{parent_code}{child.group(1)}"
            current_parent = parent_code
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

    courses: list[ParsedCourse] = []
    for prefix, (course_key, display_name, grade_band) in _COURSES.items():
        standards = tuple(grouped[prefix])
        if len(standards) < 2:
            raise StandardsIngestError(
                f"Alabama Physical Education {display_name} standards structure changed "
                "unexpectedly"
            )
        codes = [standard.code for standard in standards]
        if len(codes) != len(set(codes)):
            raise StandardsIngestError(
                f"Alabama Physical Education {display_name} produced duplicate standards "
                "identifiers"
            )
        courses.append(
            ParsedCourse(
                course_key=course_key,
                display_name=display_name,
                source_course_code=prefix,
                grade_band=grade_band,
                standards=standards,
            )
        )

    return ParsedStandardsDocument(
        parser_key="alabama_physical_education_2019",
        parser_version=PHYSICAL_EDUCATION_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _noise(line: str) -> bool:
    if line.startswith("2019 Alabama Course of Study: Physical Education"):
        return True
    if line in {
        "Content Standard",
        "Content Standards",
        "Level 1",
        "Level 2",
        "Students will:",
    }:
        return True
    return bool(re.fullmatch(r"\d+", line))
