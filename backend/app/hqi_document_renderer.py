"""Render the Anniston HQI set as three branded, flowing PDF documents."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .document_sections import HqiDocument

AHS_RED = colors.HexColor("#B5121B")
AHS_DARK_RED = colors.HexColor("#7F0C12")
AHS_BLACK = colors.HexColor("#151515")
AHS_DARK_GRAY = colors.HexColor("#4A4A4A")
AHS_LIGHT_GRAY = colors.HexColor("#ECECEC")
AHS_PALE_GRAY = colors.HexColor("#F7F7F7")
AHS_WHITE = colors.white
LOGO_PATH = Path(__file__).parents[1] / "assets" / "ahs_logo.png"

DOCUMENT_TITLES: dict[HqiDocument, str] = {
    HqiDocument.INSTRUCTIONAL_FRAMEWORK: "High Quality Instruction Planning Framework",
    HqiDocument.WEEK_AT_A_GLANCE: "Week at a Glance",
    HqiDocument.WEEKLY_REFLECTION: "Weekly Reflection / PLC Discussion",
}

FRAMEWORK_FIELDS: tuple[tuple[str, str], ...] = (
    ("unit_topic", "Unit / Topic"),
    ("standards", "Content Standards"),
    ("literacy_standards", "Literacy Standards"),
    ("act_preparation", "ACT Preparation"),
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


def _split_text(value: str, *, max_chars: int = 320) -> list[str]:
    """Split long table-cell text at word boundaries into page-safe segments."""
    normalized = " ".join(value.split())
    if not normalized:
        return [""]
    words = normalized.split(" ")
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for word in words:
        added = len(word) + (1 if current else 0)
        if current and current_length + added > max_chars:
            chunks.append(" ".join(current))
            current = [word]
            current_length = len(word)
        else:
            current.append(word)
            current_length += added
    if current:
        chunks.append(" ".join(current))
    return chunks


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "meta": ParagraphStyle(
            "AHSMetadata",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=AHS_BLACK,
        ),
        "meta_label": ParagraphStyle(
            "AHSMetadataLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=AHS_DARK_RED,
            spaceAfter=2,
        ),
        "band": ParagraphStyle(
            "AHSSectionBand",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=AHS_WHITE,
            leftIndent=2,
        ),
        "body_box": ParagraphStyle(
            "AHSBodyBox",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.5,
            textColor=AHS_BLACK,
            borderWidth=0.65,
            borderColor=AHS_DARK_GRAY,
            borderPadding=7,
            backColor=AHS_PALE_GRAY,
            splitLongWords=True,
            allowWidows=1,
            allowOrphans=1,
        ),
        "grid_header": ParagraphStyle(
            "AHSGridHeader",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            alignment=TA_CENTER,
            textColor=AHS_WHITE,
        ),
        "grid_label": ParagraphStyle(
            "AHSGridLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=AHS_BLACK,
        ),
        "grid_body": ParagraphStyle(
            "AHSGridBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=6.6,
            leading=8.2,
            alignment=TA_LEFT,
            textColor=AHS_BLACK,
            splitLongWords=True,
        ),
        "reflection_number": ParagraphStyle(
            "AHSReflectionNumber",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=AHS_WHITE,
        ),
        "reflection_prompt": ParagraphStyle(
            "AHSReflectionPrompt",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=AHS_BLACK,
        ),
        "reflection_body": ParagraphStyle(
            "AHSReflectionBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=AHS_BLACK,
            borderWidth=0.7,
            borderColor=AHS_DARK_GRAY,
            borderPadding=7,
            backColor=AHS_WHITE,
            splitLongWords=True,
            allowWidows=1,
            allowOrphans=1,
        ),
    }


def _metadata_table(payload: Mapping[str, str], styles: dict[str, ParagraphStyle]) -> Table:
    fields = (
        ("Teacher", payload.get("teacher", "")),
        ("Course", payload.get("course", "")),
        ("Grade", payload.get("grade", "")),
        ("Week of", payload.get("week_of", "")),
    )
    cells: list[Flowable] = []
    for label, value in fields:
        cells.append(
            Table(
                [
                    [Paragraph(label.upper(), styles["meta_label"])],
                    [Paragraph(_paragraph_text(value), styles["meta"])],
                ],
                colWidths=[1.73 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), AHS_LIGHT_GRAY),
                        ("BOX", (0, 0), (-1, -1), 0.7, AHS_DARK_GRAY),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.5, AHS_DARK_GRAY),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                ),
            )
        )
    table = Table([cells], colWidths=[1.78 * inch] * 4)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
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
        value = " "
    band = Table(
        [[Paragraph(label.upper(), styles["band"])]],
        colWidths=[7.08 * inch],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), AHS_RED),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        ),
    )
    return [
        band,
        Paragraph(_paragraph_text(value), styles["body_box"]),
        Spacer(1, 0.09 * inch),
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
    header: list[Flowable] = [
        Paragraph("Instructional Component", styles["grid_header"])
    ]
    header.extend(Paragraph(day_name, styles["grid_header"]) for _, day_name in DAY_NAMES)
    data: list[list[Flowable]] = [header]
    component_starts: list[int] = []
    for prefix, label in DAILY_FIELDS:
        day_chunks = [
            _split_text(payload.get(f"{prefix}_{day_key}", "")) for day_key, _ in DAY_NAMES
        ]
        segment_count = max(len(chunks) for chunks in day_chunks)
        component_starts.append(len(data))
        for segment_index in range(segment_count):
            row_label = label if segment_index == 0 else f"{label} (continued)"
            row: list[Flowable] = [Paragraph(row_label, styles["grid_label"])]
            for chunks in day_chunks:
                value = chunks[segment_index] if segment_index < len(chunks) else ""
                row.append(Paragraph(_paragraph_text(value), styles["grid_body"]))
            data.append(row)

    table = LongTable(
        data,
        colWidths=[1.35 * inch] + [1.146 * inch] * 5,
        repeatRows=1,
        splitByRow=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AHS_BLACK),
                ("BACKGROUND", (0, 1), (0, -1), AHS_LIGHT_GRAY),
                ("ROWBACKGROUNDS", (1, 1), (-1, -1), [AHS_WHITE, AHS_PALE_GRAY]),
                ("GRID", (0, 0), (-1, -1), 0.55, AHS_DARK_GRAY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    for row_index in component_starts:
        table.setStyle(
            TableStyle(
                [("LINEABOVE", (0, row_index), (-1, row_index), 1.1, AHS_RED)]
            )
        )
    return [table]


def _reflection_story(
    payload: Mapping[str, str],
    styles: dict[str, ParagraphStyle],
) -> list[Flowable]:
    story: list[Flowable] = []
    for index, (field, prompt) in enumerate(REFLECTION_FIELDS, start=1):
        response = payload.get(field, "") or " "
        header = Table(
            [
                [
                    Paragraph(str(index), styles["reflection_number"]),
                    Paragraph(prompt, styles["reflection_prompt"]),
                ]
            ],
            colWidths=[0.42 * inch, 6.66 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), AHS_RED),
                    ("BACKGROUND", (1, 0), (1, 0), AHS_LIGHT_GRAY),
                    ("BOX", (0, 0), (-1, -1), 0.7, AHS_DARK_GRAY),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            ),
        )
        story.extend(
            [
                header,
                Paragraph(_paragraph_text(response), styles["reflection_body"]),
                Spacer(1, 0.09 * inch),
            ]
        )
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
        canvas.setFillColor(AHS_BLACK)
        canvas.rect(0, 10.02 * inch, 8.5 * inch, 0.98 * inch, fill=1, stroke=0)
        canvas.setFillColor(AHS_RED)
        canvas.rect(0, 9.94 * inch, 8.5 * inch, 0.08 * inch, fill=1, stroke=0)
        if LOGO_PATH.exists():
            canvas.drawImage(
                ImageReader(str(LOGO_PATH)),
                0.48 * inch,
                10.17 * inch,
                width=0.62 * inch,
                height=0.62 * inch,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        canvas.setFillColor(AHS_WHITE)
        canvas.setFont("Helvetica-Bold", 13)
        canvas.drawString(1.25 * inch, 10.56 * inch, "ANNISTON HIGH SCHOOL")
        canvas.setFont("Helvetica-Bold", 9.5)
        canvas.drawString(1.25 * inch, 10.30 * inch, title)
        canvas.setFillColor(AHS_DARK_GRAY)
        canvas.rect(0, 0, 8.5 * inch, 0.48 * inch, fill=1, stroke=0)
        canvas.setFillColor(AHS_WHITE)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(
            0.48 * inch,
            0.19 * inch,
            f"{teacher} | {course} | Week of {week_of}",
        )
        canvas.drawRightString(8.02 * inch, 0.19 * inch, f"Page {page_number}")
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
        topMargin=1.23 * inch,
        bottomMargin=0.66 * inch,
        title=DOCUMENT_TITLES[document],
        allowSplitting=True,
    )

    story: list[Flowable] = [_metadata_table(payload, styles), Spacer(1, 0.16 * inch)]
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
