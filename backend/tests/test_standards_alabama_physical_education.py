from hashlib import sha256

import pytest

from app.standards_alabama_physical_education import (
    parse_alabama_physical_education_2019,
)
from app.standards_ingest import ExtractedDocument, StandardsIngestError

PREFIXES = (
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


def _document(*, omit: str | None = None) -> ExtractedDocument:
    lines: list[str] = []
    for prefix in PREFIXES:
        if prefix == omit:
            continue
        lines.extend(
            [
                f"{prefix}-1.1 Demonstrate the first required movement standard.",
                "Level 1",
                "Required level-one wording remains part of the standard.",
                "Level 2",
                "Required level-two wording remains part of the standard.",
                "a. Demonstrate a required supporting skill.",
                "Examples: Supplemental example must not become standard text.",
                "Example continuation must also be excluded.",
                f"{prefix}-2.1 Apply the second required movement standard.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_physical_education_parser_returns_k8_and_all_high_school_courses() -> None:
    parsed = parse_alabama_physical_education_2019(_document())

    assert len(parsed.courses) == 16
    assert parsed.courses[0].course_key == "kindergarten"
    assert parsed.courses[8].course_key == "grade_8"
    assert parsed.courses[9].course_key == "beginning_kinesiology"
    assert parsed.courses[-1].course_key == "varsity_athletics"


def test_physical_education_parser_preserves_required_levels_and_children() -> None:
    parsed = parse_alabama_physical_education_2019(_document())
    strength = next(
        course for course in parsed.courses if course.course_key == "strength_conditioning"
    )
    by_code = {standard.code: standard for standard in strength.standards}

    assert by_code["SC-1.1"].text == (
        "Demonstrate the first required movement standard. "
        "Required level-one wording remains part of the standard. "
        "Required level-two wording remains part of the standard."
    )
    assert by_code["SC-1.1a"].parent_code == "SC-1.1"
    assert by_code["SC-1.1a"].text == "Demonstrate a required supporting skill."
    assert "Supplemental example" not in by_code["SC-1.1a"].text
    assert by_code["SC-2.1"].parent_code is None


def test_physical_education_parser_normalizes_spacing_around_source_codes() -> None:
    lines = []
    for prefix in PREFIXES:
        lines.extend(
            [
                f"{prefix} - 3 . 1 Required standard one.",
                f"{prefix}-3.2 Required standard two.",
            ]
        )
    normalized = "\n".join(lines)
    parsed = parse_alabama_physical_education_2019(
        ExtractedDocument(
            lines=tuple(lines),
            normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
        )
    )

    kinesiology = next(
        course for course in parsed.courses if course.course_key == "beginning_kinesiology"
    )
    assert [standard.code for standard in kinesiology.standards] == ["BK-3.1", "BK-3.2"]


def test_physical_education_parser_collects_split_code_and_text_rows() -> None:
    lines: list[str] = []
    for prefix in PREFIXES:
        lines.extend(
            [
                f"{prefix}-1.1",
                f"Required split-line physical education standard one for {prefix}.",
                f"{prefix}-1.2",
                f"Required split-line physical education standard two for {prefix}.",
            ]
        )
    normalized = "\n".join(lines)
    parsed = parse_alabama_physical_education_2019(
        ExtractedDocument(
            lines=tuple(lines),
            normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
        )
    )
    kindergarten = parsed.courses[0]
    assert [standard.code for standard in kindergarten.standards] == ["K-1.1", "K-1.2"]
    assert kindergarten.standards[0].text == (
        "Required split-line physical education standard one for K."
    )


def test_physical_education_parser_fails_closed_when_course_prefix_is_missing() -> None:
    with pytest.raises(StandardsIngestError, match="Varsity Athletics"):
        parse_alabama_physical_education_2019(_document(omit="VA"))
