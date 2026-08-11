from __future__ import annotations

import re
from dataclasses import dataclass

from .standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
    StandardsIngestError,
)

_AAS_CODE_PATTERN = (
    r"(?:ELA21|ELA|M|SCI|SS)(?:\.(?!AAS\b)[A-Za-z0-9]+)*\.AAS\.[A-Za-z0-9.]+"
)
_GENERAL_CODE_PATTERN = (
    r"(?:ELA21|ELA|SCI|SS)(?:\.(?!AAS\b)[A-Za-z0-9]+)+\s*[-–]\s*"
)
_ELA_GENERAL_CODE_PATTERN = r"(?:K|[1-9]|1[0-2])\.\d+[a-z]?\s+"
_AAS_STANDARD = re.compile(
    rf"^(?P<code>{_AAS_CODE_PATTERN})\s*(?:[-–]\s*)?(?P<text>.*)$",
    flags=re.IGNORECASE,
)
_GENERAL_PREFIX = re.compile(
    rf"^(?:{_GENERAL_CODE_PATTERN}|{_ELA_GENERAL_CODE_PATTERN}|\d+\.\s+)",
    flags=re.IGNORECASE,
)
_INLINE_CODE = re.compile(
    rf"(?={_AAS_CODE_PATTERN}\s*(?:[-–]\s*)?)",
    flags=re.IGNORECASE,
)
_INLINE_GENERAL = re.compile(
    rf"(?=(?:(?<![A-Za-z0-9.]){_GENERAL_CODE_PATTERN}|"
    rf"(?<![A-Za-z0-9.]){_ELA_GENERAL_CODE_PATTERN}|"
    rf"(?:^|(?<=[.!?)]))\d+\.\s+[A-Z]))",
    flags=re.IGNORECASE,
)
_PAGE_SUFFIX = re.compile(r"(?<=[.!?)])\d{1,3}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_AAS_MISSING_DOT = re.compile(
    r"\b(?P<prefix>ELA(?:21)?\.AAS)(?=(?:K|[1-9]|1[0-2])\.)",
    flags=re.IGNORECASE,
)
_MATH_LAYOUT_CODE = re.compile(
    r"M\s*\.\s*(?:(?P<domain>G|A)\s*\.\s*)?AAS\s*\.\s*"
    r"(?P<grade>K|[1-9]|1[0-2])\s*\.\s*(?P<number>\d+)(?P<suffix>[a-z]?)",
    flags=re.IGNORECASE,
)
_MATH_CANONICAL_CODE = re.compile(
    r"^M(?:\.(?:G|A))?\.AAS\.(?P<grade>K|[1-9]|1[0-2])\.\d+[a-z]?$",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _CourseSpec:
    course_key: str
    display_name: str
    grade_band: str
    headings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _SubjectSpec:
    parser_key: str
    parser_version: str
    code_prefixes: tuple[str, ...]
    courses: tuple[_CourseSpec, ...]


_ELA = _SubjectSpec(
    parser_key="alabama_aas_ela_2021",
    parser_version="gate-e-alabama-aas-ela-2021-v2",
    code_prefixes=("ELA21.", "ELA."),
    courses=tuple(
        _CourseSpec(
            course_key="kindergarten" if grade == 0 else f"grade_{grade}",
            display_name="Kindergarten" if grade == 0 else f"Grade {grade}",
            grade_band="K" if grade == 0 else str(grade),
            headings=(
                "kindergarten",
                "kindergarten ela",
                "kindergarten english language arts",
            )
            if grade == 0
            else (
                f"grade {grade}",
                f"grade {grade} ela",
                f"grade {grade} english language arts",
            ),
        )
        for grade in range(13)
    ),
)


def _math_display_name(grade: int) -> str:
    if grade == 0:
        return "Kindergarten"
    if grade in {9, 10}:
        return f"Grade {grade} Geometry with Data Analysis"
    if grade in {11, 12}:
        return f"Grade {grade} Algebra with Probability"
    return f"Grade {grade}"


_MATH = _SubjectSpec(
    parser_key="alabama_aas_math_2019",
    parser_version="gate-e-alabama-aas-math-2019-v2",
    code_prefixes=("M.",),
    courses=tuple(
        _CourseSpec(
            course_key="kindergarten" if grade == 0 else f"grade_{grade}",
            display_name=_math_display_name(grade),
            grade_band="K" if grade == 0 else str(grade),
            headings=(
                "kindergarten",
                "kindergarten mathematics",
            )
            if grade == 0
            else (
                f"grade {grade}",
                f"grade {grade} mathematics",
                f"grade {grade} geometry with data analysis",
                f"grade {grade}- geometry with data analysis",
                f"grade {grade} algebra with probability",
                f"grade {grade}- algebra with probability",
            ),
        )
        for grade in range(13)
    ),
)

_SCIENCE = _SubjectSpec(
    parser_key="alabama_aas_science_2017",
    parser_version="gate-e-alabama-aas-science-2017-v1",
    code_prefixes=("SCI.",),
    courses=(
        _CourseSpec("kindergarten", "Kindergarten", "K", ("kindergarten science",)),
        *tuple(
            _CourseSpec(
                f"grade_{grade}",
                f"Grade {grade}",
                str(grade),
                (f"grade {grade} science",),
            )
            for grade in range(1, 9)
        ),
        _CourseSpec(
            "grade_9",
            "Grade 9 Physical Science",
            "9",
            ("grade 9 physical science",),
        ),
        _CourseSpec("grade_10", "Grade 10 Biology", "10", ("grade 10 biology",)),
        _CourseSpec(
            "grade_11",
            "Grade 11 Earth and Space Science",
            "11",
            ("grade 11 earth and space science",),
        ),
        _CourseSpec(
            "grade_12",
            "Grade 12 Environmental Science",
            "12",
            ("grade 12 environmental science",),
        ),
    ),
)

_SOCIAL_STUDIES = _SubjectSpec(
    parser_key="alabama_aas_social_studies_2017",
    parser_version="gate-e-alabama-aas-social-studies-2017-v1",
    code_prefixes=("SS.",),
    courses=(
        _CourseSpec("kindergarten", "Kindergarten", "K", ("kindergarten social studies",)),
        *tuple(
            _CourseSpec(
                f"grade_{grade}",
                f"Grade {grade}",
                str(grade),
                (f"grade {grade} social studies",),
            )
            for grade in range(1, 12)
        ),
        _CourseSpec(
            "grade_12_united_states_government",
            "Grade 12 United States Government",
            "12",
            ("grade 12 united states government",),
        ),
        _CourseSpec(
            "grade_12_economics",
            "Grade 12 Economics",
            "12",
            ("grade 12 economics",),
        ),
    ),
)


def parse_alabama_aas_ela_2021(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    return _parse_aas(extracted, _ELA)


def parse_alabama_aas_math_2019(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    if extracted.document_format == "pdf" and extracted.source_content is not None:
        from .standards_alabama_aas_math_spatial import (
            parse_alabama_aas_math_2019_spatial,
        )

        return parse_alabama_aas_math_2019_spatial(extracted)

    parsed = _parse_aas(extracted, _MATH)
    _validate_math_document(parsed)
    return parsed


def parse_alabama_aas_science_2017(extracted: ExtractedDocument) -> ParsedStandardsDocument:
    return _parse_aas(extracted, _SCIENCE)


def parse_alabama_aas_social_studies_2017(
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    return _parse_aas(extracted, _SOCIAL_STUDIES)


def _math_course_on_page(raw_lines: list[str]) -> _CourseSpec | None:
    for raw_line in raw_lines:
        line = _clean_text(raw_line).casefold()
        if not line:
            continue
        for course in reversed(_MATH.courses):
            for heading in sorted(course.headings, key=len, reverse=True):
                pattern = rf"(?<!\w){re.escape(heading.casefold())}(?!\w)"
                if re.search(pattern, line):
                    return course
    return None


def _canonical_math_code(match: re.Match[str]) -> str:
    domain = match.group("domain")
    grade = match.group("grade").upper()
    number = match.group("number")
    suffix = match.group("suffix").lower()
    if domain:
        return f"M.{domain.upper()}.AAS.{grade}.{number}{suffix}"
    return f"M.AAS.{grade}.{number}{suffix}"


def _is_math_layout_noise(line: str) -> bool:
    normalized = line.casefold().rstrip(":")
    if normalized in {
        "2019 aas standard",
        "2019 math cos standard 2019 aas standard",
        "cluster 2019 math cos standard 2019 aas standard",
        "mathematics alternate achievement standards",
    }:
        return True
    return bool(re.fullmatch(r"\d{1,3}", line))


def _validate_math_document(parsed: ParsedStandardsDocument) -> None:
    for course in parsed.courses:
        seen: set[str] = set()
        expected_grade = course.grade_band.upper() if course.grade_band else None
        for standard in course.standards:
            match = _MATH_CANONICAL_CODE.fullmatch(standard.code)
            if match is None:
                raise StandardsIngestError(
                    "Alabama alternate mathematics parser produced an incomplete standard code"
                )
            if expected_grade is not None and match.group("grade").upper() != expected_grade:
                raise StandardsIngestError(
                    "Alabama alternate mathematics standard was assigned to the wrong grade"
                )
            if standard.code in seen:
                raise StandardsIngestError(
                    "Alabama alternate mathematics parser produced a duplicate standard code"
                )
            seen.add(standard.code)
            if not standard.text.strip() or standard.text.rstrip().endswith("$"):
                raise StandardsIngestError(
                    "Alabama alternate mathematics parser produced truncated standard text"
                )


def _parse_aas(
    extracted: ExtractedDocument,
    spec: _SubjectSpec,
) -> ParsedStandardsDocument:
    heading_lookup = {
        heading.casefold(): course
        for course in spec.courses
        for heading in course.headings
    }
    standards_by_course: dict[str, list[ParsedStandard]] = {
        course.course_key: [] for course in spec.courses
    }
    current_course: _CourseSpec | None = None
    current_code: str | None = None
    current_parts: list[str] = []

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

    for raw_line in extracted.lines:
        for fragment in _fragments(raw_line):
            line = _clean_text(fragment)
            if not line:
                continue

            course = heading_lookup.get(line.casefold())
            if course is not None:
                flush()
                current_course = course
                continue

            aas = _AAS_STANDARD.match(line)
            if aas and _matches_subject(aas.group("code"), spec):
                flush()
                if current_course is None:
                    continue
                current_code = aas.group("code")
                initial = aas.group("text").strip()
                current_parts = [initial] if initial else []
                continue

            if _GENERAL_PREFIX.match(line):
                flush()
                continue

            if _is_structure_line(line):
                flush()
                continue

            if current_code is not None:
                current_parts.append(line)

    flush()

    courses: list[ParsedCourse] = []
    for course in spec.courses:
        standards = tuple(standards_by_course[course.course_key])
        if len(standards) < 3:
            raise StandardsIngestError(
                f"Alabama alternate standards parser found incomplete {course.display_name} data "
                f"for {spec.parser_key}"
            )
        courses.append(
            ParsedCourse(
                course_key=course.course_key,
                display_name=course.display_name,
                source_course_code=None,
                grade_band=course.grade_band,
                standards=standards,
            )
        )

    return ParsedStandardsDocument(
        parser_key=spec.parser_key,
        parser_version=spec.parser_version,
        normalized_sha256=extracted.normalized_sha256,
        courses=tuple(courses),
    )


def _matches_subject(code: str, spec: _SubjectSpec) -> bool:
    normalized = code.upper()
    return any(normalized.startswith(prefix.upper()) for prefix in spec.code_prefixes)


def _fragments(line: str) -> tuple[str, ...]:
    normalized_line = _AAS_MISSING_DOT.sub(r"\g<prefix>.", line)
    starts = {0, len(normalized_line)}
    starts.update(match.start() for match in _INLINE_CODE.finditer(normalized_line))
    starts.update(match.start() for match in _INLINE_GENERAL.finditer(normalized_line))
    boundaries = sorted(starts)
    return tuple(
        normalized_line[boundaries[index] : boundaries[index + 1]].strip()
        for index in range(len(boundaries) - 1)
        if normalized_line[boundaries[index] : boundaries[index + 1]].strip()
    )


def _clean_text(value: str) -> str:
    cleaned = _CONTROL.sub("", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return _PAGE_SUFFIX.sub("", cleaned).strip()


def _is_structure_line(line: str) -> bool:
    normalized = line.casefold().rstrip(":")
    if normalized in {
        "alabama alternate achievement standards",
        "english language arts alternate achievement standards",
        "mathematics alternate achievement standards",
        "science alternate achievement standards",
        "social studies alternate achievement standards",
        "general education standards alabama alternate achievement standards",
        "cluster 2019 math cos standard 2019 aas standard",
        "table of contents",
        "overview",
        "acknowledgments",
        "acknowledgements",
    }:
        return True
    if line.startswith("Copyright ©") or line.startswith("Published by "):
        return True
    if re.fullmatch(r"\d{1,3}", line):
        return True
    return (
        len(line) <= 80
        and not re.search(r"[.!?;,]$", line)
        and (line.isupper() or line.istitle())
    )
