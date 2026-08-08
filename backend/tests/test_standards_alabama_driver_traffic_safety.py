from hashlib import sha256

import pytest

from app.standards_alabama_driver_traffic_safety import (
    parse_alabama_driver_traffic_safety_2007,
)
from app.standards_ingest import ExtractedDocument, StandardsIngestError


def _document(*, omit: int | None = None) -> ExtractedDocument:
    lines: list[str] = ["CLASSROOM PHASE"]
    for number in range(1, 27):
        if number == omit:
            continue
        if number == 20:
            lines.append("BEHIND-THE-WHEEL PHASE")
        lines.append(f"{number}. Required driver safety standard {number}.")
        if number == 3:
            lines.extend(
                [
                    "a. Required supporting skill.",
                    "Examples: Supplemental example must not enter authoritative wording.",
                    "Example continuation must also be excluded.",
                ]
            )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_driver_traffic_parser_returns_single_course_with_main_standards_1_to_26() -> None:
    parsed = parse_alabama_driver_traffic_safety_2007(_document())

    assert len(parsed.courses) == 1
    course = parsed.courses[0]
    assert course.course_key == "driver_traffic_safety"
    main_codes = [
        standard.code for standard in course.standards if standard.parent_code is None
    ]
    assert main_codes == [str(number) for number in range(1, 27)]


def test_driver_traffic_parser_preserves_phase_and_required_children_only() -> None:
    parsed = parse_alabama_driver_traffic_safety_2007(_document())
    by_code = {standard.code: standard for standard in parsed.courses[0].standards}

    assert by_code["3"].strand == "Classroom Phase"
    assert by_code["3a"].parent_code == "3"
    assert by_code["3a"].text == "Required supporting skill."
    assert "Supplemental example" not in by_code["3a"].text
    assert by_code["20"].strand == "Behind-the-Wheel Phase"


def test_driver_traffic_parser_fails_closed_when_main_sequence_changes() -> None:
    with pytest.raises(StandardsIngestError, match="standards 1 through 26"):
        parse_alabama_driver_traffic_safety_2007(_document(omit=17))
