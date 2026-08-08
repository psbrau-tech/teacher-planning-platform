from hashlib import sha256

import pytest

from app.standards_alabama_career_mathematics import parse_alabama_career_mathematics
from app.standards_ingest import ExtractedDocument, StandardsIngestError

STRAND_BY_START = {
    1: "MEASUREMENT",
    3: "ENTREPRENEURIAL ECONOMICS AND FINANCES",
    7: "ALGEBRA",
    10: "GEOMETRY",
    13: "DATA ANALYSIS AND PROBABILITY",
}


def _document(*, omit: int | None = None) -> ExtractedDocument:
    lines: list[str] = ["Students will:"]
    for number in range(1, 15):
        if number == omit:
            continue
        heading = STRAND_BY_START.get(number)
        if heading is not None:
            lines.append(heading)
        lines.append(f"{number}. Required Career Mathematics standard {number}.")
        if number == 3:
            lines.extend(
                [
                    "a. Required supporting finance skill.",
                    "Examples: Supplemental example must not become authoritative wording.",
                    "Example continuation must also be excluded.",
                    "b. Required supporting economics skill.",
                ]
            )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_career_mathematics_parser_returns_combined_a_and_b_courses() -> None:
    parsed = parse_alabama_career_mathematics(_document())

    assert [course.course_key for course in parsed.courses] == [
        "career_mathematics",
        "career_mathematics_a",
        "career_mathematics_b",
    ]
    combined, part_a, part_b = parsed.courses
    assert [
        standard.code for standard in combined.standards if standard.parent_code is None
    ] == [str(number) for number in range(1, 15)]
    assert [
        standard.code for standard in part_a.standards if standard.parent_code is None
    ] == [str(number) for number in range(1, 7)]
    assert [
        standard.code for standard in part_b.standards if standard.parent_code is None
    ] == [str(number) for number in range(7, 15)]


def test_career_mathematics_parser_preserves_strands_children_and_excludes_examples() -> None:
    parsed = parse_alabama_career_mathematics(_document())
    combined = parsed.courses[0]
    by_code = {standard.code: standard for standard in combined.standards}

    assert by_code["1"].strand == "Measurement"
    assert by_code["3"].strand == "Entrepreneurial Economics and Finances"
    assert by_code["7"].strand == "Algebra"
    assert by_code["10"].strand == "Geometry"
    assert by_code["13"].strand == "Data Analysis and Probability"
    assert by_code["3a"].parent_code == "3"
    assert by_code["3a"].text == "Required supporting finance skill."
    assert "Supplemental example" not in by_code["3a"].text
    assert by_code["3b"].parent_code == "3"


def test_career_mathematics_parser_fails_closed_when_main_sequence_changes() -> None:
    with pytest.raises(StandardsIngestError, match="standards 1 through 14"):
        parse_alabama_career_mathematics(_document(omit=8))
