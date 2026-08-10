from hashlib import sha256

from app.standards_alabama_aas_hardened import (
    parse_alabama_aas_math_2019,
    parse_alabama_aas_science_2017,
    parse_alabama_aas_social_studies_2017,
)
from app.standards_ingest import ExtractedDocument


def _document(lines: list[str]) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_math_aas_repairs_spaced_final_identifier_segment_from_pdf_extraction() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.append(heading)
        for number in range(1, 4):
            lines.append(
                f"M.AAS.{token}. {number} Alternate math standard {number}."
            )

    parsed = parse_alabama_aas_math_2019(_document(lines))

    kindergarten = parsed.courses[0]
    assert [standard.code for standard in kindergarten.standards] == [
        "M.AAS.K.1",
        "M.AAS.K.2",
        "M.AAS.K.3",
    ]
    assert parsed.parser_version == "gate-e-alabama-aas-math-2019-v2"
    assert all(
        not standard.code.endswith(".")
        for course in parsed.courses
        for standard in course.standards
    )


def test_math_aas_repairs_qualified_high_school_identifier() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.append(heading)
        if grade == 9:
            lines.extend(
                [
                    "M.G.AAS.9. 1 First geometry alternate standard.",
                    "M.G.AAS.9. 2 Second geometry alternate standard.",
                    "M.G.AAS.9. 3 Third geometry alternate standard.",
                ]
            )
        else:
            for number in range(1, 4):
                lines.append(
                    f"M.AAS.{token}. {number} Alternate math standard {number}."
                )

    parsed = parse_alabama_aas_math_2019(_document(lines))
    grade_nine = next(course for course in parsed.courses if course.course_key == "grade_9")

    assert [standard.code for standard in grade_nine.standards] == [
        "M.G.AAS.9.1",
        "M.G.AAS.9.2",
        "M.G.AAS.9.3",
    ]


def test_science_aas_suppresses_only_exact_extraction_duplicates() -> None:
    course_rows = [
        ("Kindergarten Science", "K"),
        *[(f"Grade {grade} Science", str(grade)) for grade in range(1, 9)],
        ("Grade 9 Physical Science", "PS.HS"),
        ("Grade 10 Biology", "BIO.HS"),
        ("Grade 11 Earth and Space Science", "ESS.HS"),
        ("Grade 12 Environmental Science", "ENV.HS"),
    ]
    lines: list[str] = []
    for heading, token in course_rows:
        lines.append(heading)
        rows = [
            f"SCI.AAS.{token}.{number}- Alternate science standard {number}."
            for number in range(1, 4)
        ]
        lines.extend(rows)
        if token == "K":
            lines.append(rows[0])

    parsed = parse_alabama_aas_science_2017(_document(lines))
    kindergarten = parsed.courses[0]

    assert [standard.code for standard in kindergarten.standards] == [
        "SCI.AAS.K.1",
        "SCI.AAS.K.2",
        "SCI.AAS.K.3",
    ]
    assert parsed.parser_version == "gate-e-alabama-aas-science-2017-v2"


def test_social_studies_aas_deduplicates_exact_rows_but_preserves_conflicting_source_code() -> None:
    course_rows = [
        ("Kindergarten Social Studies", "K"),
        *[(f"Grade {grade} Social Studies", str(grade)) for grade in range(1, 12)],
        ("Grade 12 United States Government", "USG.AAS.12"),
        ("Grade 12 Economics", "E.AAS.12"),
    ]
    lines: list[str] = []
    for heading, token in course_rows:
        lines.append(heading)
        for number in range(1, 4):
            code = (
                f"SS.{token}.{number}"
                if ".AAS." in token
                else f"SS.AAS.{token}.{number}"
            )
            lines.append(f"{code}- Alternate social studies standard {number}.")
        if token == "K":
            lines.append("SS.AAS.K.1- Alternate social studies standard 1.")
        if token == "7":
            lines.extend(
                [
                    "SS.AAS.7.11- First authoritative statement using duplicate code.",
                    "SS.AAS.7.11- Second authoritative statement using duplicate code.",
                ]
            )

    parsed = parse_alabama_aas_social_studies_2017(_document(lines))
    kindergarten = parsed.courses[0]
    grade_seven = next(course for course in parsed.courses if course.course_key == "grade_7")

    assert sum(standard.code == "SS.AAS.K.1" for standard in kindergarten.standards) == 1
    duplicate_code_rows = [
        standard for standard in grade_seven.standards if standard.code == "SS.AAS.7.11"
    ]
    assert [standard.text for standard in duplicate_code_rows] == [
        "First authoritative statement using duplicate code.",
        "Second authoritative statement using duplicate code.",
    ]
    assert parsed.parser_version == "gate-e-alabama-aas-social-studies-2017-v2"
