from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject, NumberObject, TextStringObject

from .pdf_fields import validate_field_lengths, validate_hqi_payload

PdfFieldValue = str | list[str] | tuple[str, str, float]
MULTILINE_FLAG = 1 << 12


def _configure_text_field(field_reference: Any) -> None:
    """Remove restrictive text limits and enable multiline, auto-sized text."""
    field = field_reference.get_object()
    if field.get("/FT") == "/Tx":
        flags = int(field.get("/Ff", 0)) | MULTILINE_FLAG
        field[NameObject("/Ff")] = NumberObject(flags)
        if "/MaxLen" in field:
            del field["/MaxLen"]
        field[NameObject("/DA")] = TextStringObject("/Helv 0 Tf 0 g")

    for child in field.get("/Kids", []):
        _configure_text_field(child)


def _configure_writer_form(writer: PdfWriter) -> None:
    root = writer.root_object
    acroform_reference = root.get("/AcroForm")
    if acroform_reference is None:
        raise ValueError("HQI template does not contain an AcroForm")

    acroform = acroform_reference.get_object()
    acroform[NameObject("/NeedAppearances")] = NumberObject(1)
    for field_reference in acroform.get("/Fields", []):
        _configure_text_field(field_reference)


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
        raise ValueError(f"HQI field content exceeds application limits: {detail}")

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
    _configure_writer_form(writer)
    form_values: dict[str, PdfFieldValue] = dict(payload)

    for page in writer.pages:
        writer.update_page_form_field_values(page, form_values, auto_regenerate=True)

    if flatten:
        for page in writer.pages:
            if page.get("/Annots"):
                page["/Annots"] = ArrayObject()

    output = BytesIO()
    writer.write(output)
    return output.getvalue()
