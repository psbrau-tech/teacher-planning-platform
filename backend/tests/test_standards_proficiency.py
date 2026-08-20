from hashlib import sha256

import pytest

from app.standards_ingest import ExtractedDocument, StandardsIngestError
from app.standards_proficiency import parse_alabama_ela_proficiency


def _document(grade: int = 9) -> ExtractedDocument:
    lines: list[str] = [
        "Alabama Course of Study: English Language Arts",
        "PROFICIENCY SCALES",
        f"Grade: {grade}",
        "Literacy Type: Critical Literacy",
        "Focus Area: Reception",
        "Category: Reading",
    ]
    for code in range(1, 6):
        lines.extend(
            [
                f"Standard: {code}. Grade {grade} standard {code} exact wording.",
                "Score 4.0",
                f"Extension application for standard {code}.",
                "3.5 In addition to score 3.0 performance with partial success.",
                "Score 3.0",
                f"Proficient performance for standard {code}.",
                "2.5 Partial knowledge of the 3.0 content.",
                "Score 2.0",
                f"Foundational knowledge for standard {code}.",
                "1.5 Partial success at the 2.0 content.",
                "Score 1.0",
                "With help, partial success.",
                "0.5 With help, partial success of 2.0 content.",
                "Score 0.0",
                "Even with help, no understanding demonstrated.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _current_format_document(grade: int = 6) -> ExtractedDocument:
    lines: list[str] = [
        "Alabama Course of Study: English Language Arts",
        "PROFICIENCY SCALES",
        f"Grade: {grade}th",
        "Literacy Type: Critical Literacy",
        "Focus Area: Reception",
        "Category: Reading",
    ]
    for code in range(1, 6):
        lines.extend(
            [
                f"Standard {code}: Current Grade {grade} standard {code} exact wording",
                "continued standard wording.",
                "Sample",
                "Activities & Resources",
                "Score",
                "4.0",
                f"Extension application for current standard {code}.",
                "3.5 In addition to score 3.0 performance with partial success.",
                "Score",
                "3.0",
                f"Proficient performance for current standard {code}.",
                "2.5 Partial knowledge of the 3.0 content.",
                "Score",
                "2.0",
                f"Foundational knowledge for current standard {code}.",
                "1.5 Partial success at the 2.0 content.",
                "Score",
                "1.0",
                "With help, partial success.",
                "Score",
                "0.0",
                "Even with help, no understanding demonstrated.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _inline_boundary_document(grade: int = 12, *, invisible: bool = False) -> ExtractedDocument:
    separator = "\u200b " if invisible else " "
    lines: list[str] = [
        "Alabama Course of Study: English Language Arts",
        "PROFICIENCY SCALES",
        f"Grade: {grade}th",
        "Literacy Type: Critical Literacy",
        "Focus Area: Reception",
        "Category: Reading",
    ]
    for code in range(1, 6):
        lines.extend(
            [
                (
                    f"Standard {code}: Grade {grade} standard {code} exact wording. "
                    f"Sample{separator}Activities & Resources"
                ),
                "Score",
                "4.0",
                f"Extension application for current standard {code}.",
                "Score",
                "3.0",
                f"Proficient performance for current standard {code}.",
                "Score",
                "2.0",
                f"Foundational knowledge for current standard {code}.",
            ]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_proficiency_parser_preserves_standard_and_performance_levels() -> None:
    parsed = parse_alabama_ela_proficiency(
        "alabama_ela_proficiency_grade_9",
        _document(),
    )

    assert parsed.grade_band == "9"
    assert parsed.parser_version == "gate-e-alabama-ela-proficiency-6-12-v4"
    assert len(parsed.scales) == 5
    first = parsed.scales[0]
    assert first.standard_code == "1"
    assert first.standard_text == "Grade 9 standard 1 exact wording."
    assert first.literacy_type == "Critical Literacy"
    assert first.focus_area == "Reception"
    assert first.category == "Reading"
    assert first.levels["4.0"] == "Extension application for standard 1."
    assert first.levels["3.0"] == "Proficient performance for standard 1."
    assert first.levels["2.0"] == "Foundational knowledge for standard 1."


def test_proficiency_parser_accepts_current_alsde_pdf_layout() -> None:
    parsed = parse_alabama_ela_proficiency(
        "alabama_ela_proficiency_grade_6",
        _current_format_document(),
    )

    assert parsed.grade_band == "6"
    assert len(parsed.scales) == 5
    first = parsed.scales[0]
    assert first.standard_code == "1"
    assert first.standard_text == (
        "Current Grade 6 standard 1 exact wording continued standard wording."
    )
    assert "Sample" not in first.standard_text
    assert "Activities & Resources" not in first.standard_text
    assert first.levels["4.0"] == "Extension application for current standard 1."
    assert first.levels["3.0"] == "Proficient performance for current standard 1."
    assert first.levels["2.0"] == "Foundational knowledge for current standard 1."


def test_proficiency_parser_trims_inline_sample_activities_heading() -> None:
    parsed = parse_alabama_ela_proficiency(
        "alabama_ela_proficiency_grade_12",
        _inline_boundary_document(),
    )

    first = parsed.scales[0]
    assert first.standard_text == "Grade 12 standard 1 exact wording."
    assert "Sample Activities & Resources" not in first.standard_text
    assert first.levels["4.0"] == "Extension application for current standard 1."
    assert first.levels["3.0"] == "Proficient performance for current standard 1."
    assert first.levels["2.0"] == "Foundational knowledge for current standard 1."


def test_proficiency_parser_trims_invisible_inline_sample_heading_artifact() -> None:
    parsed = parse_alabama_ela_proficiency(
        "alabama_ela_proficiency_grade_12",
        _inline_boundary_document(invisible=True),
    )

    first = parsed.scales[0]
    assert first.standard_text == "Grade 12 standard 1 exact wording."
    assert "Activities & Resources" not in first.standard_text


def test_proficiency_parser_rejects_grade_mismatch() -> None:
    with pytest.raises(StandardsIngestError, match="expected Grade 6"):
        parse_alabama_ela_proficiency(
            "alabama_ela_proficiency_grade_6",
            _document(grade=9),
        )


def test_proficiency_parser_rejects_incomplete_core_levels() -> None:
    document = _document()
    lines = list(document.lines)
    lines = [line for line in lines if line != "Score 2.0"]
    broken = ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=document.normalized_sha256,
    )
    with pytest.raises(StandardsIngestError, match="missing one or more core performance levels"):
        parse_alabama_ela_proficiency(
            "alabama_ela_proficiency_grade_9",
            broken,
        )
