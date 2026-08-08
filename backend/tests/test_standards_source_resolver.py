import pytest

from app.standards_source_resolver import resolve_governed_source_document
from app.standards_sources import StandardsSourceResolutionError


def test_catalog_discovered_source_uses_exact_approved_alabama_document() -> None:
    resolved = resolve_governed_source_document(
        resolver_key="catalog_discovered_direct",
        landing_url="https://www.alabamaachieves.org/acad-stand/",
        document_url="https://www.alabamaachieves.org/files/science.pdf",
        source_title="2023 Alabama Course of Study: Science",
        source_edition="2023",
    )

    assert resolved.document_url == "https://www.alabamaachieves.org/files/science.pdf"
    assert resolved.landing_url == "https://www.alabamaachieves.org/acad-stand/"
    assert resolved.anchor_text == "2023 Alabama Course of Study: Science"
    assert resolved.observed_version == "2023"


def test_catalog_discovered_source_rejects_non_alabama_document() -> None:
    with pytest.raises(StandardsSourceResolutionError, match="outside the Alabama allowlist"):
        resolve_governed_source_document(
            resolver_key="catalog_discovered_direct",
            landing_url="https://www.alabamaachieves.org/acad-stand/",
            document_url="https://example.com/science.pdf",
            source_title="Science",
            source_edition="2023",
        )


def test_catalog_discovered_source_rejects_unsupported_document_format() -> None:
    with pytest.raises(StandardsSourceResolutionError, match="unsupported format"):
        resolve_governed_source_document(
            resolver_key="catalog_discovered_direct",
            landing_url="https://www.alabamaachieves.org/acad-stand/",
            document_url="https://www.alabamaachieves.org/files/science.html",
            source_title="Science",
            source_edition="2023",
        )
