from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, cast
from uuid import UUID

import httpx

from .settings import Settings
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]
_PARSER_VERSION = "act-public-html-v1"
_CODE = re.compile(r"\b([A-Z][A-Z&]{1,5})\s+([2-7]\d{2})\.\s*")

ACT_CCR_SOURCES: tuple[tuple[str, str, str], ...] = (
    (
        "act_ccrs_english",
        "English",
        "https://www.act.org/content/act/en/college-and-career-readiness/standards/english-standards.html",
    ),
    (
        "act_ccrs_mathematics",
        "Mathematics",
        "https://www.act.org/content/act/en/college-and-career-readiness/standards/mathematics-standards.html",
    ),
    (
        "act_ccrs_reading",
        "Reading",
        "https://www.act.org/content/act/en/college-and-career-readiness/standards/reading-standards.html",
    ),
    (
        "act_ccrs_science",
        "Science",
        "https://www.act.org/content/act/en/college-and-career-readiness/standards/science-standards.html",
    ),
    (
        "act_ccrs_writing",
        "Writing",
        "https://www.act.org/content/act/en/college-and-career-readiness/standards/writing-standards.html",
    ),
)

_SCORE_RANGES = {
    "default": {2: "13-15", 3: "16-19", 4: "20-23", 5: "24-27", 6: "28-32", 7: "33-36"},
    "Writing": {2: "3-4", 3: "5-6", 4: "7-8", 5: "9-10", 6: "11-12", 7: "11-12"},
}


class ActReferenceError(RuntimeError):
    """Bounded ACT reference ingestion failure."""


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        elif tag in {"p", "div", "td", "th", "li", "h1", "h2", "h3", "h4", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "td", "th", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


@dataclass(frozen=True, slots=True)
class ActReferenceEntry:
    reference_code: str
    domain: str
    category: str
    score_range: str
    exact_text: str
    sequence: int
    source_locator: str


@dataclass(frozen=True, slots=True)
class ParsedActReference:
    source_key: str
    domain: str
    source_sha256: str
    normalized_sha256: str
    parser_version: str
    entries: tuple[ActReferenceEntry, ...]


def _normalize_html(raw: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(raw)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[\t\r ]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def parse_act_ccr_html(*, source_key: str, domain: str, raw_html: str) -> ParsedActReference:
    normalized = _normalize_html(raw_html)
    matches = list(_CODE.finditer(normalized))
    if not matches:
        raise ActReferenceError(f"No ACT CCR standards were found for {domain}")

    entries: list[ActReferenceEntry] = []
    seen_codes: set[str] = set()
    ranges = _SCORE_RANGES.get(domain, _SCORE_RANGES["default"])
    for index, match in enumerate(matches):
        prefix, number_text = match.groups()
        code = f"{prefix} {number_text}"
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        exact_text = normalized[start:end].strip(" \n|\u00a0")
        # Stop before page navigation / Ideas for Progress material after the final standard.
        exact_text = re.split(r"\n(?:Ideas for Progress|Welcome to ACT)\b", exact_text, maxsplit=1)[0].strip()
        if not exact_text:
            raise ActReferenceError(f"ACT reference {code} has no authoritative wording")
        if code in seen_codes:
            raise ActReferenceError(f"Duplicate ACT reference code in {domain}: {code}")
        seen_codes.add(code)
        level = int(number_text[0])
        score_range = ranges.get(level)
        if score_range is None:
            raise ActReferenceError(f"Unsupported ACT score-range level for {code}")
        entries.append(
            ActReferenceEntry(
                reference_code=code,
                domain=domain,
                category=prefix,
                score_range=score_range,
                exact_text=exact_text,
                sequence=len(entries) + 1,
                source_locator=f"{domain} CCR Standards / {code}",
            )
        )

    if len(entries) < 10:
        raise ActReferenceError(f"ACT {domain} parser produced implausibly few entries")
    raw_bytes = raw_html.encode("utf-8")
    normalized_bytes = normalized.encode("utf-8")
    return ParsedActReference(
        source_key=source_key,
        domain=domain,
        source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        normalized_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        parser_version=_PARSER_VERSION,
        entries=tuple(entries),
    )


def fetch_and_parse_act_ccr(source_key: str, domain: str, url: str) -> ParsedActReference:
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "TPP-Standards-Maintenance/1.0"})
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise ActReferenceError(f"ACT public source is unavailable for {domain}") from error
    return parse_act_ccr_html(source_key=source_key, domain=domain, raw_html=response.text)


