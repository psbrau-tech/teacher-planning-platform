from hashlib import sha256

from app.standards_alabama_ela import parse_alabama_ela_2021
from app.standards_ingest import ExtractedDocument


def _document() -> ExtractedDocument:
    lines: list[str] = []
    for grade in range(13):
        label = "KINDERGARTEN" if grade == 0 else f"GRADE {grade}"
        marker = (
            "KINDERGARTEN CONTENT STANDARDS"
            if grade == 0
            else f"GRADE {grade} CONTENT STANDARDS"
        )
        lines.extend([label, "RECURRING STANDARDS FOR TEST GRADE BAND", "Students will:"])
        if grade == 2:
            lines.extend(
                [
                    "R1. Grade 2 recurring standard one.",
                    "R2. Grade 2 recurring standard two.",
                    "R3. Grade 2 recurring standard three.",
                    marker,
                    "Each content standard completes the stem “Students will…”",
                    "R4. Grade 2 recurring standard four after the content heading.",
                    "R5. Grade 2 recurring standard five after the content heading.",
                ]
            )
        elif grade >= 9:
            lines.extend(
                [
                    "Reception",
                    "R1. Read a workplace document.",
                    "R2. Read and comprehend literary texts.",
                    "R3. Utilize active listening skills in formal and informal conversations, following predetermined norms.",
                    "Expression",
                    "R4. Use digital and electronic tools appropriately, safely, and ethically.",
                    "R5. Utilize a writing process.",
                    marker,
                ]
            )
        else:
            lines.extend(
                [
                    *[f"R{number}. Recurring standard {number}." for number in range(1, 6)],
                    marker,
                ]
            )
        lines.extend(
            [f"{number}. Content standard {number}." for number in range(1, 7)]
        )
    normalized = "\n".join(lines)
    return ExtractedDocument(
        lines=tuple(lines),
        normalized_sha256=sha256(normalized.encode("utf-8")).hexdigest(),
    )


def test_ela_parser_collects_grade_2_recurring_rows_across_content_heading() -> None:
    parsed = parse_alabama_ela_2021(_document())
    grade_two = next(course for course in parsed.courses if course.course_key == "grade_2")

    recurring = [
        standard for standard in grade_two.standards if standard.strand == "Recurring Standards"
    ]
    content = [
        standard for standard in grade_two.standards if standard.strand == "Content Standards"
    ]

    assert [standard.code for standard in recurring] == ["R1", "R2", "R3", "R4", "R5"]
    assert recurring[-1].text == "Grade 2 recurring standard five after the content heading."
    assert [standard.code for standard in content] == ["1", "2", "3", "4", "5", "6"]
    assert all(not standard.code.startswith("R") for standard in content)


def test_ela_parser_does_not_append_title_case_lane_header_to_grade_9_r3() -> None:
    parsed = parse_alabama_ela_2021(_document())
    grade_nine = next(course for course in parsed.courses if course.course_key == "grade_9")
    r3 = next(standard for standard in grade_nine.standards if standard.code == "R3")

    assert r3.text == (
        "Utilize active listening skills in formal and informal conversations, "
        "following predetermined norms."
    )
    assert "Expression" not in r3.text
