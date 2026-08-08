from hashlib import sha256

import pytest

from app.standards_alabama_social_studies import parse_alabama_social_studies_2024
from app.standards_ingest import ExtractedDocument, StandardsIngestError

COURSES = (
    ("Kindergarten", "kindergarten"),
    ("Grade 1", "grade_1"),
    ("Grade 2", "grade_2"),
    ("Grade 3", "grade_3"),
    ("Grade 4", "grade_4"),
    ("Grade 5", "grade_5"),
    ("Grade 6", "grade_6"),
    ("Grade 7", "grade_7"),
    ("Grade 8", "grade_8"),
    ("Grade 9", "grade_9"),
    ("Grade 10", "grade_10"),
    ("Grade 11", "grade_11"),
    ("Grade 12 — Economics", "grade_12_economics"),
    ("Grade 12 — United States Government", "grade_12_us_government"),
    ("Psychology", "psychology"),
    ("Sociology", "sociology"),
    ("Contemporary World Issues", "contemporary_world_issues"),
    ("Human Geography", "human_geography"),
    ("Historical Studies", "historical_studies"),
    ("Holocaust Studies", "holocaust_studies"),
    ("Alabama Studies", "alabama_studies"),
)

SOURCE_COURSE_KEYS = (
    "kindergarten",
    "grade_1",
    "grade_2",
    "grade_3",
    "grade_4",
    "grade_5",
    "grade_6",
    "grade_7",
    "grade_8",
    "grade_9",
    "grade_10",
    "grade_11",
    "grade_12_us_government",
    "grade_12_economics",
    "psychology",
    "sociology",
    "contemporary_world_issues",
    "human_geography",
    "historical_studies",
    "holocaust_studies",
    "alabama_studies",
)

DISPLAY_BY_KEY = {course_key: display_name for display_name, course_key in COURSES}


def _document(*, omit: str | None = None) -> ExtractedDocument:
    lines: list[str] = []
    for course_key in SOURCE_COURSE_KEYS:
        if course_key == omit:
            continue
        lines.extend(
            [
                DISPLAY_BY_KEY[course_key],
                "Course Overview",
                "Themes and Topics",
                "Content Standards",
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


def test_social_studies_parser_returns_all_expected_courses_in_catalog_order() -> None:
    parsed = parse_alabama_social_studies_2024(_document())

    assert len(parsed.courses) == 21
    assert [course.course_key for course in parsed.courses] == [
        key for _, key in COURSES
    ]
    assert parsed.courses[0].display_name == "Kindergarten"
    assert parsed.courses[9].display_name.startswith(
        "Grade 9 — World History and Geography"
    )
    assert parsed.courses[11].display_name.startswith(
        "Grade 11 — United States History II"
    )
    assert parsed.courses[12].course_key == "grade_12_economics"
    assert parsed.courses[13].course_key == "grade_12_us_government"
    assert parsed.courses[-1].display_name == "Alabama Studies"


def test_social_studies_parser_respects_authoritative_government_then_economics_order() -> None:
    parsed = parse_alabama_social_studies_2024(_document())
    government = next(
        course for course in parsed.courses if course.course_key == "grade_12_us_government"
    )
    economics = next(
        course for course in parsed.courses if course.course_key == "grade_12_economics"
    )

    for course in (government, economics):
        assert [standard.code for standard in course.standards] == [
            "1",
            "1a",
            "1b",
            "2",
            "3",
        ]


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


def test_social_studies_parser_fails_closed_if_expected_section_disappears() -> None:
    with pytest.raises(StandardsIngestError, match="every expected grade or named course"):
        parse_alabama_social_studies_2024(_document(omit="psychology"))
