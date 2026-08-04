from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.pdf_generator import MULTILINE_FLAG, fill_hqi_pdf

TEMPLATE_PATH = Path(__file__).parents[1] / "assets" / "anniston_hqi_lesson_plan.fillable.pdf"


def test_editable_pdf_preserves_values_and_expands_text_fields() -> None:
    generated = fill_hqi_pdf(
        TEMPLATE_PATH,
        {
            "teacher": "Synthetic Teacher",
            "course": "LET 1",
            "standards": "Army JROTC leadership competency " * 20,
            "clt_mon": "Explain the purpose, structure, and expectations of Army JROTC. " * 8,
        },
    )

    reader = PdfReader(BytesIO(generated))
    fields = reader.get_fields() or {}
    assert fields["teacher"]["/V"] == "Synthetic Teacher"
    assert fields["course"]["/V"] == "LET 1"
    assert len(fields["clt_mon"]["/V"]) > 400
    assert int(fields["clt_mon"].get("/Ff", 0)) & MULTILINE_FLAG
    assert "/MaxLen" not in fields["clt_mon"]
    assert " 0 Tf" in str(fields["clt_mon"]["/DA"])


def test_flattened_pdf_removes_page_annotations() -> None:
    generated = fill_hqi_pdf(
        TEMPLATE_PATH,
        {"teacher": "Synthetic Teacher", "course": "LET 1"},
        flatten=True,
    )

    reader = PdfReader(BytesIO(generated))
    assert all(not page.get("/Annots") for page in reader.pages)
