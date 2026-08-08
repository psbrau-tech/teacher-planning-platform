from hashlib import sha256

import pytest

from app.standards_alabama_health import parse_alabama_health_2019
from app.standards_ingest import ExtractedDocument, StandardsIngestError

PREFIXES = ("K", "1", "2", "3", "4", "5", "6", "7", "8", "HE", "HA", "WH")


def _document(*, omit: str | None = None) -> ExtractedDocument:
    lines: list[str] = []
    for prefix in PREFIXES:
        if prefix == omit:
            continue
        separator = "." if prefix not in {"HE", "HA", "WH"} else "."
        lines.extend(
            [
                "Anchor Standard 1: Synthetic anchor wording.",
                f"{prefix}{separator}1.1 Required health standard one for {prefix}.",
                "a. Required supporting sub-standard.",
                "Examples: Example content must not become authoritative standard text.",
                "Example continuation that must also be excluded.",
                f"{prefix}{separator}2.1 Required health standard two for {prefix}.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_health_parser_returns_k8_required_health_and_both_electives() -> None:
    parsed = parse_alabama_health_2019(_document())

    assert len(parsed.courses) == 12
    assert parsed.courses[0].course_key == "kindergarten"
    assert parsed.courses[8].course_key == "grade_8"
    assert parsed.courses[9].course_key == "health_education"
    assert parsed.courses[10].course_key == "leaders_health_advocacy"
    assert parsed.courses[11].course_key == "world_health"


def test_health_parser_normalizes_codes_and_preserves_required_children() -> None:
    parsed = parse_alabama_health_2019(_document())
    health = next(course for course in parsed.courses if course.course_key == "health_education")
    by_code = {standard.code: standard for standard in health.standards}

    assert by_code["HE.1.1"].text == "Required health standard one for HE."
    assert by_code["HE.1.1a"].parent_code == "HE.1.1"
    assert by_code["HE.1.1a"].text == "Required supporting sub-standard."
    assert "Example content" not in by_code["HE.1.1a"].text
    assert by_code["HE.2.1"].parent_code is None


def test_health_parser_accepts_source_spacing_variants() -> None:
    lines = [
        "HE 2.1 Analyze an external influence.",
        "HE.2.2 Analyze another external influence.",
        "HA 6.2 Compile survey results.",
        "HA.6.3 Implement a strategy.",
        "WH. 5.1 Evaluate alternatives.",
        "WH.5.2 Examine barriers.",
    ]
    for prefix in ("K", "1", "2", "3", "4", "5", "6", "7", "8"):
        lines.extend(
            [
                f"{prefix}.1.1 Required standard one.",
                f"{prefix}.1.2 Required standard two.",
            ]
        )
    normalized = "\n".join(lines)
    parsed = parse_alabama_health_2019(
        ExtractedDocument(
            lines=tuple(lines),
            normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
        )
    )

    health = next(course for course in parsed.courses if course.course_key == "health_education")
    advocacy = next(
        course for course in parsed.courses if course.course_key == "leaders_health_advocacy"
    )
    world = next(course for course in parsed.courses if course.course_key == "world_health")
    assert [standard.code for standard in health.standards] == ["HE.2.1", "HE.2.2"]
    assert [standard.code for standard in advocacy.standards] == ["HA.6.2", "HA.6.3"]
    assert [standard.code for standard in world.standards] == ["WH.5.1", "WH.5.2"]


def test_health_parser_fails_closed_when_a_required_course_family_is_missing() -> None:
    with pytest.raises(StandardsIngestError, match="World Health"):
        parse_alabama_health_2019(_document(omit="WH"))
