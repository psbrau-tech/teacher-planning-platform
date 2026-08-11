from io import BytesIO

from reportlab.pdfgen import canvas

from app.standards_alabama_aas_math_spatial import parse_alabama_aas_math_2019_spatial
from app.standards_ingest import ExtractedDocument


def _three_column_math_pdf() -> ExtractedDocument:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for grade in range(13):
        token = "K" if grade == 0 else str(grade)
        if grade == 0:
            heading = "Kindergarten Mathematics"
        elif grade in {9, 10}:
            heading = f"Grade {grade} Geometry with Data Analysis"
        elif grade in {11, 12}:
            heading = f"Grade {grade} Algebra with Probability"
        else:
            heading = f"Grade {grade} Mathematics"

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(72, 760, heading)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(72, 720, "Cluster")
        pdf.drawString(220, 720, "2019 Math COS Standard")
        pdf.drawString(430, 720, "2019 AAS Standard")
        pdf.setFont("Helvetica", 9)

        for offset, number in enumerate((1, 4, 7)):
            y = 680 - (offset * 120)
            pdf.drawString(72, y, f"Cluster narrative {number}.")
            pdf.drawString(220, y, f"{number}. General standard that must not leak.")
            if grade in {9, 10}:
                code = f"M.G.AAS.{token}.{number}"
            elif grade in {11, 12}:
                code = f"M.A.AAS.{token}.{number}"
            else:
                code = f"M.AAS.{token}.{number}"
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawString(430, y, code)
            pdf.setFont("Helvetica", 9)
            pdf.drawString(430, y - 14, f"Alternate standard {number}.")
        pdf.showPage()

    pdf.save()
    return ExtractedDocument(
        lines=("plain extraction not used",),
        normalized_sha256="a" * 64,
        source_content=buffer.getvalue(),
        document_format="pdf",
    )


def test_spatial_parser_keeps_only_right_hand_aas_lane() -> None:
    parsed = parse_alabama_aas_math_2019_spatial(_three_column_math_pdf())

    assert parsed.parser_version == "gate-e-alabama-aas-math-2019-v2"
    assert len(parsed.courses) == 13
    kindergarten = parsed.courses[0]
    grade_nine = parsed.courses[9]
    grade_eleven = parsed.courses[11]
    assert [standard.code for standard in kindergarten.standards] == [
        "M.AAS.K.1",
        "M.AAS.K.4",
        "M.AAS.K.7",
    ]
    assert [standard.code for standard in grade_nine.standards] == [
        "M.G.AAS.9.1",
        "M.G.AAS.9.4",
        "M.G.AAS.9.7",
    ]
    assert [standard.code for standard in grade_eleven.standards] == [
        "M.A.AAS.11.1",
        "M.A.AAS.11.4",
        "M.A.AAS.11.7",
    ]
    assert all(
        "General standard" not in standard.text and "Cluster narrative" not in standard.text
        for course in parsed.courses
        for standard in course.standards
    )
