from hashlib import sha256
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.standards_ingest import (
    ExtractedDocument,
    FetchedSource,
    StandardsIngestError,
    extract_document,
    parse_document,
)


def _extracted(*lines: str) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_ela_grade_10_parser_preserves_recurring_and_content_standards() -> None:
    document = _extracted(
        "GRADE 10",
        "RECURRING STANDARDS FOR GRADES 9-12",
        "Students will:",
        "R1. Read a variety of print and nonprint documents.",
        "R2. Read and comprehend literary texts.",
        "R3. Utilize active listening skills.",
        "R4. Use digital and electronic tools appropriately.",
        "R5. Utilize a writing process.",
        "R6. Employ conventions of grammar, mechanics, and usage.",
        "R7. Use context clues to determine meanings.",
        "GRADE 10 CONTENT STANDARDS",
        *[f"{number}. Grade ten standard {number}." for number in range(1, 28)],
        "GRADE 11",
    )

    parsed = parse_document("alabama_ela_2021", document)

    assert len(parsed.courses) == 1
    course = parsed.courses[0]
    assert course.course_key == "english_10"
    assert course.standards[0].code == "ELA10.R1"
    assert course.standards[0].text == "Read a variety of print and nonprint documents."
    assert course.standards[-1].code == "ELA10.27"
    assert course.standards[-1].text == "Grade ten standard 27."


def test_bma_parser_keeps_foundational_and_course_specific_standards() -> None:
    lines: list[str] = []
    for title in ("BUSINESS ESSENTIALS", "BUSINESS COMMUNICATIONS", "BUSINESS LAW"):
        lines.extend(
            [
                title.title(),
                "Grade Levels 9-12",
                "Foundational",
                "Standards",
                *[f"{number}. Shared foundation {number}." for number in range(1, 7)],
                title,
                "CONTENT STANDARDS",
                *[f"{number}. {title.title()} standard {number}." for number in range(1, 6)],
            ]
        )

    parsed = parse_document("alabama_bma_2021", _extracted(*lines))

    assert {course.course_key for course in parsed.courses} == {
        "business_essentials",
        "business_communications",
        "business_law",
    }
    essentials = next(course for course in parsed.courses if course.course_key == "business_essentials")
    assert essentials.grade_band == "9-12"
    assert essentials.standards[0].code == "F1"
    assert essentials.standards[0].text == "Shared foundation 1."
    assert essentials.standards[6].code == "1"
    assert essentials.standards[6].text == "Business Essentials standard 1."


def test_army_parser_groups_exact_lesson_identifiers_by_let_level() -> None:
    lines: list[str] = []
    for level in range(1, 5):
        for lesson in range(1, 6):
            lines.extend(
                [
                    f"U{level}C1L{lesson}: Lesson {lesson}",
                    f"Competency for LET {level} lesson {lesson}",
                    f"• Objective {lesson}",
                ]
            )
        lines.append(f"Unit {level + 1}: Leadership Education and Training")

    parsed = parse_document("army_jrotc_v12", _extracted(*lines))

    assert [course.course_key for course in parsed.courses] == [
        "army_jrotc_let_1",
        "army_jrotc_let_2",
        "army_jrotc_let_3",
        "army_jrotc_let_4",
    ]
    let_two = parsed.courses[1]
    assert let_two.standards[0].code == "U2C1L1"
    assert let_two.standards[0].text == (
        "Lesson 1 Competency for LET 2 lesson 1 Objective 1"
    )


def test_docx_extraction_reads_wordprocessingml_paragraphs_in_order() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
  <w:body>
    <w:p><w:r><w:t>U1C1L1: Foundations</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Explain the mission</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
  </w:body>
</w:document>"""
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    raw = payload.getvalue()
    source = FetchedSource(
        requested_url="https://example.invalid/guide.docx",
        resolved_url="https://example.invalid/guide.docx",
        document_format="docx",
        content=raw,
        source_sha256=sha256(raw).hexdigest(),
    )

    extracted = extract_document(source)

    assert extracted.lines == ("U1C1L1: Foundations", "Explain the mission")


def test_parser_fails_closed_when_expected_course_structure_disappears() -> None:
    with pytest.raises(StandardsIngestError, match="section was not found"):
        parse_document("alabama_ela_2021", _extracted("unexpected replacement document"))