def service_role_client(settings: Settings) -> SupabaseRestClient:
    if settings.supabase_url is None or not settings.supabase_service_role_key:
        raise ActReferenceError("ACT maintenance requires the Supabase service-role maintenance path")
    return SupabaseRestClient(
        base_url=str(settings.supabase_url).rstrip("/"),
        api_key=settings.supabase_service_role_key,
        access_token=settings.supabase_service_role_key,
        timeout_seconds=30.0,
    )


def stage_act_reference(client: SupabaseRestClient, parsed: ParsedActReference) -> UUID:
    try:
        sources = cast(
            list[JsonRecord],
            client.request(
                "GET",
                "act_reference_sources",
                params={"source_key": f"eq.{parsed.source_key}", "select": "id", "limit": "2"},
            ),
        )
    except (SupabaseRestError, TypeError) as error:
        raise ActReferenceError("ACT source registry lookup failed") from error
    if len(sources) != 1:
        raise ActReferenceError(f"ACT source registry is missing or ambiguous: {parsed.source_key}")
    source_id = UUID(str(sources[0]["id"]))

    try:
        existing = cast(
            list[JsonRecord],
            client.request(
                "GET",
                "act_reference_snapshots",
                params={
                    "source_id": f"eq.{source_id}",
                    "source_sha256": f"eq.{parsed.source_sha256}",
                    "select": "id",
                    "limit": "2",
                },
            ),
        )
        if existing:
            return UUID(str(existing[0]["id"]))
        snapshots = cast(
            list[JsonRecord],
            client.request(
                "POST",
                "act_reference_snapshots",
                payload={
                    "source_id": str(source_id),
                    "source_sha256": parsed.source_sha256,
                    "normalized_sha256": parsed.normalized_sha256,
                    "parser_version": parsed.parser_version,
                    "status": "pending",
                    "provenance": {"publisher": "ACT", "public_first_party": True},
                },
                prefer="return=representation",
            ),
        )
        if len(snapshots) != 1:
            raise ActReferenceError("ACT candidate snapshot save returned invalid data")
        snapshot_id = UUID(str(snapshots[0]["id"]))
        payload = [
            {
                "snapshot_id": str(snapshot_id),
                "source_id": str(source_id),
                "reference_code": entry.reference_code,
                "domain": entry.domain,
                "category": entry.category,
                "score_range": entry.score_range,
                "exact_text": entry.exact_text,
                "sequence": entry.sequence,
                "source_locator": entry.source_locator,
                "metadata": {"public_first_party": True},
            }
            for entry in parsed.entries
        ]
        client.request("POST", "act_reference_entries", payload=payload, prefer="return=minimal")
        return snapshot_id
    except SupabaseRestError as error:
        raise ActReferenceError("ACT candidate reference material could not be staged") from error


def load_approved_act_entries(client: SupabaseRestClient, reference_codes: list[str]) -> list[JsonRecord]:
    unique = sorted({code.strip() for code in reference_codes if code.strip()})
    if not unique:
        return []
    if len(unique) > 8:
        raise ActReferenceError("No more than 8 ACT references may be recommended at once")
    quoted = ",".join(f'"{code}"' for code in unique)
    try:
        rows = cast(
            list[JsonRecord],
            client.request(
                "GET",
                "act_reference_entries",
                params={
                    "reference_code": f"in.({quoted})",
                    "select": "reference_code,domain,category,score_range,exact_text,source_id,snapshot_id",
                    "order": "domain.asc,reference_code.asc",
                },
            ),
        )
    except SupabaseRestError as error:
        raise ActReferenceError("Approved ACT reference lookup failed") from error
    found = {str(row.get("reference_code")) for row in rows}
    missing = [code for code in unique if code not in found]
    if missing:
        raise ActReferenceError(f"AI returned unknown or unapproved ACT references: {', '.join(missing)}")
    return rows
