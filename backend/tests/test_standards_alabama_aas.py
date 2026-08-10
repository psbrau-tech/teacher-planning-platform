from hashlib import sha256

from app.standards_alabama_aas import (
    parse_alabama_aas_ela_2021,
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


def test_ela_aas_parser_materializes_k_12_by_grade() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = (
            "Kindergarten English Language Arts"
            if grade == 0
            else f"Grade {grade} English Language Arts"
        )
        lines.append(heading)
        for number in range(1, 4):
            lines.extend(
                [
                    f"ELA21.{token}.{number}- General standard {number}.",
                    f"ELA21.AAS.{token}.{number}- Alternate ELA standard {number}.",
                ]
            )

    parsed = parse_alabama_aas_ela_2021(_document(lines))

    assert len(parsed.courses) == 13
    assert parsed.courses[0].standards[0].code == "ELA21.AAS.K.1"
    assert parsed.courses[-1].standards[-1].code == "ELA21.AAS.12.3"


def test_math_aas_parser_ignores_general_rows_and_page_boundary_join() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.extend(
            [
                heading,
                "1. General math standard.",
                f"M.AAS.{token}.1 Alternate math standard one.",
                "Measurement",
                "2. General math standard.",
                f"M.AAS.{token}.2 Alternate math standard two.",
                f"M.AAS.{token}.3 Alternate math standard three.4. Next general row.",
            ]
        )

    parsed = parse_alabama_aas_math_2019(_document(lines))
    grade_two = next(course for course in parsed.courses if course.course_key == "grade_2")

    assert [standard.code for standard in grade_two.standards] == [
        "M.AAS.2.1",
        "M.AAS.2.2",
        "M.AAS.2.3",
    ]
    assert grade_two.standards[-1].text == "Alternate math standard three."


def test_science_aas_parser_keeps_high_school_courses_separate() -> None:
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
        for number in range(1, 4):
            lines.extend(
                [
                    f"SCI.{token}.{number}- General science standard.",
                    f"SCI.AAS.{token}.{number}- Alternate science standard {number}.",
                ]
            )

    parsed = parse_alabama_aas_science_2017(_document(lines))

    assert len(parsed.courses) == 13
    assert parsed.courses[-4].display_name == "Grade 9 Physical Science"
    assert parsed.courses[-1].display_name == "Grade 12 Environmental Science"


def test_social_studies_aas_parser_preserves_courses_and_duplicate_source_codes() -> None:
    course_rows = [
        ("Kindergarten Social Studies", "K", "K", "K"),
        *[
            (f"Grade {grade} Social Studies", str(grade), str(grade), str(grade))
            for grade in range(1, 12)
        ],
        ("Grade 12 United States Government", "USG.12", "USG.AAS.12", "12"),
        ("Grade 12 Economics", "E.12", "E.AAS.12", "12"),
    ]
    lines: list[str] = []
    for heading, general_token, aas_token, grade in course_rows:
        lines.append(heading)
        for number in range(1, 4):
            general_code = f"SS.{general_token}.{number}"
            aas_code = (
                f"SS.AAS.{aas_token}.{number}"
                if ".AAS." not in aas_token
                else f"SS.{aas_token}.{number}"
            )
            lines.extend(
                [
                    f"{general_code}- General social studies standard.",
                    f"{aas_code}- Alternate social studies standard {number}.",
                ]
            )
        if grade == "7":
            lines.extend(
                [
                    "SS.AAS.7.11- First official statement using the duplicate source code.",
                    "SS.AAS.7.11- Second official statement using the duplicate source code.",
                ]
            )

    parsed = parse_alabama_aas_social_studies_2017(_document(lines))

    assert len(parsed.courses) == 14
    assert parsed.courses[-2].course_key == "grade_12_united_states_government"
    assert parsed.courses[-2].standards[0].code == "SS.USG.AAS.12.1"
    assert parsed.courses[-1].course_key == "grade_12_economics"
    assert parsed.courses[-1].standards[0].code == "SS.E.AAS.12.1"

    grade_seven = next(course for course in parsed.courses if course.course_key == "grade_7")
    duplicate_rows = [standard for standard in grade_seven.standards if standard.code == "SS.AAS.7.11"]
    assert [standard.text for standard in duplicate_rows] == [
        "First official statement using the duplicate source code.",
        "Second official statement using the duplicate source code.",
    ]
