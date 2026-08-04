"""Render the Anniston HQI source pages as three independent expandable documents."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from .document_sections import DOCUMENT_FIELDS, READABLE_PAGE_CAPACITY, HqiDocument
from .pdf_generator import fill_hqi_pdf

DOCUMENT_PAGE_INDEX: dict[HqiDocument, int] = {
    HqiDocument.INSTRUCTIONAL_FRAMEWORK: 0,
    HqiDocument.WEEK_AT_A_GLANCE: 1,
    HqiDocument.WEEKLY_REFLECTION: 2,
}

DOCUMENT_TITLES: dict[HqiDocument, str] = {
    HqiDocument.INSTRUCTIONAL_FRAMEWORK: "High Quality Instruction Planning Framework",
    HqiDocument.WEEK_AT_A_GLANCE: "Week at a Glance",
    HqiDocument.WEEKLY_REFLECTION: "Weekly Reflection / PLC Discussion",
}

FIELD_LABELS: dict[str, str] = {
    "teacher": "Teacher",
    "course": "Course",
    "grade": "Grade",
    "week_of": "Week of",
    "unit_topic": "Unit / Topic",
    "standards": "Standards",
    "know": "Know",
    "understand": "Understand",
    "do": "Do",
    "plds": "Performance-Level Descriptors / Proficiency Scale",
    "misconceptions": "Likely Misconceptions",
    "formative": "Formative Assessments",
    "summative": "Summative Assessments",
    "performance_task": "Performance Task",
    "resources": "Resources",
}

DAY_NAMES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
}
DAILY_LABELS = {
    "clt": "Clear Learning Target",
    "rrt": "Rigorous and Relevant Task",
    "cfu": "Checks for Understanding",
    "ri": "Responsive Instruction",
    "sic": "Strong Instructional Culture",
    "esl": "Evidence of Student Learning",
}
REFLECTION_LABELS = {
    1: "What knowledge has been building this week?",
    2: "What understandings are being developed?",
    3: "What evidence is demonstrating mastery?",
    4: "What misconceptions emerged?",
    5: "What standard(s) or parts of the standard need reteaching?",
    6: "Which students need intervention?",
    7: "What is the plan for intervention (Tier 2 and Tier 3)?",
    8: "Which students need enrichment?",
    9: "What is the plan for enrichment?",
    10: "Which instructional moves worked?",
    11: "What instructional adjustments will I make next week?",
    12: "What are next week's instructional priorities?",
}


@dataclass(frozen=True, slots=True)
class RenderedHqiDocument:
    document: HqiDocument
    pdf_bytes: bytes
    page_count: int
    continuation_page_count: int


def _split_at_word_boundary(value: str, capacity: int) -> tuple[str, str]:
    if len(value) <= capacity:
        return value, ""
    split_at = value.rfind(" ", 0, capacity + 1)
    if split_at < max(1, capacity // 2):
        split_at = capacity
    return value[:split_at].rstrip(), value[split_at:].lstrip()


def _field_label(field: str) -> str:
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]
    if field.startswith("reflect_"):
        index = int(field.split("_")[1])
        return REFLECTION_LABELS[index]
    prefix, day = field.split("_", 1)
    return f"{DAY_NAMES[day]} — {DAILY_LABELS[prefix]}"


def _continuation_pdf(
    document: HqiDocument,
    overflow: Sequence[tuple[str, str]],
    metadata: Mapping[str, str],
) -> bytes:
    output = BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TPPContinuationTitle",
        parent=styles["Heading1"],
        fontSize=14,
        leading=17,
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "TPPContinuationMeta",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        spaceAfter=3,
    )
    label_style = ParagraphStyle(
        "TPPContinuationLabel",
        parent=styles["Heading2"],
        fontSize=10,
        leading=13,
        spaceBefore=8,
        spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "TPPContinuationBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=7,
    )

    def footer(canvas: object, doc: object) -> None:
        del doc
        canvas.saveState()  # type: ignore[attr-defined]
        page = canvas.getPageNumber()  # type: ignore[attr-defined]
        canvas.setFont("Helvetica", 8)  # type: ignore[attr-defined]
        canvas.drawRightString(  # type: ignore[attr-defined]
            7.5 * inch,
            0.45 * inch,
            f"Continuation page {page}",
        )
        canvas.restoreState()  # type: ignore[attr-defined]

    teacher_course = (
        f"Teacher: {metadata.get('teacher', '')} &nbsp;&nbsp; "
        f"Course: {metadata.get('course', '')}"
    )
    week_grade = (
        f"Week of: {metadata.get('week_of', '')} &nbsp;&nbsp; "
        f"Grade: {metadata.get('grade', '')}"
    )
    story: list[Flowable] = [
        Paragraph(f"{DOCUMENT_TITLES[document]} — Continuation", title_style),
        Paragraph(teacher_course, meta_style),
        Paragraph(week_grade, meta_style),
        Spacer(1, 0.08 * inch),
    ]
    for field, value in overflow:
        story.append(Paragraph(_field_label(field), label_style))
        paragraphs = value.split("\n\n") or [value]
        for paragraph in paragraphs:
            story.append(Paragraph(paragraph.replace("\n", "<br/>"), body_style))

    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.65 * inch,
        title=f"{DOCUMENT_TITLES[document]} Continuation",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def render_hqi_document(
    template_path: Path,
    payload: Mapping[str, str],
    document: HqiDocument,
    *,
    flatten: bool = False,
) -> RenderedHqiDocument:
    fields = DOCUMENT_FIELDS[document]
    source_values: dict[str, str] = {}
    overflow: list[tuple[str, str]] = []

    for field in fields:
        value = payload.get(field, "")
        first_page, remainder = _split_at_word_boundary(value, READABLE_PAGE_CAPACITY[field])
        source_values[field] = first_page
        if remainder:
            overflow.append((field, remainder))

    filled_packet = PdfReader(BytesIO(fill_hqi_pdf(template_path, source_values, flatten=flatten)))
    writer = PdfWriter()
    writer.add_page(filled_packet.pages[DOCUMENT_PAGE_INDEX[document]])

    if overflow:
        continuation = PdfReader(
            BytesIO(
                _continuation_pdf(
                    document,
                    overflow,
                    {
                        "teacher": payload.get("teacher", ""),
                        "course": payload.get("course", ""),
                        "grade": payload.get("grade", ""),
                        "week_of": payload.get("week_of", ""),
                    },
                )
            )
        )
        for page in continuation.pages:
            writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    page_count = len(writer.pages)
    return RenderedHqiDocument(
        document=document,
        pdf_bytes=output.getvalue(),
        page_count=page_count,
        continuation_page_count=max(0, page_count - 1),
    )


def render_hqi_packet(
    template_path: Path,
    payload: Mapping[str, str],
    *,
    flatten: bool = False,
) -> tuple[bytes, tuple[RenderedHqiDocument, ...]]:
    documents = tuple(
        render_hqi_document(template_path, payload, document, flatten=flatten)
        for document in HqiDocument
    )
    writer = PdfWriter()
    for rendered in documents:
        reader = PdfReader(BytesIO(rendered.pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), documents
