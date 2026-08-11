from __future__ import annotations

import re

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

ALGEBRA_FINANCE_PARSER_VERSION = "gate-e-alabama-algebra-finance-revised-v1"
_MAIN = re.compile(r"^(\d+)\.\s+(.+)$")
_CHILD = re.compile(r"^([a-z])\.\s+(.+)$")
_SUPPLEMENT_PREFIXES = ("Example:", "Examples:")
_STRANDS = {
    "Banking Services",
    "Investing",
    "Employment and Income Taxes",
    "Automobile Ownership and Operation",
    "Mathematical Operations",
    "Consumer Credit",
    "Independent Living",
    "Retirement Planning and Budgeting",
}


def parse_alabama_algebra_finance(extracted: ExtractedDocument) -> ParsedStandardsDocument:
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
        if line in _STRANDS:
            flush()
            current_main = None
            current_strand = line
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
    expected_codes = [str(number) for number in range(1, 20)]
    if main_codes != expected_codes:
        raise StandardsIngestError(
            "Alabama Algebra with Finance parser expected main standards 1 through 19"
        )
    if len({standard.code for standard in standards}) != len(standards):
        raise StandardsIngestError(
            "Alabama Algebra with Finance parser produced duplicate standards identifiers"
        )

    return ParsedStandardsDocument(
        parser_key="alabama_algebra_finance_revised",
        parser_version=ALGEBRA_FINANCE_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=(
            ParsedCourse(
                course_key="algebra_with_finance",
                display_name="Algebra with Finance",
                source_course_code="210036",
                grade_band="9-12",
                standards=tuple(standards),
            ),
        ),
    )


def _noise(line: str) -> bool:
    if line.startswith("Algebra with Finance –"):
        return True
    if line == "Alabama Course of Study: Algebra with Finance":
        return True
    if line == "Students will:":
        return True
    return bool(re.fullmatch(r"\d+", line))
