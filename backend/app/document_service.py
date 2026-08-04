from __future__ import annotations

from pathlib import Path

from .pdf_generator import fill_hqi_pdf

DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "anniston_hqi_lesson_plan.fillable.pdf"
)


def generate_anniston_hqi(
    payload: dict[str, str],
    *,
    flatten: bool = False,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> bytes:
    return fill_hqi_pdf(template_path, payload, flatten=flatten)
