from hashlib import sha256

import pytest

from app.standards_alabama_generic_academic import parse_alabama_generic_academic
from app.standards_ingest import ExtractedDocument, StandardsIngestError


def _document(lines: list[str]) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_generic_academic_parser_requires_explicit_content_standard_sections() -> None:
    with pytest.raises(StandardsIngestError, match="no explicit content-standards sections"):
        parse_alabama_generic_academic(
            "synthetic_academic",
            _document(["Course Overview", "1. A numbered sentence outside a course section."]),
        )


def test_generic_academic_parser_extracts_multiple_explicit_course_sections() -> None:
    parsed = parse_alabama_generic_academic(
        "synthetic_academic",
        _document(
            [
                "GRADE 5 CONTENT STANDARDS",
                "Domain Heading",
                "1. Analyze an authoritative concept.",
                "2. Apply the concept in a discipline-specific context.",
                "a. Explain a required subcomponent.",
                "3. Communicate a conclusion using appropriate evidence.",
                "ADVANCED COURSE CONTENT STANDARDS",
                "1",
                "Evaluate an advanced course concept using source evidence.",
                "1a Compare two required representations of the concept.",
                "Examples: Illustrative text that is not part of the standard.",
                "2. Construct a discipline-specific product.",
                "3. Reflect on the quality of the product.",
            ]
        ),
    )

    assert len(parsed.courses) == 2
    grade_five = parsed.courses[0]
    assert grade_five.display_name == "Grade 5"
    assert grade_five.grade_band == "5"
    assert grade_five.standards[0].code == "1"
    assert grade_five.standards[2].code == "2a"
    assert grade_five.standards[2].parent_code == "2"

    advanced = parsed.courses[1]
    by_code = {standard.code: standard for standard in advanced.standards}
    assert by_code["1"].text == (
        "Evaluate an advanced course concept using source evidence."
    )
    assert by_code["1a"].parent_code == "1"
    assert "Illustrative text" not in by_code["1a"].text


def test_generic_academic_parser_rejects_ambiguous_duplicate_sections() -> None:
    with pytest.raises(StandardsIngestError, match="ambiguous duplicate section"):
        parse_alabama_generic_academic(
            "synthetic_academic",
            _document(
                [
                    "BIOLOGY CONTENT STANDARDS",
                    "1. Standard one.",
                    "2. Standard two.",
                    "3. Standard three.",
                    "BIOLOGY CONTENT STANDARDS",
                    "1. Different one.",
                    "2. Different two.",
                    "3. Different three.",
                ]
            ),
        )
