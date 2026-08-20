from __future__ import annotations

import re
from dataclasses import dataclass

from .standards_ingest import ExtractedDocument, StandardsIngestError

PROFICIENCY_PARSER_VERSION = "gate-e-alabama-ela-proficiency-6-12-v4"

_GRADE_BY_PARSER_KEY = {
    f"alabama_ela_proficiency_grade_{grade}": str(grade)
    for grade in range(6, 13)
}
# ALSDE's live PDFs use "Standard 1: ..." while an earlier export used
# "Standard: 1. ...". Support both documented source layouts without relaxing
# the grade or core-level validation below.
_STANDARD = re.compile(
    r"^Standard(?:\s+(\d+)\s*:\s*|:\s*(\d+)\.\s*)(.*)$",
    flags=re.IGNORECASE,
)
_GRADE = re.compile(
    r"^Grade:?\s*(6|7|8|9|10|11|12)(?:st|nd|rd|th)?$",
    flags=re.IGNORECASE,
)
_SCORE = re.compile(
    r"^(?:Score\s*)?(4\.0|3\.5|3\.0|2\.5|2\.0|1\.5|1\.0|0\.5|0\.0)"
    r"(?:\s+(.*))?$",
    flags=re.IGNORECASE,
)
_META = {
    "literacy_type": re.compile(r"^Literacy Type:\s*(.*)$", flags=re.IGNORECASE),
    "focus_area": re.compile(r"^Focus Area:\s*(.*)$", flags=re.IGNORECASE),
    "category": re.compile(r"^Category:\s*(.*)$", flags=re.IGNORECASE),
}
_STANDARD_TEXT_BOUNDARIES = frozenset(
    {
        "sample",
        "activities & resources",
        "sample activities",
        "sample activities & resources",
    }
)
_INLINE_STANDARD_TEXT_BOUNDARY = re.compile(
    r"\s+(?:sample\s+)?activities\s*&\s*resources\s*$",
    flags=re.IGNORECASE,
)
_INVISIBLE_TEXT = re.compile(r"[\u200b\u200c\u200d\ufeff]")


@dataclass(frozen=True, slots=True)
class ParsedProficiencyScale:
    grade_band: str
    standard_code: str
    standard_text: str
    literacy_type: str | None
    focus_area: str | None
    category: str | None
    levels: dict[str, str]


@dataclass(frozen=True, slots=True)
class ParsedProficiencyDocument:
    parser_key: str
    parser_version: str
    normalized_sha256: str
    grade_band: str
    scales: tuple[ParsedProficiencyScale, ...]


def parse_alabama_ela_proficiency(
    parser_key: str,
    extracted: ExtractedDocument,
) -> ParsedProficiencyDocument:
    grade_band = _GRADE_BY_PARSER_KEY.get(parser_key)
    if grade_band is None:
        raise StandardsIngestError(f"Unsupported proficiency-scale parser: {parser_key}")

    lines = _coalesce_score_lines(extracted.lines)
    observed_grades = {
        match.group(1)
        for line in lines
        if (match := _GRADE.match(line)) is not None
    }
    if observed_grades and observed_grades != {grade_band}:
        raise StandardsIngestError(
            f"Alabama ELA proficiency source expected Grade {grade_band} but found "
            f"{', '.join(sorted(observed_grades))}"
        )

    starts = [index for index, line in enumerate(lines) if _STANDARD.match(line)]
    if not starts:
        raise StandardsIngestError(
            f"Alabama ELA Grade {grade_band} proficiency source contained no standards"
        )

    scales: list[ParsedProficiencyScale] = []
    seen_codes: set[str] = set()
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        block = lines[start:end]
        match = _STANDARD.match(block[0])
        if match is None:
            continue
        code = match.group(1) or match.group(2)
        if code is None:
            continue
        if code in seen_codes:
            raise StandardsIngestError(
                f"Alabama ELA Grade {grade_band} proficiency standard {code} is duplicated"
            )
        seen_codes.add(code)

        standard_text = _standard_text(block, match.group(3))
        if not standard_text:
            raise StandardsIngestError(
                f"Alabama ELA Grade {grade_band} proficiency standard {code} has no text"
            )
        levels = _level_text(block)
        if not all(level in levels for level in ("4.0", "3.0", "2.0")):
            raise StandardsIngestError(
                f"Alabama ELA Grade {grade_band} proficiency standard {code} is missing "
                "one or more core performance levels"
            )

        metadata = _metadata_before(lines, start)
        scales.append(
            ParsedProficiencyScale(
                grade_band=grade_band,
                standard_code=code,
                standard_text=standard_text,
                literacy_type=metadata.get("literacy_type"),
                focus_area=metadata.get("focus_area"),
                category=metadata.get("category"),
                levels=levels,
            )
        )

    if len(scales) < 5:
        raise StandardsIngestError(
            f"Alabama ELA Grade {grade_band} proficiency source produced too few scales"
        )

    return ParsedProficiencyDocument(
        parser_key=parser_key,
        parser_version=PROFICIENCY_PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        grade_band=grade_band,
        scales=tuple(scales),
    )


