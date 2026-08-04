from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Mapping

from pypdf import PdfReader, PdfWriter

from .pdf_fields import validate_hqi_payload


def fill_hqi_pdf(
    template_path: Path,
    values: Mapping[str, str],
    *,
    flatten: bool = False,
) -> bytes:
    unknown_fields = validate_hqi_payload(dict(values))
    if unknown_fields:
        raise ValueError(f"Unknown HQI fields: {', '.join(unknown_fields)}")
    if not template_path.exists():
        raise FileNotFoundError(f"HQI template not found: {template_path}")

    reader = PdfReader(str(template_path))
    source_fields = reader.get_fields() or {}
    missing_in_template = sorted(set(values) - set(source_fields))
    if missing_in_template:
        raise ValueError(
            "Template does not contain expected fields: " + ", ".join(missing_in_template)
        )

    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.set_need_appearances_writer(True)

    for page in writer.pages:
        writer.update_page_form_field_values(page, dict(values), auto_regenerate=True)

    if flatten:
        for page in writer.pages:
            annotations = page.get("/Annots")
            if annotations:
                page["/Annots"] = []

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
