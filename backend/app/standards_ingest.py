from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from unicodedata import normalize
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import httpx
from pypdf import PdfReader

PARSER_VERSION = "gate-e-standards-v1"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
SOURCE_TIMEOUT_SECONDS = 30.0
_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class StandardsIngestError(RuntimeError):
    """Bounded authoritative-source ingestion failure."""


@dataclass(frozen=True, slots=True)
class FetchedSource:
    requested_url: str
    resolved_url: str
    document_format: str
    content: bytes
    source_sha256: str


@dataclass(frozen=True, slots=True)
class ParsedStandard:
    code: str
    text: str
    parent_code: str | None = None
    strand: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedCourse:
    course_key: str
    display_name: str
    source_course_code: str | None
    grade_band: str | None
    standards: tuple[ParsedStandard, ...]


@dataclass(frozen=True, slots=True)
class ParsedStandardsDocument:
    parser_key: str
    parser_version: str
    normalized_sha256: str
    courses: tuple[ParsedCourse, ...]


@dataclass(frozen=True, slots=True)
class ExtractedDocument:
    lines: tuple[str, ...]
    normalized_sha256: str
    source_content: bytes | None = None
    document_format: str | None = None


def fetch_source(
    url: str,
    document_format: str,
    *,
    timeout_seconds: float = SOURCE_TIMEOUT_SECONDS,
    max_source_bytes: int = MAX_SOURCE_BYTES,
) -> FetchedSource:
    if document_format not in {"pdf", "docx"}:
        raise StandardsIngestError(f"Unsupported standards document format: {document_format}")

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": "TeacherPlanningPlatform-Standards/1.0"},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise StandardsIngestError("Authoritative standards source is unavailable") from error

    content = response.content
    if not content or len(content) > max_source_bytes:
        raise StandardsIngestError("Authoritative standards source has an invalid size")

    if document_format == "pdf" and not content.startswith(b"%PDF"):
        raise StandardsIngestError("Authoritative standards PDF returned unexpected content")
    if document_format == "docx" and not content.startswith(b"PK"):
        raise StandardsIngestError("Authoritative standards DOCX returned unexpected content")

    return FetchedSource(
        requested_url=url,
        resolved_url=str(response.url),
        document_format=document_format,
        content=content,
        source_sha256=sha256(content).hexdigest(),
    )


def extract_document(source: FetchedSource) -> ExtractedDocument:
    if source.document_format == "pdf":
        lines = _extract_pdf_lines(source.content)
    elif source.document_format == "docx":
        lines = _extract_docx_lines(source.content)
    else:
        raise StandardsIngestError(
            f"Unsupported standards document format: {source.document_format}"
        )

    if not lines:
        raise StandardsIngestError("Authoritative standards document contained no readable text")

    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=lines,
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
        source_content=source.content,
        document_format=source.document_format,
    )


def parse_document(parser_key: str, extracted: ExtractedDocument) -> ParsedStandardsDocument:
    parser = _PARSERS.get(parser_key)
    if parser is None:
        raise StandardsIngestError(f"Unsupported standards parser: {parser_key}")

    courses = parser(extracted.lines)
    if not courses or any(not course.standards for course in courses):
        raise StandardsIngestError("Authoritative standards parser produced incomplete course data")

    return ParsedStandardsDocument(
        parser_key=parser_key,
        parser_version=PARSER_VERSION,
        normalized_sha256=extracted.normalized_sha256,
        courses=courses,
    )


def ingest_source(
    url: str,
    document_format: str,
    parser_key: str,
) -> tuple[FetchedSource, ParsedStandardsDocument]:
    source = fetch_source(url, document_format)
    extracted = extract_document(source)
    return source, parse_document(parser_key, extracted)


def _clean_line(value: str) -> str:
    normalized = normalize("NFKC", value).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_pdf_lines(content: bytes) -> tuple[str, ...]:
    try:
        reader = PdfReader(BytesIO(content))
    except Exception as error:  # pypdf exposes multiple parse exception types.
        raise StandardsIngestError("Authoritative standards PDF could not be parsed") from error

    lines: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception as error:
            raise StandardsIngestError(
                "Authoritative standards PDF text extraction failed"
            ) from error
        lines.extend(cleaned for raw in page_text.splitlines() if (cleaned := _clean_line(raw)))
    return tuple(lines)


def _extract_docx_lines(content: bytes) -> tuple[str, ...]:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as error:
        raise StandardsIngestError("Authoritative standards DOCX could not be parsed") from error

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as error:
        raise StandardsIngestError("Authoritative standards DOCX XML is invalid") from error

    paragraph_tag = f"{{{_WORD_NAMESPACE}}}p"
    text_tag = f"{{{_WORD_NAMESPACE}}}t"
    lines: list[str] = []
    for paragraph in root.iter(paragraph_tag):
        text = "".join(node.text or "" for node in paragraph.iter(text_tag))
        cleaned = _clean_line(text)
        if cleaned:
            lines.append(cleaned)
    return tuple(lines)


