from hashlib import sha256

import pytest

from app import standards_alabama_arts as arts
from app.standards_ingest import ExtractedDocument, StandardsIngestError

DISCIPLINES = ("DANCE", "MEDIA ARTS", "MUSIC", "THEATRE", "VISUAL ARTS")


def _single_section(discipline: str, name: str) -> list[str]:
    lines = [discipline, name, "Content Standards", "Creating", "Explore"]
    for number in range(1, 12):
        lines.extend(
            [
                f"{number}. {arts._ANCHOR_TEXT[number]}",
                f"{number}. Required {name} standard wording for anchor {number}.",
            ]
        )
    return lines


def _full_document(*, section_count: int = 33) -> ExtractedDocument:
    lines: list[str] = []
    for index in range(section_count):
        discipline = DISCIPLINES[index % len(DISCIPLINES)]
        lines.extend(_single_section(discipline, f"Synthetic Section {index + 1}"))
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_arts_parser_requires_33_authoritative_content_sections() -> None:
    parsed = arts.parse_alabama_arts_2024(_full_document())

    assert len(parsed.courses) == 33
    assert all(len(course.standards) == 11 for course in parsed.courses)
    assert parsed.courses[0].standards[0].text == (
        "Required Synthetic Section 1 standard wording for anchor 1."
    )

    with pytest.raises(StandardsIngestError, match="exactly 33"):
        arts.parse_alabama_arts_2024(_full_document(section_count=32))


def test_arts_lane_discovery_uses_authoritative_grade_and_level_headers() -> None:
    grade_lanes = arts._discover_lanes(
        (
            "Kindergarten Grade 1 Grade 2",
            "1. Required standard.",
        ),
        "Kindergarten Grade 1 Grade 2",
    )
    level_lanes = arts._discover_lanes(
        (
            "Grades 6-8",
            "Level I Level II Level III",
            "1. Required standard.",
        ),
        "Grades 6-8",
    )

    assert grade_lanes == (
        ("Kindergarten", "K"),
        ("Grade 1", "1"),
        ("Grade 2", "2"),
    )
    assert level_lanes == (
        ("Level I", "6-8"),
        ("Level II", "6-8"),
        ("Level III", "6-8"),
    )


def test_arts_three_lane_two_cell_merge_duplicates_only_shared_late_cell() -> None:
    section = arts._Section(
        marker_index=0,
        end_index=0,
        discipline="MEDIA ARTS",
        section_name="Kindergarten Grade 1 Grade 2",
        lanes=(
            ("Kindergarten", "K"),
            ("Grade 1", "1"),
            ("Grade 2", "2"),
        ),
    )
    occurrences = {
        number: [
            (f"Kindergarten wording {number}.", "Creating"),
            (f"Grade 1 wording {number}.", "Creating"),
            (f"Grade 2 wording {number}.", "Creating"),
        ]
        for number in range(1, 12)
    }
    occurrences[11] = [
        ("Kindergarten wording 11.", "Connecting"),
        ("Shared Grade 1 and Grade 2 wording 11.", "Connecting"),
    ]

    courses = arts._courses_from_section(section, occurrences)

    assert courses[0].standards[-1].text == "Kindergarten wording 11."
    assert courses[1].standards[-1].text == "Shared Grade 1 and Grade 2 wording 11."
    assert courses[2].standards[-1].text == "Shared Grade 1 and Grade 2 wording 11."


def test_arts_single_course_preserves_repeated_anchor_number_as_unique_internal_code() -> None:
    section = arts._Section(
        marker_index=0,
        end_index=0,
        discipline="MUSIC",
        section_name="Grades 3-5 General Music",
        lanes=(("Grades 3-5 General Music", "3-5"),),
    )
    occurrences = {
        number: [(f"Required wording {number}.", "Responding")]
        for number in range(1, 12)
    }
    occurrences[7] = [
        ("First required responding standard.", "Responding"),
        ("Second required responding standard.", "Responding"),
    ]

    courses = arts._courses_from_section(section, occurrences)
    by_code = {standard.code: standard.text for standard in courses[0].standards}

    assert by_code["7"] == "First required responding standard."
    assert by_code["7.2"] == "Second required responding standard."
