from __future__ import annotations

from urllib.parse import urlparse

import httpx

from .standards_catalog_discovery import (
    ACADEMIC_CATALOG_URL,
    CTE_COS_CATALOG_URL,
    CTE_PROGRAM_CATALOG_URL,
    DiscoveredStandardsSource,
    StandardsCatalogDiscoveryError,
    discover_alabama_catalogs,
)

CATALOG_TIMEOUT_SECONDS = 20.0
MAX_CATALOG_BYTES = 4 * 1024 * 1024
_ALLOWED_HOSTS = frozenset({"www.alabamaachieves.org", "alabamaachieves.org"})


def fetch_current_alabama_catalog(
    *,
    timeout_seconds: float = CATALOG_TIMEOUT_SECONDS,
) -> tuple[DiscoveredStandardsSource, ...]:
    urls = (
        ACADEMIC_CATALOG_URL,
        CTE_COS_CATALOG_URL,
        CTE_PROGRAM_CATALOG_URL,
    )
    html_by_url: dict[str, str] = {}
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": "TeacherPlanningPlatform-Standards/1.0"},
        ) as client:
            for url in urls:
                response = client.get(url)
                response.raise_for_status()
                _require_allowed_url(str(response.url))
                if not response.content or len(response.content) > MAX_CATALOG_BYTES:
                    raise StandardsCatalogDiscoveryError(
                        "Authoritative Alabama standards catalog has an invalid size"
                    )
                html_by_url[url] = response.text
    except StandardsCatalogDiscoveryError:
        raise
    except httpx.HTTPError as error:
        raise StandardsCatalogDiscoveryError(
            "Authoritative Alabama standards catalog is unavailable"
        ) from error

    return discover_alabama_catalogs(
        academic_html=html_by_url[ACADEMIC_CATALOG_URL],
        cte_cos_html=html_by_url[CTE_COS_CATALOG_URL],
        cte_program_html=html_by_url[CTE_PROGRAM_CATALOG_URL],
    )


def _require_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise StandardsCatalogDiscoveryError(
            "Authoritative Alabama standards catalog redirected outside the allowlist"
        )
