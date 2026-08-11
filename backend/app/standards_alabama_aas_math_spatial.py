from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pypdf import PdfReader

from .standards_alabama_aas import (
    _MATH,
    _MATH_LAYOUT_CODE,
    _canonical_math_code,
    _clean_text,
    _is_math_layout_noise,
    _math_course_on_page,
    _validate_math_document,
)
from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

_FRAGMENT_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True, slots=True)
class _PositionedText:
    x: float
    y: float
    text: str


def _clean_positioned_fragment(value: str) -> str:
    """Normalize a positioned PDF fragment without stripping code suffix digits."""

    cleaned = _FRAGMENT_CONTROL.sub("", value)
    return re.sub(r"\s+", " ", cleaned).strip()


def _positioned_text_visitor(
    fragments: list[_PositionedText],
) -> Callable[[str, list[float], list[float], dict[str, Any] | None, float], None]:
    def visitor(
        text: str,
        user_matrix: list[float],
        text_matrix: list[float],
        font_dictionary: dict[str, Any] | None,
        font_size: float,
    ) -> None:
        del font_dictionary, font_size
        text_x = float(text_matrix[4])
        text_y = float(text_matrix[5])
        user_x = float(user_matrix[4])
        user_y = float(user_matrix[5])
        x = text_x if abs(text_x) > 0.01 else user_x
        y = text_y if abs(text_y) > 0.01 else user_y
        for raw_line in text.splitlines():
            cleaned = _clean_positioned_fragment(raw_line)
            if cleaned:
                fragments.append(_PositionedText(x=x, y=y, text=cleaned))

    return visitor


def _right_lane_lines(
    fragments: list[_PositionedText],
    *,
    lane_min_x: float,
) -> tuple[str, ...]:
    """Reconstruct visual lines from right-lane fragments, top to bottom."""

    grouped: dict[float, list[_PositionedText]] = {}
    for fragment in fragments:
        if fragment.x < lane_min_x:
            continue
        y_key = round(fragment.y, 1)
        grouped.setdefault(y_key, []).append(fragment)

    lines: list[str] = []
    for y_key in sorted(grouped, reverse=True):
        row = sorted(grouped[y_key], key=lambda fragment: fragment.x)
        line = _clean_positioned_fragment(" ".join(fragment.text for fragment in row))
        if line:
            lines.append(line)
    return tuple(lines)


def parse_alabama_aas_math_2019_spatial(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    """Parse the authoritative Math AAS lane using PDF text coordinates.

    The source is a three-column table. Plain text extraction interleaves cells, and a
    single logical AAS code can be split across multiple PDF text objects. Coordinate-based
    visual-line reconstruction keeps only the right-hand AAS lane and rejoins fragments on
    a shared baseline before identifiers are parsed.
    """

    if extracted.document_format != "pdf" or extracted.source_content is None:
        raise StandardsIngestError(
            "Alabama alternate mathematics parser requires the authoritative PDF bytes"
        )

    try:
        reader = PdfReader(BytesIO(extracted.source_content))
    except Exception as error:
        raise StandardsIngestError(
            "Alabama alternate mathematics PDF could not be parsed"
        ) from error

    standards_by_course: dict[str, list[ParsedStandard]] = {
        course.course_key: [] for course in _MATH.courses
    }
    current_course = None
    current_code: str | None = None
    current_parts: list[str] = []
    prior_aas_x: float | None = None

    def flush() -> None:
        nonlocal current_code, current_parts
        if current_course is not None and current_code is not None:
            text = _clean_text(" ".join(current_parts))
            if text:
                standards_by_course[current_course.course_key].append(
                    ParsedStandard(
                        code=current_code,
                        text=text,
                        strand="Alternate Achievement Standards",
                    )
                )
        current_code = None
        current_parts = []

    for page in reader.pages:
        fragments: list[_PositionedText] = []
        visitor = _positioned_text_visitor(fragments)
        try:
            page_text = page.extract_text(visitor_text=visitor) or ""
        except Exception as error:
            raise StandardsIngestError(
                "Alabama alternate mathematics coordinate extraction failed"
            ) from error

        page_course = _math_course_on_page(page_text.splitlines())
        if page_course is not None and page_course != current_course:
            flush()
            current_course = page_course

        code_xs = [
            fragment.x
            for fragment in fragments
            if _MATH_LAYOUT_CODE.search(fragment.text) is not None
        ]
        header_xs = [
            fragment.x
            for fragment in fragments
            if "2019 AAS Standard" in fragment.text
        ]
        aas_x: float | None
        if code_xs:
            aas_x = min(code_xs)
            prior_aas_x = aas_x
        elif header_xs:
            aas_x = min(header_xs)
            prior_aas_x = aas_x
        else:
            aas_x = prior_aas_x

        page_width = float(page.mediabox.width)
        geometric_lane_x = page_width * 0.64
        lane_min_x = (
            geometric_lane_x
            if aas_x is None
            else min(aas_x - 12.0, geometric_lane_x)
        )

        for lane in _right_lane_lines(fragments, lane_min_x=lane_min_x):
            if _is_math_layout_noise(lane):
                continue

            code_match = _MATH_LAYOUT_CODE.search(lane)
            if code_match is not None:
                flush()
                if current_course is None:
                    continue
                current_code = _canonical_math_code(code_match)
                initial = lane[code_match.end() :].lstrip(" -–")
                current_parts = [initial] if initial else []
                continue

            if current_code is not None:
                current_parts.append(lane)

    flush()

    courses: list[ParsedCourse] = []
    for course in _MATH.courses:
        standards = tuple(standards_by_course[course.course_key])
        if len(standards) < 3:
            raise StandardsIngestError(
                "Alabama alternate mathematics coordinate parser found incomplete "
                f"{course.display_name} data"
            )
        courses.append(
            ParsedCourse(
                course_key=course.course_key,
                display_name=course.display_name,
                source_course_code=course.display_name,
                grade_band=course.grade_band,
                standards=standards,
            )
        )

    parsed = ParsedStandardsDocument(
        parser_key=_MATH.parser_key,
        parser_version=_MATH.parser_version,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )
    _validate_math_document(parsed)
    return parsed
