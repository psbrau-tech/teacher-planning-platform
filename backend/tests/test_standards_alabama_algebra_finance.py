from hashlib import sha256

import pytest

from app.standards_alabama_algebra_finance import parse_alabama_algebra_finance
from app.standards_ingest import ExtractedDocument, StandardsIngestError

STRANDS = (
    "Banking Services",
    "Investing",
    "Employment and Income Taxes",
    "Automobile Ownership and Operation",
    "Mathematical Operations",
    "Consumer Credit",
    "Independent Living",
    "Retirement Planning and Budgeting",
)


def _document(*, omit: int | None = None) -> ExtractedDocument:
    lines: list[str] = ["Students will:"]
    for number in range(1, 20):
        if number == omit:
            continue
        if number in {1, 4, 5, 8, 9, 15, 16, 19}:
            lines.append(STRANDS[{1: 0, 4: 1, 5: 2, 8: 3, 9: 4, 15: 5, 16: 6, 19: 7}[number]])
        lines.append(f"{number}. Required Algebra with Finance standard {number}.")
        if number == 3:
            lines.extend(
                [
                    "a. Required supporting calculation.",
                    "Examples: Supplemental example must not become authoritative wording.",
                    "Example continuation must also be excluded.",
                    "b. Required supporting interpretation.",
                ]
            )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_algebra_finance_parser_returns_current_single_course_and_main_sequence() -> None:
    parsed = parse_alabama_algebra_finance(_document())

    assert len(parsed.courses) == 1
    course = parsed.courses[0]
    assert course.course_key == "algebra_with_finance"
    assert course.source_course_code == "210036"
    assert course.grade_band == "9-12"
    assert [
        standard.code for standard in course.standards if standard.parent_code is None
    ] == [str(number) for number in range(1, 20)]


def test_algebra_finance_parser_preserves_strands_children_and_excludes_examples() -> None:
    parsed = parse_alabama_algebra_finance(_document())
    by_code = {standard.code: standard for standard in parsed.courses[0].standards}

    assert by_code["1"].strand == "Banking Services"
    assert by_code["4"].strand == "Investing"
    assert by_code["3a"].parent_code == "3"
    assert by_code["3a"].text == "Required supporting calculation."
    assert "Supplemental example" not in by_code["3a"].text
    assert by_code["3b"].parent_code == "3"
    assert by_code["19"].strand == "Retirement Planning and Budgeting"


def test_algebra_finance_parser_fails_closed_when_main_sequence_changes() -> None:
    with pytest.raises(StandardsIngestError, match="standards 1 through 19"):
        parse_alabama_algebra_finance(_document(omit=11))
