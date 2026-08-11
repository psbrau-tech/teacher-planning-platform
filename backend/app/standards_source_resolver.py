from __future__ import annotations

from urllib.parse import urlparse

from .standards_sources import (
    ResolvedStandardsSource,
    StandardsSourceResolutionError,
    resolve_authoritative_document,
)

_ALABAMA_HOSTS = frozenset({"www.alabamaachieves.org", "alabamaachieves.org"})


def resolve_governed_source_document(
    *,
    resolver_key: str,
    landing_url: str,
    document_url: str,
    source_title: str,
    source_edition: str,
) -> ResolvedStandardsSource:
    if resolver_key != "catalog_discovered_direct":
        return resolve_authoritative_document(resolver_key, landing_url)

    _require_alabama_document(document_url)
    _require_alabama_landing(landing_url)
    return ResolvedStandardsSource(
        landing_url=landing_url,
        document_url=document_url,
        anchor_text=source_title,
        observed_version=source_edition or None,
    )


def _require_alabama_document(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALABAMA_HOSTS:
        raise StandardsSourceResolutionError(
            "Catalog-discovered authoritative standards document is outside the Alabama allowlist"
        )
    if not parsed.path.lower().endswith((".pdf", ".docx")):
        raise StandardsSourceResolutionError(
            "Catalog-discovered authoritative standards document has an unsupported format"
        )


def _require_alabama_landing(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALABAMA_HOSTS:
        raise StandardsSourceResolutionError(
            "Catalog-discovered standards landing page is outside the Alabama allowlist"
        )
