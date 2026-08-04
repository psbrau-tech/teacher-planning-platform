"""Render the Anniston HQI set as three independent, flowing PDF documents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .document_sections import HqiDocument

DOCUMENT_TITLES: dict[HqiDocument, str] = {
    HqiDocument.INSTRUCTIONAL_FRAMEWORK: "High Quality Instruction Planning Framework",
    HqiDocument.WEEK_AT_A_GLANCE: "Week at a Glance",
    HqiDocument.WEEKLY_REFLECTION: "Weekly Reflection / PLC Discussion",
}

FRAMEWORK_FIELDS: tuple[tuple[str, str], ...] = (
    ("unit_topic", "Unit / Topic"),
    ("standards", "Standards"),
    ("know", "Know"),
    ("understand", "Understand"),
    ("do", "Do"),
    ("plds", "Performance-Level Descriptors / Proficiency Scale"),
    ("misconceptions", "Likely Misconceptions"),
    ("formative", "Formative Assessments"),
    ("summative", "Summative Assessments"),
    ("performance_task", "Performance Task"),
    ("resources", "Resources"),
)

DAY_NAMES: tuple[tuple[str, str], ...] = (
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
)

DAILY_FIELDS: tuple[tuple[str, str], ...] = (
    ("clt", "Clear Learning Target"),
    ("rrt", "Rigorous and Relevant Task"),
    ("cfu", "Checks for Understanding"),
    ("ri", "Responsive Instruction"),
    ("sic", "Strong Instructional Culture"),
    ("esl", "Evidence of Student Learning"),
)

REFLECTION_FIELDS: tuple[tuple[str, str], ...] = (
    ("reflect_1", "What knowledge has been building this week?"),
    ("reflect_2", "What understandings are being developed?"),
    ("reflect_3", "What evidence is demonstrating mastery?"),
    ("reflect_4", "What misconceptions emerged?"),
    ("reflect_5", "What standard(s) or parts of the standard need reteaching?"),
    ("reflect_6", "Which students need intervention?"),
    ("reflect_7", "What is the plan for intervention (Tier 2 and Tier 3)?"),
    ("reflect_8", "Which students need enrichment?"),
    ("reflect_9", "What is the plan for enrichment?"),
    ("reflect_10", "Which instructional moves worked?"),
    ("reflect_11", "What instructional adjustments will I make next week?"),
    ("reflect_12", "What are next week's instructional priorities?"),
)


@dataclass(frozen=True, slots=True)
class RenderedHqiDocument:
    document: HqiDocument
    pdf_bytes: bytes
    page_count: int
    continuation_page_count: int


def _paragraph_text(value: str) -> str:
    escaped = escape(value.strip())
    return escaped.replace("\n\n", "<br/><br/>").replace("\n", "<br/>") or "&nbsp;"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TPPTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "meta": ParagraphStyle(
            "TPPMeta",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
        ),
        "section": ParagraphStyle(
            "TPPSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            spaceBefore=7,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "day": ParagraphStyle(
            "TPPDay",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=9,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "TPPBody",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            spaceAfter=5,
            splitLongWords=True,
        ),
    }


def _metadata_table(payload: Mapping[str, str], styles: dict[str, ParagraphStyle]) -> Table:
    cells = [
        Paragraph(f"<b>Teacher:</b> {_paragraph_text(payload.get('teacher', ''))}", styles["meta"]),
        Paragraph(f"<b>Course:</b> {_paragraph_text(payload.get('course', ''))}", styles["meta"]),
        Paragraph(f"<b>Grade:</b> {_paragraph_text(payload.get('grade', ''))}", styles["meta"]),
        Paragraph(f"<b>Week of:</b> {_paragraph_text(payload.get('week_of', ''))}", styles["meta"]),
    ]
    table = Table([cells[:2], cells[2:]], colWidths=[3.55 * inch, 3.55 * inch])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _section_block(
    label: str,
    value: str,
    styles: dict[str, ParagraphStyle],
) -> list[Flowable]:
    if not value.strip():
        return []
    return [
        Paragraph(label, styles["section"]),
        Paragraph(_paragraph_text(value), styles["body"]),
    ]


def _framework_story(
    payload: Mapping[str, str],
    styles: dict[str, ParagraphStyle],
) -> list[Flowable]:
    story: list[Flowable] = []
    for field, label in FRAMEWORK_FIELDS:
        story.extend(_section_block(label, payload.get(field, ""), styles))
    return story


def _week_story(
    payload: Mapping[str, str],
    styles: dict[str, ParagraphStyle],
) -> list[Flowable]:
    story: list[Flowable] = []
    rendered_day_count = 0
    for day_key, day_name in DAY_NAMES:
        day_blocks: list[Flowable] = []
        for prefix, label in DAILY_FIELDS:
            field = f"{prefix}_{day_key}"
            day_blocks.extend(_section_block(label, payload.get(field, ""), styles))
        if not day_blocks:
            continue
        if rendered_day_count:
            story.append(Spacer(1, 0.08 * inch))
        story.append(Paragraph(day_name, styles["day"]))
        story.extend(day_blocks)
        rendered_day_count += 1
    return story


def _reflection_story(
    payload: Mapping[str, str],
    styles: dict[str, ParagraphStyle],
) -> list[Flowable]:
    story: list[Flowable] = []
    for field, label in REFLECTION_FIELDS:
        story.extend(_section_block(label, payload.get(field, ""), styles))
    return story


def _document_story(
    document: HqiDocument,
    payload: Mapping[str, str],
    styles: dict[str, ParagraphStyle],
) -> list[Flowable]:
    if document == HqiDocument.INSTRUCTIONAL_FRAMEWORK:
        return _framework_story(payload, styles)
    if document == HqiDocument.WEEK_AT_A_GLANCE:
        return _week_story(payload, styles)
    return _reflection_story(payload, styles)


def _page_decorator(
    document: HqiDocument,
    payload: Mapping[str, str],
) -> Callable[[Canvas, SimpleDocTemplate], None]:
    title = DOCUMENT_TITLES[document]
    teacher = payload.get("teacher", "")
    course = payload.get("course", "")
    week_of = payload.get("week_of", "")

    def decorate(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        del doc
        canvas.saveState()
        page_number = canvas.getPageNumber()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            0.65 * inch,
            0.42 * inch,
            f"{teacher} | {course} | Week of {week_of}",
        )
        canvas.drawRightString(
            7.85 * inch,
            0.42 * inch,
            f"{title} | Page {page_number}",
        )
        canvas.restoreState()

    return decorate


def render_hqi_document(
    template_path: Path,
    payload: Mapping[str, str],
    document: HqiDocument,
    *,
    flatten: bool = False,
) -> RenderedHqiDocument:
    del flatten
    if not template_path.exists():
        raise FileNotFoundError(template_path)

    styles = _styles()
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.7 * inch,
        title=DOCUMENT_TITLES[document],
        allowSplitting=True,
    )

    story: list[Flowable] = [
        Paragraph(DOCUMENT_TITLES[document], styles["title"]),
        _metadata_table(payload, styles),
        Spacer(1, 0.12 * inch),
    ]
    story.extend(_document_story(document, payload, styles))

    decorator = _page_decorator(document, payload)
    doc.build(story, onFirstPage=decorator, onLaterPages=decorator)
    pdf_bytes = output.getvalue()
    page_count = len(PdfReader(BytesIO(pdf_bytes)).pages)
    return RenderedHqiDocument(
        document=document,
        pdf_bytes=pdf_bytes,
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
