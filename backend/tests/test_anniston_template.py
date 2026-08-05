from pathlib import Path

from pypdf import PdfReader

from app.pdf_fields import TEMPLATE_HQI_FIELDS

TEMPLATE_PATH = Path(__file__).parents[1] / "assets" / "anniston_hqi_lesson_plan.fillable.pdf"


def test_approved_anniston_template_is_present_and_three_pages() -> None:
    assert TEMPLATE_PATH.exists()
    reader = PdfReader(str(TEMPLATE_PATH))
    assert len(reader.pages) == 3


def test_approved_anniston_template_field_contract() -> None:
    reader = PdfReader(str(TEMPLATE_PATH))
    actual_fields = tuple((reader.get_fields() or {}).keys())
    assert set(actual_fields) == set(TEMPLATE_HQI_FIELDS), (
        "The approved PDF field names do not match the legacy template contract. "
        f"Expected={sorted(TEMPLATE_HQI_FIELDS)} Actual={sorted(actual_fields)}"
    )