def _coalesce_score_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.casefold() == "score" and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if re.fullmatch(
                r"(?:4\.0|3\.5|3\.0|2\.5|2\.0|1\.5|1\.0|0\.5|0\.0)",
                next_line,
            ):
                result.append(f"Score {next_line}")
                index += 2
                continue
        result.append(line)
        index += 1
    return tuple(result)


def _standard_text(block: tuple[str, ...], first: str) -> str:
    parts: list[str] = []
    candidates = (first, *block[1:])
    for index, line in enumerate(candidates):
        if index > 0 and _score_marker(line) is not None:
            break
        stripped = _clean_boundary_text(line.strip())
        if stripped.casefold() in _STANDARD_TEXT_BOUNDARIES:
            break
        stripped, boundary_found = _trim_inline_standard_text_boundary(stripped)
        if _is_header_noise(stripped):
            if boundary_found:
                break
            continue
        if any(pattern.match(stripped) for pattern in _META.values()):
            if boundary_found:
                break
            continue
        if stripped:
            parts.append(stripped)
        if boundary_found:
            break
    return _trim_standard_text_boundary_suffix(" ".join(parts).strip())


def _clean_boundary_text(value: str) -> str:
    return _INVISIBLE_TEXT.sub("", value)


def _trim_inline_standard_text_boundary(value: str) -> tuple[str, bool]:
    cleaned = _clean_boundary_text(value)
    match = _INLINE_STANDARD_TEXT_BOUNDARY.search(cleaned)
    if match is None:
        return cleaned, False
    return cleaned[: match.start()].strip(), True


def _trim_standard_text_boundary_suffix(value: str) -> str:
    cleaned = _clean_boundary_text(value)
    match = _INLINE_STANDARD_TEXT_BOUNDARY.search(cleaned)
    if match is None:
        return cleaned.strip()
    return cleaned[: match.start()].strip()


def _level_text(block: tuple[str, ...]) -> dict[str, str]:
    levels: dict[str, str] = {}
    current_score: str | None = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_score, current_parts
        if current_score is not None:
            text = " ".join(part for part in current_parts if part).strip()
            if text:
                levels[current_score] = text
        current_score = None
        current_parts = []

    for line in block:
        marker = _score_marker(line)
        if marker is not None:
            score, trailing = marker
            flush()
            current_score = score
            if trailing:
                current_parts.append(trailing)
            continue
        if current_score is None or _is_header_noise(line):
            continue
        if _GRADE.match(line) or any(pattern.match(line) for pattern in _META.values()):
            continue
        current_parts.append(line.strip())
    flush()
    return levels


def _score_marker(line: str) -> tuple[str, str | None] | None:
    match = _SCORE.match(line.strip())
    if match is None:
        return None
    trailing = match.group(2).strip() if match.group(2) and match.group(2).strip() else None
    return match.group(1), trailing


def _metadata_before(lines: tuple[str, ...], start: int) -> dict[str, str]:
    metadata: dict[str, str] = {}
    lower = max(0, start - 12)
    for line in lines[lower:start]:
        for key, pattern in _META.items():
            match = pattern.match(line)
            if match and match.group(1).strip():
                metadata[key] = match.group(1).strip()
    return metadata


def _is_header_noise(line: str) -> bool:
    normalized = line.strip().casefold()
    if not normalized:
        return True
    if normalized in {
        "alabama course of study: english language arts",
        "proficiency scales",
        "sample activities",
    }:
        return True
    if normalized.startswith("alabama course of study: english language arts"):
        return True
    return bool(re.fullmatch(r"\d{1,3}", normalized))
