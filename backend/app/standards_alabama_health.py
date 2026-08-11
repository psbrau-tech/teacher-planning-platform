from __future__ import annotations

import re

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

HEALTH_PARSER_VERSION = "gate-e-alabama-health-2019-v3"
_MAIN = re.compile(
    r"^(K|[1-8]|HE|HA|WH)\s*[.-]?\s*(\d+)\s*\.\s*(\d+)([a-z])?\.?(?:\s+(.*))?$",
    flags=re.IGNORECASE,
)
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_EXAMPLE_PREFIXES = ("Example:", "Examples:")
_STANDARDS_START = "Grades K-5 Standards"
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
    "HE": ("health_education", "Health Education", "9-12"),
    "HA": ("leaders_health_advocacy", "Leaders in Health Advocacy", "10-12"),
    "WH": ("world_health", "World Health", "10-12"),
}


def parse_alabama_health_2019(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    grouped: dict[str, list[ParsedStandard]] = {prefix: [] for prefix in _COURSES}
    current_prefix: str | None = None
    current_code: str | None = None
    current_parts: list[str] = []
    current_parent: str | None = None
    skipping_example = False
    has_authoritative_start = any(
        re.sub(r"\s+", " ", line).strip() == _STANDARDS_START
        for line in extracted.lines
    )
    standards_started = not has_authoritative_start

    def flush() -> None:
        nonlocal current_prefix, current_code, current_parts, current_parent
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
        current_parts = []
        current_parent = None

    for raw_line in extracted.lines:
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line == _STANDARDS_START:
            standards_started = True
            continue
        if not standards_started:
            continue

        main = _MAIN.match(line)
        if main is not None:
            flush()
            prefix = main.group(1).upper()
            anchor = main.group(2)
            item = main.group(3)
            suffix = (main.group(4) or "").lower()
            base_code = _code(prefix, anchor, item)
            current_prefix = prefix
            current_code = f"{base_code}{suffix}"
            current_parent = base_code if suffix else None
            text = (main.group(5) or "").strip()
            current_parts = [text] if text else []
            skipping_example = False
            continue

        child = _CHILD.match(line)
        if child is not None and current_prefix is not None and current_code is not None:
            parent_code = current_code
            flush()
            current_prefix = parent_code.split(".", 1)[0]
            current_parent = parent_code
            current_code = f"{parent_code}{child.group(1)}"
            current_parts = [child.group(2)]
            skipping_example = False
            continue

        if any(line.startswith(prefix) for prefix in _EXAMPLE_PREFIXES):
            skipping_example = True
            continue
        if skipping_example or current_code is None or _noise(line):
            continue
        current_parts.append(line)

    flush()

    courses: list[ParsedCourse] = []
    for prefix, (course_key, display_name, grade_band) in _COURSES.items():
        standards = tuple(grouped[prefix])
        if len(standards) < 2:
            raise StandardsIngestError(
                f"Alabama Health {display_name} standards structure changed unexpectedly"
            )
        codes = [standard.code for standard in standards]
        if len(codes) != len(set(codes)):
            raise StandardsIngestError(
                f"Alabama Health {display_name} produced duplicate standards identifiers"
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
        parser_key="alabama_health_2019",
        parser_version=HEALTH_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _code(prefix: str, anchor: str, item: str) -> str:
    return f"{prefix}.{anchor}.{item}"


def _noise(line: str) -> bool:
    if line.startswith("Alabama Course of Study: Health Education"):
        return True
    if line.startswith("Anchor Standard"):
        return True
    if line in {
        "Students can:",
        "Each content standard completes the sentence stem Students can…",
    }:
        return True
    return bool(re.fullmatch(r"\d+", line))
