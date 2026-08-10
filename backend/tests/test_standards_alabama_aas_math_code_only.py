from hashlib import sha256

from app.standards_alabama_aas_hardened import parse_alabama_aas_math_2019
from app.standards_ingest import ExtractedDocument


def _document(lines: list[str]) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_math_aas_preserves_code_only_pdf_rows_across_k_12() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.append(heading)
        for number in (1, 4, 5):
            lines.extend(
                [
                    f"M.AAS.{token}.{number}",
                    f"Alternate math standard {number} for {token}.",
                ]
            )

    parsed = parse_alabama_aas_math_2019(_document(lines))

    kindergarten = parsed.courses[0]
    assert [standard.code for standard in kindergarten.standards] == [
        "M.AAS.K.1",
        "M.AAS.K.4",
        "M.AAS.K.5",
    ]
    assert [standard.text for standard in kindergarten.standards] == [
        "Alternate math standard 1 for K.",
        "Alternate math standard 4 for K.",
        "Alternate math standard 5 for K.",
    ]

    grade_twelve = parsed.courses[-1]
    assert [standard.code for standard in grade_twelve.standards] == [
        "M.AAS.12.1",
        "M.AAS.12.4",
        "M.AAS.12.5",
    ]
    assert parsed.parser_version == "gate-e-alabama-aas-math-2019-v2"


def test_math_aas_preserves_qualified_code_only_high_school_rows() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.append(heading)
        if grade == 9:
            for number in (1, 2, 4):
                lines.extend(
                    [
                        f"M.G.AAS.9.{number}",
                        f"Geometry alternate standard {number}.",
                    ]
                )
            continue
        for number in (1, 2, 3):
            lines.extend(
                [
                    f"M.AAS.{token}.{number}",
                    f"Alternate math standard {number}.",
                ]
            )

    parsed = parse_alabama_aas_math_2019(_document(lines))
    grade_nine = next(course for course in parsed.courses if course.course_key == "grade_9")

    assert [standard.code for standard in grade_nine.standards] == [
        "M.G.AAS.9.1",
        "M.G.AAS.9.2",
        "M.G.AAS.9.4",
    ]
    assert [standard.text for standard in grade_nine.standards] == [
        "Geometry alternate standard 1.",
        "Geometry alternate standard 2.",
        "Geometry alternate standard 4.",
    ]


def test_math_aas_preserves_identifier_appended_to_general_text_line() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.append(heading)
        if grade == 1:
            lines.extend(
                [
                    "1. General standard wording. M.AAS.1.17",
                    "Alternate standard seventeen wording.",
                    "M.AAS.1.19",
                    "Alternate standard nineteen wording.",
                    "M.AAS.1.20",
                    "Alternate standard twenty wording.",
                ]
            )
            continue
        for number in (1, 2, 3):
            lines.extend(
                [
                    f"M.AAS.{token}.{number}",
                    f"Alternate math standard {number}.",
                ]
            )

    parsed = parse_alabama_aas_math_2019(_document(lines))
    grade_one = next(course for course in parsed.courses if course.course_key == "grade_1")

    assert [standard.code for standard in grade_one.standards] == [
        "M.AAS.1.17",
        "M.AAS.1.19",
        "M.AAS.1.20",
    ]
    assert grade_one.standards[0].text == "Alternate standard seventeen wording."
