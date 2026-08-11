from hashlib import sha256
from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from app.standards_alabama_aas import (
    parse_alabama_aas_ela_2021,
    parse_alabama_aas_math_2019,
    parse_alabama_aas_science_2017,
    parse_alabama_aas_social_studies_2017,
)
from app.standards_ingest import ExtractedDocument, StandardsIngestError


def _document(lines: list[str]) -> ExtractedDocument:
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def _math_layout_document() -> ExtractedDocument:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        if grade == 0:
            heading = "Kindergarten Mathematics"
        elif grade in {9, 10}:
            heading = f"Grade {grade}- Geometry with Data Analysis"
        elif grade in {11, 12}:
            heading = f"Grade {grade}- Algebra with Probability"
        else:
            heading = f"Grade {grade} Mathematics"

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(72, 760, heading)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(72, 720, "Cluster")
        pdf.drawString(220, 720, "2019 Math COS Standard")
        pdf.drawString(430, 720, "2019 AAS Standard")
        pdf.setFont("Helvetica", 9)

        for number in range(1, 4):
            y = 680 - ((number - 1) * 110)
            pdf.drawString(72, y, f"Neighboring cluster narrative {number}.")
            pdf.drawString(220, y, f"{number}. General standard text that must not leak.")
            if grade in {9, 10}:
                code = f"M.G.AAS.{token}.{number}"
            elif grade in {11, 12}:
                code = f"M.A.AAS.{token}.{number}"
            else:
                code = f"M.AAS.{token}.{number}"
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(430, y, code)
            pdf.setFont("Helvetica", 9)
            pdf.drawString(430, y - 14, f"Alternate math standard {number}.")
        pdf.showPage()

    pdf.save()
    content = buffer.getvalue()
    return ExtractedDocument(
        lines=("plain extraction intentionally unused for layout parser",),
        normalized_sha256="a" * 64,
        source_content=content,
        document_format="pdf",
    )


def test_ela_aas_parser_materializes_official_k_12_pdf_pattern() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "KINDERGARTEN ELA" if grade == 0 else f"Grade {grade} ELA"
        lines.append(heading)
        for number in range(1, 4):
            lines.append(
                f"{token}.{number} General standard {number}. "
                f"ELA.AAS.{token}.{number} Alternate ELA standard {number}."
            )

    parsed = parse_alabama_aas_ela_2021(_document(lines))

    assert len(parsed.courses) == 13
    assert parsed.parser_version == "gate-e-alabama-aas-ela-2021-v2"
    assert parsed.courses[0].standards[0].code == "ELA.AAS.K.1"
    assert parsed.courses[-1].standards[-1].code == "ELA.AAS.12.3"

    kindergarten = parsed.courses[0]
    assert [standard.text for standard in kindergarten.standards] == [
        "Alternate ELA standard 1.",
        "Alternate ELA standard 2.",
        "Alternate ELA standard 3.",
    ]
    assert all("General standard" not in standard.text for standard in kindergarten.standards)


def test_ela_aas_parser_splits_publisher_token_missing_dot_after_aas() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "KINDERGARTEN ELA" if grade == 0 else f"Grade {grade} ELA"
        lines.append(heading)
        lines.extend(
            [
                f"ELA.AAS.{token}.1 Alternate ELA standard one.",
                f"ELA.AAS.{token}.2 Alternate ELA standard two.",
                f"ELA.AAS.{token}.3 Alternate ELA standard three.",
            ]
        )
        if grade == 1:
            lines.append(
                "ELA.AAS.1.7a Identify a phoneme with its grapheme. "
                "ELA.AAS1.7b Encode concrete CVC spelled words."
            )

    parsed = parse_alabama_aas_ela_2021(_document(lines))
    grade_one = next(course for course in parsed.courses if course.course_key == "grade_1")
    standards = {standard.code: standard.text for standard in grade_one.standards}

    assert standards["ELA.AAS.1.7a"] == "Identify a phoneme with its grapheme."
    assert standards["ELA.AAS.1.7b"] == "Encode concrete CVC spelled words."


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

    assert parsed.parser_version == "gate-e-alabama-aas-math-2019-v2"
    assert [standard.code for standard in grade_two.standards] == [
        "M.AAS.2.1",
        "M.AAS.2.2",
        "M.AAS.2.3",
    ]
    assert grade_two.standards[-1].text == "Alternate math standard three."


def test_math_aas_layout_parser_isolates_authoritative_right_hand_lane() -> None:
    parsed = parse_alabama_aas_math_2019(_math_layout_document())

    assert len(parsed.courses) == 13
    assert parsed.parser_version == "gate-e-alabama-aas-math-2019-v2"
    grade_nine = next(course for course in parsed.courses if course.course_key == "grade_9")
    grade_eleven = next(course for course in parsed.courses if course.course_key == "grade_11")
    assert grade_nine.display_name == "Grade 9 Geometry with Data Analysis"
    assert grade_eleven.display_name == "Grade 11 Algebra with Probability"
    assert [standard.code for standard in grade_nine.standards] == [
        "M.G.AAS.9.1",
        "M.G.AAS.9.2",
        "M.G.AAS.9.3",
    ]
    assert [standard.code for standard in grade_eleven.standards] == [
        "M.A.AAS.11.1",
        "M.A.AAS.11.2",
        "M.A.AAS.11.3",
    ]
    assert all(
        "General standard" not in standard.text and "Neighboring cluster" not in standard.text
        for course in parsed.courses
        for standard in course.standards
    )


def test_math_aas_parser_rejects_incomplete_identifier() -> None:
    lines: list[str] = []
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        heading = "Kindergarten Mathematics" if grade == 0 else f"Grade {grade} Mathematics"
        lines.extend(
            [
                heading,
                f"M.AAS.{token}.1 Alternate one.",
                f"M.AAS.{token}.2 Alternate two.",
                f"M.AAS.{token}.3 Alternate three.",
            ]
        )
    lines[2] = "M.AAS.K. Incomplete code must fail."

    with pytest.raises(StandardsIngestError, match="incomplete"):
        parse_alabama_aas_math_2019(_document(lines))


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
    duplicate_rows = [
        standard for standard in grade_seven.standards if standard.code == "SS.AAS.7.11"
    ]
    assert [standard.text for standard in duplicate_rows] == [
        "First official statement using the duplicate source code.",
        "Second official statement using the duplicate source code.",
    ]
