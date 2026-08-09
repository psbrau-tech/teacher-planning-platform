from __future__ import annotations

import json
from pathlib import Path

from .document_sections import HqiDocument
from .hqi_document_renderer import RenderedHqiDocument, render_hqi_document, render_hqi_packet
from .pdf_fields import ALL_HQI_FIELDS
from .pdf_generator import fill_hqi_pdf

DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "assets" / "anniston_hqi_lesson_plan.fillable.pdf"
)

_DAY_ALIASES = (
    ("monday", "mon"),
    ("tuesday", "tue"),
    ("wednesday", "wed"),
    ("thursday", "thu"),
    ("friday", "fri"),
)


def normalize_planning_payload(payload: dict[str, str]) -> dict[str, str]:
    """Translate the teacher working-plan shape into the approved HQI document contract.

    Exact HQI fields always win. The aliases below let the integrated weekly planner feed the
    principal-approved PDFs without inventing content for fields the teacher did not address.
    """
    normalized = {
        field: value
        for field, value in payload.items()
        if field in ALL_HQI_FIELDS and isinstance(value, str)
    }

    def set_if_blank(field: str, value: str | None) -> None:
        if isinstance(value, str) and (field not in normalized or not normalized.get(field)):
            normalized[field] = value

    set_if_blank("teacher", payload.get("teacher"))
    set_if_blank("course", payload.get("course"))
    set_if_blank("grade", payload.get("grade"))
    set_if_blank("week_of", payload.get("week_of"))
    set_if_blank("unit_topic", payload.get("unit_topic"))
    set_if_blank("standards", payload.get("standards"))
    set_if_blank("literacy_standards", payload.get("literacy_standards"))
    set_if_blank("act_preparation", payload.get("act_preparation"))
    set_if_blank("know", payload.get("know"))
    set_if_blank("understand", payload.get("understand"))
    set_if_blank("do", payload.get("do"))
    set_if_blank("plds", payload.get("learning_targets"))
    set_if_blank("formative", payload.get("assessments"))
    set_if_blank("performance_task", payload.get("activities"))
    set_if_blank("resources", payload.get("resources"))

    learning_targets = payload.get("learning_targets", "")
    assessments = payload.get("assessments", "")
    for day_name, suffix in _DAY_ALIASES:
        daily_text = payload.get(day_name, "")
        if not daily_text.strip():
            continue
        set_if_blank(f"clt_{suffix}", learning_targets)
        set_if_blank(f"rrt_{suffix}", daily_text)
        set_if_blank(f"cfu_{suffix}", assessments)
        set_if_blank(f"esl_{suffix}", assessments)

    reflection_value = payload.get("reflection")
    if isinstance(reflection_value, str) and reflection_value:
        try:
            reflection = json.loads(reflection_value)
        except json.JSONDecodeError:
            reflection = None
        if isinstance(reflection, dict):
            for index in range(1, 13):
                key = f"reflect_{index}"
                value = reflection.get(key)
                if isinstance(value, str):
                    set_if_blank(key, value)

    return normalized


def generate_anniston_hqi(
    payload: dict[str, str],
    *,
    flatten: bool = False,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> bytes:
    """Legacy packet path retained for compatibility during the pilot."""
    return fill_hqi_pdf(template_path, normalize_planning_payload(payload), flatten=flatten)


def generate_anniston_hqi_document(
    payload: dict[str, str],
    document: HqiDocument,
    *,
    flatten: bool = False,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> RenderedHqiDocument:
    return render_hqi_document(
        template_path,
        normalize_planning_payload(payload),
        document,
        flatten=flatten,
    )


def generate_anniston_hqi_packet(
    payload: dict[str, str],
    *,
    flatten: bool = False,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> tuple[bytes, tuple[RenderedHqiDocument, ...]]:
    return render_hqi_packet(
        template_path,
        normalize_planning_payload(payload),
        flatten=flatten,
    )
