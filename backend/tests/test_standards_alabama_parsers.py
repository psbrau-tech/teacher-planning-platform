from hashlib import sha256

from app.standards_ingest import ExtractedDocument
from app.standards_parser_dispatch import parse_governed_standards_document


def _extracted(lines: list[str]) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_ela_parser_returns_every_k12_grade_with_exact_printed_codes() -> None:
    lines: list[str] = []
    grade_specs = [("KINDERGARTEN", "KINDERGARTEN CONTENT STANDARDS")]
    grade_specs.extend(
        (f"GRADE {grade}", f"GRADE {grade} CONTENT STANDARDS")
        for grade in range(1, 13)
    )
    for grade_label, content_marker in grade_specs:
        lines.extend(
            [
                grade_label,
                "RECURRING STANDARDS FOR TEST GRADE BAND",
                "Students will:",
                *[f"R{number}. Recurring standard {number}." for number in range(1, 5)],
                content_marker,
                *[f"{number}. Content standard {number}." for number in range(1, 6)],
            ]
        )

    parsed = parse_governed_standards_document("alabama_ela_2021", _extracted(lines))

    assert len(parsed.courses) == 13
    assert parsed.courses[0].course_key == "kindergarten"
    assert parsed.courses[0].display_name == "Kindergarten"
    assert parsed.courses[-1].course_key == "grade_12"
    assert parsed.courses[-1].display_name == "Grade 12"
    grade_ten = next(course for course in parsed.courses if course.course_key == "grade_10")
    assert grade_ten.source_course_code == "GRADE 10 CONTENT STANDARDS"
    assert grade_ten.standards[0].code == "R1"
    assert grade_ten.standards[0].strand == "Recurring Standards"
    assert grade_ten.standards[4].code == "1"
    assert grade_ten.standards[4].strand == "Content Standards"
    assert all(not standard.code.startswith("ELA") for standard in grade_ten.standards)


def test_ela_parser_fails_closed_if_any_grade_content_section_is_missing() -> None:
    lines: list[str] = []
    for grade in range(0, 12):
        label = "KINDERGARTEN" if grade == 0 else f"GRADE {grade}"
        marker = (
            "KINDERGARTEN CONTENT STANDARDS"
            if grade == 0
            else f"GRADE {grade} CONTENT STANDARDS"
        )
        lines.extend(
            [
                label,
                "RECURRING STANDARDS FOR TEST GRADE BAND",
                *[f"R{number}. Recurring {number}." for number in range(1, 5)],
                marker,
                *[f"{number}. Content {number}." for number in range(1, 6)],
            ]
        )

    import pytest

    with pytest.raises(Exception, match="every K-12 grade"):
        parse_governed_standards_document("alabama_ela_2021", _extracted(lines))


def test_generic_cte_parser_preserves_foundational_and_content_strands() -> None:
    lines: list[str] = []
    for title in ("FINANCIAL SERVICES", "BANKING SERVICES", "INSURANCE SERVICES"):
        lines.extend(
            [
                title.title(),
                "Grade Levels 9-12",
                "FOUNDATIONAL STANDARDS",
                *[f"{number}. Shared foundation {number}." for number in range(1, 4)],
                title,
                "CONTENT STANDARDS",
                *[f"{number}. {title.title()} standard {number}." for number in range(1, 5)],
            ]
        )

    parsed = parse_governed_standards_document(
        "alabama_cte_cos_generic",
        _extracted(lines),
    )

    assert {course.course_key for course in parsed.courses} == {
        "financial_services",
        "banking_services",
        "insurance_services",
    }
    finance = next(
        course for course in parsed.courses if course.course_key == "financial_services"
    )
    assert finance.grade_band == "9-12"
    assert finance.standards[0].code == "1"
    assert finance.standards[0].strand == "Foundational Standards"
    assert finance.standards[3].code == "1"
    assert finance.standards[3].strand == "Content Standards"
