from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.document_sections import HqiDocument
from app.hqi_document_renderer import render_hqi_document, render_hqi_packet

TEMPLATE_PATH = Path(__file__).parents[1] / "assets" / "anniston_hqi_lesson_plan.fillable.pdf"


def base_payload() -> dict[str, str]:
    return {
        "teacher": "Synthetic Teacher",
        "course": "LET 1",
        "grade": "9-12",
        "week_of": "August 10, 2026",
        "unit_topic": "JROTC Foundations",
        "standards": "Army JROTC leadership competency",
        "literacy_standards": "Cite specific evidence from technical text.",
        "act_preparation": "Practice concise evidence-based written responses.",
        "clt_mon": "Explain JROTC expectations.",
        "reflect_1": "Cadets built foundational knowledge.",
    }


def test_each_source_page_renders_as_an_independent_document() -> None:
    for document in HqiDocument:
        rendered = render_hqi_document(TEMPLATE_PATH, base_payload(), document)
        reader = PdfReader(BytesIO(rendered.pdf_bytes))
        assert rendered.page_count >= 1
        assert rendered.continuation_page_count == rendered.page_count - 1
        assert len(reader.pages) == rendered.page_count


def test_long_framework_content_flows_to_additional_pages() -> None:
    payload = base_payload()
    payload["standards"] = "Complete official standards wording. " * 160

    rendered = render_hqi_document(
        TEMPLATE_PATH,
        payload,
        HqiDocument.INSTRUCTIONAL_FRAMEWORK,
    )
    reader = PdfReader(BytesIO(rendered.pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert rendered.page_count >= 2
    assert rendered.continuation_page_count >= 1
    assert "High Quality Instruction Planning Framework" in text
    assert "Complete official standards wording" in text
    assert "LITERACY STANDARDS" in text
    assert "ACT PREPARATION" in text
    assert "Page 2" in text


def test_long_daily_content_wraps_and_flows_without_shrinking() -> None:
    payload = base_payload()
    payload["clt_mon"] = "Explain, demonstrate, and reflect on the learning target. " * 120

    rendered = render_hqi_document(TEMPLATE_PATH, payload, HqiDocument.WEEK_AT_A_GLANCE)
    reader = PdfReader(BytesIO(rendered.pdf_bytes))
    all_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert rendered.continuation_page_count >= 1
    assert "Monday" in all_text
    assert "Clear Learning Target" in all_text
    assert "Explain, demonstrate" in all_text
    assert "Page 2" in all_text


def test_combined_packet_preserves_document_order_and_page_counts() -> None:
    payload = base_payload()
    payload["standards"] = "Standard detail with supporting instructional context. " * 800
    payload["reflect_1"] = "Reflection detail with evidence and next-step analysis. " * 800

    packet, documents = render_hqi_packet(TEMPLATE_PATH, payload)
    packet_reader = PdfReader(BytesIO(packet))

    assert tuple(item.document for item in documents) == tuple(HqiDocument)
    assert len(packet_reader.pages) == sum(item.page_count for item in documents)
    assert documents[0].continuation_page_count >= 1
    assert documents[2].continuation_page_count >= 1
