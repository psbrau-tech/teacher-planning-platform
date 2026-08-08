from hashlib import sha256

import pytest

from app.standards_alabama_dlcs import parse_alabama_dlcs_2025
from app.standards_ingest import ExtractedDocument, StandardsIngestError


def _standards(first: int, last: int, label: str) -> str:
    return " ".join(
        f"{number}. Required {label} content for this standard."
        for number in range(first, last + 1)
    )


def _document(*, omit_grade_8_standard: int | None = None) -> ExtractedDocument:
    lines: list[str] = ["Computational Thinking"]

    # K-2 first table leaves Grade 1 poised at 12 so the developmental notice is
    # required to assign Grade 2 standard 12 to the correct lane.
    lines.extend(
        [
            "Kindergarten Grade 1 Grade 2",
            _standards(1, 10, "Kindergarten"),
            _standards(1, 11, "Grade 1"),
            _standards(1, 11, "Grade 2"),
            "Impact of Computing",
            "Kindergarten Grade 1 Grade 2",
            (
                "Standards for this focus area are developmentally appropriate beginning "
                "in Grade 2. 12. Required Grade 2 content for this standard."
            ),
            "Digital Proficiency",
            "Kindergarten Grade 1 Grade 2",
            _standards(11, 15, "Kindergarten"),
            _standards(12, 17, "Grade 1"),
            _standards(13, 20, "Grade 2"),
        ]
    )

    lines.extend(
        [
            "Computational Thinking",
            "Grade 3 Grade 4 Grade 5",
            _standards(1, 19, "Grade 3"),
            _standards(1, 26, "Grade 4"),
            _standards(1, 24, "Grade 5"),
            "Computing Systems",
            "Grade 6 Grade 7 Grade 8",
            _standards(1, 31, "Grade 6"),
            _standards(1, 32, "Grade 7"),
        ]
    )
    grade_8_numbers = [
        number
        for number in range(1, 37)
        if number != omit_grade_8_standard
    ]
    lines.append(
        " ".join(
            f"{number}. Required Grade 8 content for this standard."
            for number in grade_8_numbers
        )
    )
    lines.extend(
        [
            "Digital Proficiency",
            "Grades 9-12",
            _standards(1, 45, "Grades 9-12"),
        ]
    )

    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_dlcs_parser_reconstructs_all_k8_and_high_school_course_lanes() -> None:
    parsed = parse_alabama_dlcs_2025(_document())

    assert [course.course_key for course in parsed.courses] == [
        "kindergarten",
        "grade_1",
        "grade_2",
        "grade_3",
        "grade_4",
        "grade_5",
        "grade_6",
        "grade_7",
        "grade_8",
        "grades_9_12",
    ]
    assert [len(course.standards) for course in parsed.courses] == [
        15,
        17,
        20,
        19,
        26,
        24,
        31,
        32,
        36,
        45,
    ]


def test_dlcs_parser_uses_developmental_notice_to_skip_blank_grade_lanes() -> None:
    parsed = parse_alabama_dlcs_2025(_document())
    grade_1 = next(course for course in parsed.courses if course.course_key == "grade_1")
    grade_2 = next(course for course in parsed.courses if course.course_key == "grade_2")

    assert grade_1.standards[11].code == "12"
    assert grade_1.standards[11].text == "Required Grade 1 content for this standard."
    assert grade_2.standards[11].code == "12"
    assert grade_2.standards[11].text == "Required Grade 2 content for this standard."


def test_dlcs_parser_splits_multiple_linearized_standards_on_one_line_without_duplication() -> None:
    parsed = parse_alabama_dlcs_2025(_document())
    kindergarten = next(
        course for course in parsed.courses if course.course_key == "kindergarten"
    )

    assert kindergarten.standards[0].text == (
        "Required Kindergarten content for this standard."
    )
    assert kindergarten.standards[1].text == (
        "Required Kindergarten content for this standard."
    )
    assert kindergarten.standards[1].code == "2"


def test_dlcs_parser_fails_closed_when_a_grade_lane_has_a_sequence_gap() -> None:
    with pytest.raises(StandardsIngestError, match="could not assign standard"):
        parse_alabama_dlcs_2025(_document(omit_grade_8_standard=17))
