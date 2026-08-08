from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

LANDING_TIMEOUT_SECONDS = 20.0
MAX_LANDING_BYTES = 16 * 1024 * 1024
_ALLOWED_HOSTS = frozenset(
    {
        "www.alabamaachieves.org",
        "alabamaachieves.org",
        "usarmyjrotc.army.mil",
    }
)


class StandardsSourceResolutionError(RuntimeError):
    """Bounded failure while resolving the publisher's current standards document."""


@dataclass(frozen=True, slots=True)
class ResolvedStandardsSource:
    landing_url: str
    document_url: str
    anchor_text: str
    observed_version: str | None


@dataclass(frozen=True, slots=True)
class _Anchor:
    href: str
    text: str


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[_Anchor] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next((value for key, value in attrs if key.lower() == "href"), None)
        if href:
            self._href = href
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        text = re.sub(r"\s+", " ", " ".join(self._parts)).strip()
        self.anchors.append(_Anchor(href=self._href, text=text))
        self._href = None
        self._parts = []


def resolve_authoritative_document(
    resolver_key: str,
    landing_url: str,
    *,
    timeout_seconds: float = LANDING_TIMEOUT_SECONDS,
) -> ResolvedStandardsSource:
    _require_allowed_url(landing_url)
    content = bytearray()
    resolved_landing = landing_url
    encoding = "utf-8"

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": "TeacherPlanningPlatform-Standards/1.0"},
        ) as client:
            with client.stream("GET", landing_url) as response:
                response.raise_for_status()
                resolved_landing = str(response.url)
                _require_allowed_url(resolved_landing)
                encoding = response.encoding or "utf-8"
                for chunk in response.iter_bytes():
                    if not chunk:
                        continue
                    if len(content) + len(chunk) > MAX_LANDING_BYTES:
                        raise StandardsSourceResolutionError(
                            "Authoritative standards landing page has an invalid size"
                        )
                    content.extend(chunk)
    except httpx.HTTPError as error:
        raise StandardsSourceResolutionError(
            "Authoritative standards landing page is unavailable"
        ) from error

    if not content:
        raise StandardsSourceResolutionError(
            "Authoritative standards landing page has an invalid size"
        )

    parser = _AnchorParser()
    try:
        parser.feed(bytes(content).decode(encoding, errors="replace"))
    except Exception as error:
        raise StandardsSourceResolutionError(
            "Authoritative standards landing page could not be parsed"
        ) from error

    return resolve_from_anchors(resolver_key, resolved_landing, tuple(parser.anchors))


def resolve_from_anchors(
    resolver_key: str,
    landing_url: str,
    anchors: tuple[_Anchor, ...],
) -> ResolvedStandardsSource:
    resolver = _RESOLVERS.get(resolver_key)
    if resolver is None:
        raise StandardsSourceResolutionError(f"Unsupported standards resolver: {resolver_key}")
    return resolver(landing_url, anchors)


def _require_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise StandardsSourceResolutionError("Authoritative standards URL is not allowlisted")


def _absolute_document(landing_url: str, anchor: _Anchor) -> tuple[str, str]:
    document_url = urljoin(landing_url, anchor.href)
    _require_allowed_url(document_url)
    return document_url, anchor.text


def _extract_year(value: str) -> int:
    years = [int(match) for match in re.findall(r"20\d{2}", value)]
    return max(years, default=0)


def _observed_year(anchor: _Anchor, document_url: str) -> str | None:
    anchor_year = _extract_year(anchor.text)
    if anchor_year:
        return str(anchor_year)
    url_year = _extract_year(document_url)
    return str(url_year) if url_year else None


def _resolve_alabama_ela(
    landing_url: str,
    anchors: tuple[_Anchor, ...],
) -> ResolvedStandardsSource:
    matches = [
        anchor
        for anchor in anchors
        if anchor.href.lower().endswith(".pdf")
        and "alabama-course-of-study" in anchor.href.lower()
        and "english-language-arts" in anchor.href.lower()
    ]
    if not matches:
        raise StandardsSourceResolutionError("Current Alabama English standards PDF was not found")
    selected = max(matches, key=lambda anchor: _extract_year(f"{anchor.text} {anchor.href}"))
    document_url, text = _absolute_document(landing_url, selected)
    return ResolvedStandardsSource(
        landing_url=landing_url,
        document_url=document_url,
        anchor_text=text,
        observed_version=_observed_year(selected, document_url),
    )


def _resolve_alabama_bma(
    landing_url: str,
    anchors: tuple[_Anchor, ...],
) -> ResolvedStandardsSource:
    matches: list[_Anchor] = []
    for anchor in anchors:
        href = anchor.href.lower()
        text = anchor.text.lower()
        if not href.endswith(".pdf"):
            continue
        is_business_management = (
            "bma" in href
            or "business management" in href
            or "bma" in text
            or "business management" in text
        )
        is_course_of_study = (
            "course-of-study" in href
            or "bma-cos" in href
            or "course of study" in text
        )
        if is_business_management and is_course_of_study:
            matches.append(anchor)
    if not matches:
        raise StandardsSourceResolutionError("Current Alabama business standards PDF was not found")
    selected = max(matches, key=lambda anchor: _extract_year(f"{anchor.text} {anchor.href}"))
    document_url, text = _absolute_document(landing_url, selected)
    return ResolvedStandardsSource(
        landing_url=landing_url,
        document_url=document_url,
        anchor_text=text,
        observed_version=_observed_year(selected, document_url),
    )


def _army_version(anchor: _Anchor) -> int:
    value = f"{anchor.text} {anchor.href}"
    match = re.search(r"(?:\bv|version\s*)(\d+)\b", value, flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _resolve_army_jrotc(
    landing_url: str,
    anchors: tuple[_Anchor, ...],
) -> ResolvedStandardsSource:
    matches = [
        anchor
        for anchor in anchors
        if anchor.href.lower().endswith(".docx")
        and "jrotc-curriculum-guide" in anchor.href.lower()
    ]
    if not matches:
        raise StandardsSourceResolutionError("Current Army JROTC curriculum guide was not found")
    selected = max(
        matches,
        key=lambda anchor: (_army_version(anchor), _extract_year(anchor.href)),
    )
    document_url, text = _absolute_document(landing_url, selected)
    version = _army_version(selected)
    return ResolvedStandardsSource(
        landing_url=landing_url,
        document_url=document_url,
        anchor_text=text,
        observed_version=f"v{version}" if version else None,
    )


_RESOLVERS = {
    "alabama_ela_current": _resolve_alabama_ela,
    "alabama_bma_current": _resolve_alabama_bma,
    "army_jrotc_current": _resolve_army_jrotc,
}
