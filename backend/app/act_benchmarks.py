from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import httpx

from .act_reference import ActReferenceError, _normalize_html
from .supabase_rest import SupabaseRestClient, SupabaseRestError

JsonRecord = dict[str, Any]
_PARSER_VERSION = "act-public-benchmarks-html-v1"
ACT_BENCHMARK_SOURCE_KEY = "act_readiness_benchmarks"
ACT_BENCHMARK_URL = (
    "https://www.act.org/content/act/en/college-and-career-readiness/benchmarks.html"
)


@dataclass(frozen=True, slots=True)
class ActBenchmark:
    domain: str
    benchmark_score: int
    related_course_area: str


@dataclass(frozen=True, slots=True)
class ParsedActBenchmarks:
    source_sha256: str
    normalized_sha256: str
    parser_version: str
    benchmarks: tuple[ActBenchmark, ...]


_BENCHMARK_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "English",
        "English Composition I",
        re.compile(r"English\s+English Composition I\s+(\d{1,2})", re.I),
    ),
    (
        "Mathematics",
        "College Algebra",
        re.compile(r"Mathematics\s+College Algebra\s+(\d{1,2})", re.I),
    ),
    (
        "Reading",
        "American History, Other History, Psychology, Sociology, Political Science, Economics",
        re.compile(
            r"Reading\s+American History, Other History, Psychology, Sociology, "
            r"Political Science, Economics\s+(\d{1,2})",
            re.I,
        ),
    ),
    (
        "Science",
        "Biology",
        re.compile(r"Science\s+Biology\s+(\d{1,2})", re.I),
    ),
    (
        "STEM",
        "Calculus, Chemistry, Biology, Physics, Engineering",
        re.compile(
            r"STEM\s+Calculus, Chemistry, Biology, Physics, Engineering\s+(\d{1,2})",
            re.I,
        ),
    ),
    (
        "ELA",
        "English Composition I, American History, Other History, Psychology, Sociology, Political Science, Economics",
        re.compile(
            r"ELA\s+English Composition I, American History, Other History, Psychology, "
            r"Sociology, Political Science, Economics\s+(\d{1,2})",
            re.I,
        ),
    ),
)


def parse_act_benchmarks_html(raw_html: str) -> ParsedActBenchmarks:
    normalized = _normalize_html(raw_html)
    flat = re.sub(r"\s+", " ", normalized)
    benchmarks: list[ActBenchmark] = []
    for domain, course_area, pattern in _BENCHMARK_PATTERNS:
        matches = pattern.findall(flat)
        if len(matches) != 1:
            raise ActReferenceError(
                f"Expected one current ACT benchmark row for {domain}; found {len(matches)}"
            )
        score = int(matches[0])
        if not 1 <= score <= 36:
            raise ActReferenceError(f"ACT benchmark score is outside 1-36 for {domain}")
        benchmarks.append(ActBenchmark(domain, score, course_area))
    return ParsedActBenchmarks(
        source_sha256=hashlib.sha256(raw_html.encode("utf-8")).hexdigest(),
        normalized_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        parser_version=_PARSER_VERSION,
        benchmarks=tuple(benchmarks),
    )


def fetch_and_parse_act_benchmarks() -> ParsedActBenchmarks:
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(
                ACT_BENCHMARK_URL,
                headers={"User-Agent": "TPP-Standards-Maintenance/1.0"},
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise ActReferenceError("ACT public readiness benchmark source is unavailable") from error
    return parse_act_benchmarks_html(response.text)


def stage_act_benchmarks(
    client: SupabaseRestClient,
    parsed: ParsedActBenchmarks,
) -> UUID:
    try:
        sources = cast(
            list[JsonRecord],
            client.request(
                "GET",
                "act_reference_sources",
                params={
                    "source_key": f"eq.{ACT_BENCHMARK_SOURCE_KEY}",
                    "select": "id",
                    "limit": "2",
                },
            ),
        )
        if len(sources) != 1:
            raise ActReferenceError("ACT readiness benchmark source registry is missing or ambiguous")
        source_id = UUID(str(sources[0]["id"]))
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
            raise ActReferenceError("ACT readiness benchmark snapshot save returned invalid data")
        snapshot_id = UUID(str(snapshots[0]["id"]))
        payload = [
            {
                "snapshot_id": str(snapshot_id),
                "source_id": str(source_id),
                "domain": benchmark.domain,
                "benchmark_score": benchmark.benchmark_score,
                "related_course_area": benchmark.related_course_area,
                "metadata": {"public_first_party": True},
            }
            for benchmark in parsed.benchmarks
        ]
        client.request(
            "POST",
            "act_readiness_benchmarks",
            payload=payload,
            prefer="return=minimal",
        )
        return snapshot_id
    except SupabaseRestError as error:
        raise ActReferenceError("ACT readiness benchmark material could not be staged") from error
