from hashlib import sha256

import pytest

from app.standards_alabama_social_studies import parse_alabama_social_studies_2024
from app.standards_ingest import ExtractedDocument, StandardsIngestError


COURSE_HEADINGS = (
    ("KINDERGARTEN", "kindergarten"),
    ("GRADE 1", "grade_1"),
    ("GRADE 2", "grade_2"),
    ("GRADE 3", "grade_3"),
    ("GRADE 4", "grade_4"),
    ("GRADE 5", "grade_5"),
    ("GRADE 6", "grade_6"),
    ("GRADE 7", "grade_7"),
    ("GRADE 8", "grade_8"),
    ("GRADE 9", "grade_9"),
    ("GRADE 10", "grade_10"),
    ("GRADE 11", "grade_11"),
    ("GRADE 12 — ECONOMICS", "grade_12_economics"),
    ("GRADE 12 — UNITED STATES GOVERNMENT", "grade_12_us_government"),
    ("PSYCHOLOGY", "psychology"),
    ("SOCIOLOGY", "sociology"),
    ("CONTEMPORARY WORLD ISSUES", "contemporary_world_issues"),
    ("HUMAN GEOGRAPHY", "human_geography"),
    ("HISTORICAL STUDIES", "historical_studies"),
    ("HOLOCAUST STUDIES", "holocaust_studies"),
    ("ALABAMA STUDIES", "alabama_studies"),
)


def _document(*, omit: str | None = None) -> ExtractedDocument:
    lines: list[str] = []
    for heading, course_key in COURSE_HEADINGS:
        if course_key == omit:
            continue
        lines.extend(
            [
                heading,
                "Course Overview",
                "Themes and Topics",
                "1",
                "Analyze a historical development using evidence from multiple sources.",
                "1a Compare two perspectives represented in the source set.",
                "Example: Illustrative classroom example that is not a standard.",
                "1b Explain how context affected the perspectives.",
                "Historical Context",
                "2",
                "Evaluate causes and effects of a significant historical event.",
                "3. Construct an evidence-based explanation of continuity and change.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_social_studies_parser_returns_all_expected_grade_and_named_courses() -> None:
    parsed = parse_alabama_social_studies_2024(_document())

    assert len(parsed.courses) == 21
    assert [course.course_key for course in parsed.courses] == [
        key for _, key in COURSE_HEADINGS
    ]
    assert parsed.courses[0].display_name == "Kindergarten"
    assert parsed.courses[9].display_name.startswith(
        "Grade 9 — World History and Geography"
    )
    assert parsed.courses[11].display_name.startswith(
        "Grade 11 — United States History II"
    )
    assert parsed.courses[-1].display_name == "Alabama Studies"


def test_social_studies_parser_reconstructs_detached_main_codes_and_children() -> None:
    parsed = parse_alabama_social_studies_2024(_document())
    grade_nine = next(course for course in parsed.courses if course.course_key == "grade_9")
    by_code = {standard.code: standard for standard in grade_nine.standards}

    assert by_code["1"].text == (
        "Analyze a historical development using evidence from multiple sources."
    )
    assert by_code["1a"].parent_code == "1"
    assert by_code["1a"].text == "Compare two perspectives represented in the source set."
    assert by_code["1b"].parent_code == "1"
    assert "Illustrative classroom example" not in by_code["1a"].text
    assert "Historical Context" not in by_code["1b"].text
    assert by_code["2"].text == (
        "Evaluate causes and effects of a significant historical event."
    )
    assert by_code["3"].parent_code is None


def test_social_studies_parser_fails_closed_if_expected_course_section_disappears() -> None:
    with pytest.raises(StandardsIngestError, match="every expected grade or named course"):
        parse_alabama_social_studies_2024(_document(omit="psychology"))