def _index_of(lines: tuple[str, ...], predicate: Callable[[str], bool], start: int = 0) -> int:
    for index in range(start, len(lines)):
        if predicate(lines[index]):
            return index
    raise StandardsIngestError("Expected authoritative standards section was not found")


def _strip_lane_prefix(line: str) -> str:
    prefixes = (
        "RECEPTION READING ",
        "EXPRESSION WRITING ",
        "RECEPTION LISTENING ",
        "EXPRESSION SPEAKING ",
        "READING ",
        "LISTENING ",
        "WRITING ",
        "SPEAKING ",
    )
    result = line
    for prefix in prefixes:
        if result.startswith(prefix):
            candidate = result[len(prefix) :].strip()
            if re.match(r"^(?:R\d+|\d+)\.", candidate):
                return candidate
    return result


def _is_heading_or_noise(line: str) -> bool:
    if line.startswith("2021 Alabama Course of Study:"):
        return True
    if re.fullmatch(r"Grade \d+", line, flags=re.IGNORECASE):
        return True
    if line in {
        "RECEPTION",
        "EXPRESSION",
        "READING",
        "LISTENING",
        "WRITING",
        "SPEAKING",
        "Students will:",
        "Each content standard completes the stem “ Students will…”",
        "Each content standard completes the stem “Students will…”",
    }:
        return True
    return bool(line.isupper() and len(line) <= 70)


def _numbered_standards(
    lines: tuple[str, ...],
    *,
    code_prefix: str,
    allow_recurring: bool = False,
) -> tuple[ParsedStandard, ...]:
    start_pattern = re.compile(
        r"^(R\d+|\d+)\.\s*(.+)$" if allow_recurring else r"^(\d+)\.\s*(.+)$"
    )
    child_pattern = re.compile(r"^([a-z])\.\s*(.+)$")
    standards: list[ParsedStandard] = []
    current_code: str | None = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_code, current_parts
        if current_code is not None:
            text = " ".join(current_parts).strip()
            if text:
                standards.append(ParsedStandard(code=f"{code_prefix}{current_code}", text=text))
        current_code = None
        current_parts = []

    for raw_line in lines:
        line = _strip_lane_prefix(raw_line)
        match = start_pattern.match(line)
        if match:
            flush()
            current_code = match.group(1)
            current_parts = [match.group(2)]
            continue

        if current_code is None:
            continue
        if _is_heading_or_noise(line):
            continue

        child = child_pattern.match(line)
        if child:
            current_parts.append(f"{child.group(1)}. {child.group(2)}")
        elif not re.fullmatch(r"\d+(?:\.\d+)?", line):
            current_parts.append(line)

    flush()
    return tuple(standards)


def _parse_alabama_ela_2021(lines: tuple[str, ...]) -> tuple[ParsedCourse, ...]:
    grade_start = _index_of(lines, lambda line: line == "GRADE 10")
    grade_end = _index_of(lines, lambda line: line == "GRADE 11", grade_start + 1)
    grade_lines = lines[grade_start:grade_end]

    recurring_start = _index_of(
        grade_lines,
        lambda line: line == "RECURRING STANDARDS FOR GRADES 9-12",
    )
    content_start = _index_of(
        grade_lines,
        lambda line: line == "GRADE 10 CONTENT STANDARDS",
        recurring_start + 1,
    )

    recurring = _numbered_standards(
        grade_lines[recurring_start + 1 : content_start],
        code_prefix="ELA10.",
        allow_recurring=True,
    )
    content = _numbered_standards(
        grade_lines[content_start + 1 :],
        code_prefix="ELA10.",
    )

    if len(recurring) < 7 or len(content) < 20:
        raise StandardsIngestError("Grade 10 ELA standards structure changed unexpectedly")

    return (
        ParsedCourse(
            course_key="english_10",
            display_name="English 10",
            source_course_code="GRADE 10",
            grade_band="10",
            standards=recurring + content,
        ),
    )


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "course"


def _nearest_uppercase_title(lines: tuple[str, ...], marker_index: int) -> str | None:
    candidates: list[str] = []
    for index in range(marker_index - 1, max(-1, marker_index - 8), -1):
        line = lines[index]
        if line.startswith("2021 Alabama Course of Study:"):
            continue
        if line in {"CONTENT STANDARDS", "FOUNDATIONAL STANDARDS"}:
            continue
        if line.isupper() and 2 <= len(line) <= 100:
            candidates.append(line)
            continue
        if candidates:
            break
    if not candidates:
        return None
    return " ".join(reversed(candidates))


