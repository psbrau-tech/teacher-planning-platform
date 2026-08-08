from __future__ import annotations

import re

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

CAREER_MATHEMATICS_PARSER_VERSION = "gate-e-alabama-career-mathematics-v1"
_MAIN = re.compile(r"^(\d+)\.\s+(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = ("Example:", "Examples:")
_STRANDS = {
    "MEASUREMENT": "Measurement",
    "ENTREPRENEURIAL ECONOMICS AND FINANCES": "Entrepreneurial Economics and Finances",
    "ALGEBRA": "Algebra",
    "GEOMETRY": "Geometry",
    "DATA ANALYSIS AND PROBABILITY": "Data Analysis and Probability",
}


def parse_alabama_career_mathematics(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
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

    for line in extracted.lines:
        strand = _STRANDS.get(line.upper())
        if strand is not None:
            flush()
            current_main = None
            current_strand = strand
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

    main_codes = [
        standard.code for standard in standards if standard.parent_code is None
    ]
    expected_codes = [str(number) for number in range(1, 15)]
    if main_codes != expected_codes:
        raise StandardsIngestError(
            "Alabama Career Mathematics parser expected main standards 1 through 14"
        )
    if len({standard.code for standard in standards}) != len(standards):
        raise StandardsIngestError(
            "Alabama Career Mathematics parser produced duplicate standards identifiers"
        )

    all_standards = tuple(standards)
    part_a = _standards_for_main_range(all_standards, 1, 6)
    part_b = _standards_for_main_range(all_standards, 7, 14)
    return ParsedStandardsDocument(
        parser_key="alabama_career_mathematics",
        parser_version=CAREER_MATHEMATICS_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=(
            ParsedCourse(
                course_key="career_mathematics",
                display_name="Career Mathematics",
                source_course_code=None,
                grade_band="9-12",
                standards=all_standards,
            ),
            ParsedCourse(
                course_key="career_mathematics_a",
                display_name="Career Mathematics A",
                source_course_code=None,
                grade_band="9-12",
                standards=part_a,
            ),
            ParsedCourse(
                course_key="career_mathematics_b",
                display_name="Career Mathematics B",
                source_course_code=None,
                grade_band="9-12",
                standards=part_b,
            ),
        ),
    )


def _standards_for_main_range(
    standards: tuple[ParsedStandard, ...],
    first: int,
    last: int,
) -> tuple[ParsedStandard, ...]:
    selected: list[ParsedStandard] = []
    for standard in standards:
        main_code = standard.parent_code or standard.code
        match = re.match(r"^(\d+)", main_code)
        if match is not None and first <= int(match.group(1)) <= last:
            selected.append(standard)
    return tuple(selected)


def _noise(line: str) -> bool:
    if line == "CAREER MATHEMATICS":
        return True
    if line == "Students will:":
        return True
    if line == "Career Mathematics":
        return True
    return bool(re.fullmatch(r"\d+Career Mathematics|\d+", line))
