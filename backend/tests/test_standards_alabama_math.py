from hashlib import sha256

import pytest

from app.standards_alabama_math import parse_alabama_math_2019
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
    "Grade 7 Accelerated",
    "Grade 8",
    "Grade 8 Accelerated",
    "Geometry with Data Analysis",
    "Algebra I with Probability",
    "Algebra II with Statistics",
    "Mathematical Modeling",
    "Applications of Finite Mathematics",
    "Precalculus",
)


def _document(*, omit: str | None = None) -> ExtractedDocument:
    lines: list[str] = [
        "STUDENT MATHEMATICAL PRACTICES",
        *[
            f"{number}. Mathematical practice {number} exact source wording."
            for number in range(1, 9)
        ],
        "Practice Notes",
    ]
    for course in COURSES:
        if course == omit:
            continue
        lines.extend(
            [
                f"{course} Content Standards",
                "Number and Quantity",
                "1. Solve a mathematical problem using an appropriate representation",
                "and explain the reasoning used.",
                "Example: Illustrative example that must not become standard text.",
                "2. Construct and justify a mathematical argument.",
                "a. Represent the relationship using an equation.",
                "Note: Teacher-facing note that is not part of the required wording.",
                "b. Compare the representation with another valid strategy.",
                "Modeling",
                "3. Analyze a mathematical model and communicate a conclusion.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_math_parser_returns_all_17_course_sections() -> None:
    parsed = parse_alabama_math_2019(_document())

    assert len(parsed.courses) == 17
    assert [course.display_name for course in parsed.courses] == list(COURSES)
    assert parsed.courses[0].course_key == "kindergarten"
    assert parsed.courses[8].course_key == "grade_7_accelerated"
    assert parsed.courses[11].course_key == "geometry_data_analysis"
    assert parsed.courses[-1].course_key == "precalculus"


def test_math_parser_attaches_all_eight_practices_to_each_course() -> None:
    parsed = parse_alabama_math_2019(_document())
    geometry = next(
        course for course in parsed.courses if course.course_key == "geometry_data_analysis"
    )
    practices = [
        standard
        for standard in geometry.standards
        if standard.strand == "Student Mathematical Practices"
    ]

    assert [practice.code for practice in practices] == [
        "SMP1",
        "SMP2",
        "SMP3",
        "SMP4",
        "SMP5",
        "SMP6",
        "SMP7",
        "SMP8",
    ]
    assert practices[0].text == "Mathematical practice 1 exact source wording."


def test_math_content_preserves_hierarchy_and_excludes_examples_and_notes() -> None:
    parsed = parse_alabama_math_2019(_document())
    algebra = next(
        course for course in parsed.courses if course.course_key == "algebra_i_probability"
    )
    content = {
        standard.code: standard
        for standard in algebra.standards
        if standard.strand == "Content Standards"
    }

    assert content["1"].text == (
        "Solve a mathematical problem using an appropriate representation "
        "and explain the reasoning used."
    )
    assert "Illustrative example" not in content["1"].text
    assert content["2a"].parent_code == "2"
    assert content["2b"].parent_code == "2"
    assert "Teacher-facing note" not in content["2a"].text
    assert "Modeling" not in content["2b"].text
    assert content["3"].parent_code is None


def test_math_parser_fails_closed_if_expected_course_section_is_missing() -> None:
    with pytest.raises(StandardsIngestError, match="every expected K-12 mathematics course"):
        parse_alabama_math_2019(_document(omit="Precalculus"))
