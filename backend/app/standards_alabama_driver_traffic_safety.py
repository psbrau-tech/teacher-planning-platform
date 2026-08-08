from __future__ import annotations

import re

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

DRIVER_TRAFFIC_SAFETY_PARSER_VERSION = "gate-e-alabama-driver-traffic-safety-2007-v3"
_MAIN = re.compile(r"^(\d+)\.\s+(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = ("Example:", "Examples:", "Note:", "Notes:")
_PHASE_HEADINGS = {
    "CLASSROOM PHASE": "Classroom Phase",
    "BEHIND-THE-WHEEL PHASE": "Behind-the-Wheel Phase",
    "BEHIND THE WHEEL PHASE": "Behind-the-Wheel Phase",
}
_COURSE_MARKER = "DRIVER AND TRAFFIC SAFETY EDUCATION COURSE"
_APPENDIX_MARKER = "Web Sites for Driver and Traffic Safety Education"
_EXPECTED_MAIN_COUNT = 21


def parse_alabama_driver_traffic_safety_2007(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    standards: list[ParsedStandard] = []
    current_main: str | None = None
    current_code: str | None = None
    current_parent: str | None = None
    current_strand = "Content Standards"
    current_parts: list[str] = []
    skipping_supplement = False
    in_course = False

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

    for line in extracted.lines:
        if not in_course:
            if line == _COURSE_MARKER:
                in_course = True
            continue

        if line == _APPENDIX_MARKER:
            flush()
            break

        phase = _PHASE_HEADINGS.get(line.upper())
        if phase is not None:
            flush()
            current_main = None
            current_strand = phase
            skipping_supplement = False
            continue

        main = _MAIN.match(line)
        if main is not None:
            next_main = int(main.group(1))
            if current_main is not None and next_main <= int(current_main):
                flush()
                break
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

    if not in_course:
        raise StandardsIngestError(
            "Alabama Driver and Traffic Safety parser did not find the authoritative course section"
        )

    flush()

    main_codes = [
        standard.code for standard in standards if standard.parent_code is None
    ]
    expected_codes = [str(number) for number in range(1, _EXPECTED_MAIN_COUNT + 1)]
    if main_codes != expected_codes:
        raise StandardsIngestError(
            "Alabama Driver and Traffic Safety parser expected main standards 1 through 21"
        )
    if len({standard.code for standard in standards}) != len(standards):
        raise StandardsIngestError(
            "Alabama Driver and Traffic Safety parser produced duplicate standards identifiers"
        )

    return ParsedStandardsDocument(
        parser_key="alabama_driver_traffic_safety_2007",
        parser_version=DRIVER_TRAFFIC_SAFETY_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=(
            ParsedCourse(
                course_key="driver_traffic_safety",
                display_name="Driver and Traffic Safety Education",
                source_course_code=None,
                grade_band=None,
                standards=tuple(standards),
            ),
        ),
    )


def _noise(line: str) -> bool:
    if line.startswith("2007 Alabama Course of Study"):
        return True
    if line in {"CONTENT STANDARDS", "Content Standards", "Students will:"}:
        return True
    return (
        len(line) <= 100
        and not re.search(r"[.!?;:]$", line)
        and (line.isupper() or line.istitle())
    )
