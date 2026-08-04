from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Mapping

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject

from .pdf_fields import validate_field_lengths, validate_hqi_payload


def fill_hqi_pdf(
    template_path: Path,
    values: Mapping[str, str],
    *,
    flatten: bool = False,
) -> bytes:
    payload = dict(values)
    unknown_fields = validate_hqi_payload(payload)
    if unknown_fields:
        raise ValueError(f"Unknown HQI fields: {', '.join(unknown_fields)}")

    length_errors = validate_field_lengths(payload)
    if length_errors:
        detail = ", ".join(
            f"{error.field}={error.character_count}/{error.character_limit}"
            for error in length_errors
        )
        raise ValueError(f"HQI field content exceeds safe layout limits: {detail}")

    if not template_path.exists():
        raise FileNotFoundError(f"HQI template not found: {template_path}")

    reader = PdfReader(str(template_path))
    source_fields = reader.get_fields() or {}
    missing_in_template = sorted(set(payload) - set(source_fields))
    if missing_in_template:
        raise ValueError(
            "Template does not contain expected fields: " + ", ".join(missing_in_template)
        )

    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.set_need_appearances_writer(True)

    for page in writer.pages:
        writer.update_page_form_field_values(page, payload, auto_regenerate=True)

    if flatten:
        for page in writer.pages:
            if page.get("/Annots"):
                page["/Annots"] = ArrayObject()

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
