from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx

LANDING_TIMEOUT_SECONDS = 20.0
MAX_LANDING_BYTES = 16 * 1024 * 1024
_ALLOWED_HOSTS = frozenset(
    {
        "www.alabamaachieves.org",
        "alabamaachieves.org",
        "english-language-arts.alsde.edu",
        "drive.google.com",
        "docs.google.com",
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
        self._tokens: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered == "a":
            href = next((value for key, value in attrs if key.lower() == "href"), None)
            if href:
                self._href = href
                self._parts = []
            return
        if lowered in {"iframe", "embed"}:
            src = next((value for key, value in attrs if key.lower() == "src"), None)
            if src:
                self._tokens.append(("embed", src))

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()
        if cleaned:
            self._tokens.append(("text", cleaned))
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        text = re.sub(r"\s+", " ", " ".join(self._parts)).strip()
        self.anchors.append(_Anchor(href=self._href, text=text))
        self._href = None
        self._parts = []

    def document_candidates(self) -> tuple[_Anchor, ...]:
        candidates = list(self.anchors)
        for index, (kind, value) in enumerate(self._tokens):
            if kind != "embed":
                continue
            context_parts: list[str] = []
            for direction in (-1, 1):
                cursor = index + direction
                collected = 0
                while 0 <= cursor < len(self._tokens) and collected < 5:
                    token_kind, token_value = self._tokens[cursor]
                    if token_kind == "text":
                        context_parts.append(token_value)
                        collected += 1
                    cursor += direction
            context = re.sub(r"\s+", " ", " ".join(context_parts)).strip()
            candidates.append(_Anchor(href=value, text=context))
        return tuple(candidates)


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
        ) as client, client.stream("GET", landing_url) as response:
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

    return resolve_from_anchors(
        resolver_key,
        resolved_landing,
        parser.document_candidates(),
    )


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
    return _downloadable_document_url(document_url), anchor.text


def _downloadable_document_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname not in {"drive.google.com", "docs.google.com"}:
        return url

    match = re.search(r"/(?:file|document)/d/([^/]+)", parsed.path)
    if match:
        return f"https://drive.google.com/uc?{urlencode({'export': 'download', 'id': match.group(1)})}"

    query = parse_qs(parsed.query)
    file_ids = query.get("id")
    if file_ids:
        return f"https://drive.google.com/uc?{urlencode({'export': 'download', 'id': file_ids[0]})}"

    return urlunparse(parsed)


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


def _grade_labels(grade: int) -> tuple[str, ...]:
    words = {
        6: "sixth",
        7: "seventh",
        8: "eighth",
        9: "ninth",
        10: "tenth",
        11: "eleventh",
        12: "twelfth",
    }
    suffix = "th"
    return (f"{grade}{suffix} grade", f"grade {grade}", f"{words[grade]} grade")


def _is_drive_document(anchor: _Anchor) -> bool:
    absolute = urlparse(anchor.href)
    return absolute.hostname in {"drive.google.com", "docs.google.com"}


def _resolve_alabama_ela_proficiency_grade(
    grade: int,
    landing_url: str,
    anchors: tuple[_Anchor, ...],
) -> ResolvedStandardsSource:
    labels = _grade_labels(grade)
    matches: list[_Anchor] = []
    for anchor in anchors:
        text = anchor.text.casefold()
        if not _is_drive_document(anchor):
            continue
        if "proficiency" not in text:
            continue
        if any(label in text for label in labels):
            matches.append(anchor)

    if not matches:
        raise StandardsSourceResolutionError(
            f"Current Alabama Grade {grade} ELA proficiency-scale document was not found"
        )

    selected = max(
        matches,
        key=lambda anchor: (
            _extract_year(f"{anchor.text} {anchor.href}"),
            "rev" in anchor.text.casefold(),
            len(anchor.text),
        ),
    )
    document_url, text = _absolute_document(landing_url, selected)
    return ResolvedStandardsSource(
        landing_url=landing_url,
        document_url=document_url,
        anchor_text=text or f"Grade {grade} ELA Proficiency Scales",
        observed_version=_observed_year(selected, document_url),
    )


def _proficiency_resolver(grade: int):
    def resolver(
        landing_url: str,
        anchors: tuple[_Anchor, ...],
    ) -> ResolvedStandardsSource:
        return _resolve_alabama_ela_proficiency_grade(grade, landing_url, anchors)

    return resolver


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
for _grade in range(6, 13):
    _RESOLVERS[f"alabama_ela_proficiency_grade_{_grade}_current"] = _proficiency_resolver(
        _grade
    )