def _find_previous_foundational(lines: tuple[str, ...], marker_index: int) -> int | None:
    for index in range(marker_index - 1, max(-1, marker_index - 80), -1):
        current = lines[index].lower()
        following = lines[index + 1].lower() if index + 1 < len(lines) else ""
        if "foundational standards" in current:
            return index
        if current == "foundational" and following == "standards":
            return index
    return None


def _find_next_foundational(lines: tuple[str, ...], start: int) -> int:
    for index in range(start, len(lines)):
        current = lines[index].lower()
        following = lines[index + 1].lower() if index + 1 < len(lines) else ""
        if "foundational standards" in current:
            return index
        if current == "foundational" and following == "standards":
            return index
    return len(lines)


def _grade_band_before(lines: tuple[str, ...], marker_index: int) -> str | None:
    for index in range(marker_index - 1, max(-1, marker_index - 60), -1):
        line = lines[index]
        match = re.search(r"Grade Levels?\s*(.*)$", line, flags=re.IGNORECASE)
        if match:
            inline = match.group(1).strip()
            if inline:
                return inline
            if index + 1 < marker_index:
                candidate = lines[index + 1]
                if re.fullmatch(r"\d+(?:-\d+)?", candidate):
                    return candidate
    return None


def _parse_alabama_bma_2021(lines: tuple[str, ...]) -> tuple[ParsedCourse, ...]:
    markers = [index for index, line in enumerate(lines) if line == "CONTENT STANDARDS"]
    courses: list[ParsedCourse] = []
    seen_keys: set[str] = set()

    for marker in markers:
        title = _nearest_uppercase_title(lines, marker)
        if not title or title in {"MIDDLE SCHOOL COURSES", "HIGH SCHOOL COURSES"}:
            continue

        content_end = _find_next_foundational(lines, marker + 1)
        content = _numbered_standards(
            lines[marker + 1 : content_end],
            code_prefix="",
        )
        if not content:
            continue

        foundational_start = _find_previous_foundational(lines, marker)
        foundational: tuple[ParsedStandard, ...] = ()
        if foundational_start is not None:
            raw_foundational = _numbered_standards(
                lines[foundational_start + 1 : marker],
                code_prefix="F",
            )
            foundational = tuple(
                ParsedStandard(code=standard.code, text=standard.text)
                for standard in raw_foundational[:6]
            )

        course_key = _slug(title)
        if course_key in seen_keys:
            continue
        seen_keys.add(course_key)
        courses.append(
            ParsedCourse(
                course_key=course_key,
                display_name=title.title(),
                source_course_code=None,
                grade_band=_grade_band_before(lines, marker),
                standards=foundational + content,
            )
        )

    high_school_courses = tuple(
        course
        for course in courses
        if course.grade_band is None
        or any(character in course.grade_band for character in ("9", "10", "11", "12"))
    )
    if len(high_school_courses) < 3:
        raise StandardsIngestError("Business standards course structure changed unexpectedly")
    return high_school_courses


def _parse_army_jrotc_v12(lines: tuple[str, ...]) -> tuple[ParsedCourse, ...]:
    lesson_pattern = re.compile(r"^(U([1-4])C\d+L\d+):\s*(.*)$")
    grouped: dict[int, list[ParsedStandard]] = {level: [] for level in range(1, 5)}
    current_level: int | None = None
    current_code: str | None = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_level, current_code, current_parts
        if current_level is not None and current_code is not None:
            text = " ".join(part for part in current_parts if part).strip()
            if text:
                grouped[current_level].append(ParsedStandard(code=current_code, text=text))
        current_level = None
        current_code = None
        current_parts = []

    for line in lines:
        match = lesson_pattern.match(line)
        if match:
            flush()
            current_level = int(match.group(2))
            current_code = match.group(1)
            current_parts = [match.group(3)] if match.group(3) else []
            continue

        if current_code is None:
            continue
        if line.startswith("Unit ") and "Leadership Education" in line:
            flush()
            continue
        if line.startswith("Total Lessons:") or line == "Back to TOC":
            flush()
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?", line):
            continue
        current_parts.append(line.lstrip("• "))

    flush()

    courses: list[ParsedCourse] = []
    for level in range(1, 5):
        standards = tuple(grouped[level])
        if len(standards) < 5:
            raise StandardsIngestError(f"Army JROTC LET {level} structure changed unexpectedly")
        courses.append(
            ParsedCourse(
                course_key=f"army_jrotc_let_{level}",
                display_name=f"Army JROTC LET {level}",
                source_course_code=f"LET {level}",
                grade_band="9-12",
                standards=standards,
            )
        )
    return tuple(courses)


_PARSERS: dict[str, Callable[[tuple[str, ...]], tuple[ParsedCourse, ...]]] = {
    "alabama_ela_2021": _parse_alabama_ela_2021,
    "alabama_bma_2021": _parse_alabama_bma_2021,
    "army_jrotc_v12": _parse_army_jrotc_v12,
}
