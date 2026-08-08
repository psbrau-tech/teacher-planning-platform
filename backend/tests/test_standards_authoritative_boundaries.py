from hashlib import sha256

from app.standards_alabama_health import parse_alabama_health_2019
from app.standards_alabama_physical_education import (
    parse_alabama_physical_education_2019,
)
from app.standards_ingest import ExtractedDocument

HEALTH_PREFIXES = ("K", "1", "2", "3", "4", "5", "6", "7", "8", "HE", "HA", "WH")
PE_PREFIXES = (
    "K",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "BK",
    "AK",
    "SO",
    "AC",
    "SC",
    "LS",
    "VA",
)


def _extracted(lines: list[str]) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_health_ignores_numbering_examples_before_authoritative_standards_tables() -> None:
    lines = [
        "Numbering of Content Standards",
        "5.1.3 indicates grade 5, anchor standard 1, content standard 3.",
        "K .7.1 1.7.1 2.7.1 3.7.1 4.7.1 5.7.1",
        "Grades K-5 Standards",
    ]
    for prefix in HEALTH_PREFIXES:
        lines.extend(
            [
                f"{prefix}.1.1",
                f"Required authoritative health standard one for {prefix}.",
                f"{prefix}.1.2",
                f"Required authoritative health standard two for {prefix}.",
            ]
        )

    parsed = parse_alabama_health_2019(_extracted(lines))
    kindergarten = parsed.courses[0]
    grade_five = next(course for course in parsed.courses if course.course_key == "grade_5")

    assert [standard.code for standard in kindergarten.standards] == ["K.1.1", "K.1.2"]
    assert [standard.code for standard in grade_five.standards] == ["5.1.1", "5.1.2"]


def test_pe_ignores_level_comparison_example_before_beginning_kinesiology() -> None:
    lines: list[str] = []
    for prefix in PE_PREFIXES:
        if prefix == "BK":
            continue
        lines.extend(
            [
                f"{prefix}-1.1 Required authoritative PE standard one.",
                f"{prefix}-1.2 Required authoritative PE standard two.",
            ]
        )

    lines.extend(
        [
            "Example of Level 1 vs. Level 2 with Suggested Method to Implement and Differentiate Between the Levels",
            "Standard 3 Level 1",
            "Students can:",
            "Level 2",
            "Students can:",
            "BK-3.1",
            "Illustrative wording that must not become governed standard text.",
            "Beginning Kinesiology",
            "BK-3.1",
            "Required Beginning Kinesiology standard one.",
            "BK-3.2",
            "Required Beginning Kinesiology standard two.",
        ]
    )

    parsed = parse_alabama_physical_education_2019(_extracted(lines))
    beginning = next(
        course for course in parsed.courses if course.course_key == "beginning_kinesiology"
    )

    assert [standard.code for standard in beginning.standards] == ["BK-3.1", "BK-3.2"]
    assert beginning.standards[0].text == "Required Beginning Kinesiology standard one."
