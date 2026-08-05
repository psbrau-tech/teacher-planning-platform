from __future__ import annotations

from pathlib import Path

from .document_sections import HqiDocument
from .hqi_document_renderer import RenderedHqiDocument, render_hqi_document, render_hqi_packet
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
    """Legacy three-page packet path retained for compatibility during the pilot."""
    return fill_hqi_pdf(template_path, payload, flatten=flatten)


def generate_anniston_hqi_document(
    payload: dict[str, str],
    document: HqiDocument,
    *,
    flatten: bool = False,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> RenderedHqiDocument:
    return render_hqi_document(template_path, payload, document, flatten=flatten)


def generate_anniston_hqi_packet(
    payload: dict[str, str],
    *,
    flatten: bool = False,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> tuple[bytes, tuple[RenderedHqiDocument, ...]]:
    return render_hqi_packet(template_path, payload, flatten=flatten)
