from app.standards_course_catalog import parse_course_catalog_document
from app.standards_ingest import ExtractedDocument


def _document(lines: tuple[str, ...]) -> ExtractedDocument:
    return ExtractedDocument(lines=lines, normalized_sha256="a" * 64)


def test_program_guide_parser_extracts_verified_army_jrotc_courses() -> None:
    parsed = parse_course_catalog_document(
        "alabama_cte_program_generic",
        _document(
            (
                "Program Courses",
                "09051G1001 Army JROTC Leadership Education and Training I 1 9-12",
                "09052G1001 Army JROTC Leadership Education and Training II 1 9-12",
                "09053G1001 Army JROTC Leadership Education and Training III 1 9-12",
                "09054G1001 Army JROTC Leadership Education and Training IV 1 9-12",
            )
        ),
    )

    by_code = {course.source_course_code: course for course in parsed.courses}
    assert by_code["09051G1001"].course_key == "army_jrotc_let_1"
    assert by_code["09052G1001"].course_key == "army_jrotc_let_2"
    assert by_code["09053G1001"].course_key == "army_jrotc_let_3"
    assert by_code["09054G1001"].course_key == "army_jrotc_let_4"
    assert by_code["09052G1001"].display_name == (
        "Army JROTC Leadership Education and Training II"
    )
    assert by_code["09052G1001"].grade_band == "9-12"


def test_program_guide_parser_handles_two_course_pairs_on_one_extracted_line() -> None:
    parsed = parse_course_catalog_document(
        "alabama_cte_program_generic",
        _document(
            (
                "Program Courses",
                "09051G1001 Army JROTC Leadership Education and Training I 1 9-12 "
                "09052G1001 Army JROTC Leadership Education and Training II 1 9-12",
            )
        ),
    )

    assert [course.source_course_code for course in parsed.courses] == [
        "09051G1001",
        "09052G1001",
    ]
    assert [course.course_key for course in parsed.courses] == [
        "army_jrotc_let_1",
        "army_jrotc_let_2",
    ]


def test_program_guide_parser_handles_course_code_and_name_split_across_lines() -> None:
    parsed = parse_course_catalog_document(
        "alabama_cte_program_generic",
        _document(
            (
                "09053G1001",
                "Army JROTC Leadership Education and Training III 1 9-12",
            )
        ),
    )

    assert len(parsed.courses) == 1
    assert parsed.courses[0].course_key == "army_jrotc_let_3"
    assert parsed.courses[0].source_course_code == "09053G1001"


def test_program_guide_parser_deduplicates_repeated_course_rows_by_state_code() -> None:
    parsed = parse_course_catalog_document(
        "alabama_cte_program_generic",
        _document(
            (
                "09054G1001 Army JROTC Leadership Education and Training IV 1 9-12",
                "Pathway Sequence",
                "09054G1001 Army JROTC Leadership Education and Training IV 1 9-12",
            )
        ),
    )

    assert len(parsed.courses) == 1
    assert parsed.courses[0].source_course_code == "09054G1001"
