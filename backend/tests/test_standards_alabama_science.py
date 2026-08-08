from hashlib import sha256

import pytest

from app.standards_alabama_science import parse_alabama_science_2023
from app.standards_ingest import ExtractedDocument, StandardsIngestError


COURSES = (
    "Kindergarten",
    "Grade 1",
    "Grade 2",
    "Grade 3",
    "Grade 4",
    "Grade 5",
    "Grade 6",
    "Grade 7",
    "Grade 8",
    "Biology",
    "Chemistry",
    "Earth and Space Science",
    "Environmental Science",
    "Human Anatomy and Physiology",
    "Physical Science",
    "Physics",
)


def _document(*, omit: str | None = None) -> ExtractedDocument:
    lines: list[str] = []
    for course in COURSES:
        if course == omit:
            continue
        lines.extend(
            [
                course,
                f"Introductory description for {course}.",
                "Each content standard completes the stem “Students will…”",
                "Topic Heading",
                "1. Plan and carry out an investigation to answer a scientific question",
                "using evidence from observations.",
                "Examples: This illustrative example is not authoritative standard text.",
                "Structure",
                "and Function",
                "2. Obtain and evaluate information to explain a scientific phenomenon.",
                "a. Use a model to describe the first required component.",
                "Clarification: This explanatory note must not enter the standard text.",
                "b. Construct an explanation for the second required component.",
                "Cause",
                "and Effect",
                "3. Communicate evidence to support a scientific claim.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_science_parser_returns_k8_and_all_named_high_school_courses() -> None:
    parsed = parse_alabama_science_2023(_document())

    assert len(parsed.courses) == 16
    assert [course.display_name for course in parsed.courses] == list(COURSES)
    assert parsed.courses[0].grade_band == "K"
    assert parsed.courses[8].grade_band == "8"
    assert parsed.courses[9].course_key == "biology"
    assert parsed.courses[-1].course_key == "physics"
    assert parsed.courses[-1].grade_band == "9-12"


def test_science_parser_preserves_required_children_and_excludes_supplemental_text() -> None:
    parsed = parse_alabama_science_2023(_document())
    biology = next(course for course in parsed.courses if course.course_key == "biology")
    by_code = {standard.code: standard for standard in biology.standards}

    assert by_code["1"].text == (
        "Plan and carry out an investigation to answer a scientific question "
        "using evidence from observations."
    )
    assert "illustrative example" not in by_code["1"].text
    assert "Structure" not in by_code["1"].text
    assert by_code["2a"].parent_code == "2"
    assert by_code["2a"].text == "Use a model to describe the first required component."
    assert by_code["2b"].parent_code == "2"
    assert "explanatory note" not in by_code["2a"].text
    assert "Cause" not in by_code["2b"].text
    assert by_code["3"].parent_code is None
    assert all(standard.strand == "Content Standards" for standard in biology.standards)


def test_science_parser_fails_closed_if_expected_course_section_disappears() -> None:
    with pytest.raises(StandardsIngestError, match="every expected K-12 grade"):
        parse_alabama_science_2023(_document(omit="Chemistry"))
