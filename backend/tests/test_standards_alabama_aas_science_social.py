from app import standards_alabama_aas_science_social as hardened
from app.standards_ingest import (
    ExtractedDocument,
    ParsedCourse,
    ParsedStandard,
    ParsedStandardsDocument,
)


def _parsed(parser_key: str, parser_version: str) -> ParsedStandardsDocument:
    return ParsedStandardsDocument(
        parser_key=parser_key,
        parser_version=parser_version,
        normalized_sha256="a" * 64,
        courses=(
            ParsedCourse(
                course_key="kindergarten",
                display_name="Kindergarten",
                source_course_code=None,
                grade_band="K",
                standards=(
                    ParsedStandard(
                        code="TEST.AAS.K.1",
                        text="Repeated overview example.",
                        strand="Alternate Achievement Standards",
                    ),
                    ParsedStandard(
                        code="TEST.AAS.K.1",
                        text="Repeated overview example.",
                        strand="Alternate Achievement Standards",
                    ),
                    ParsedStandard(
                        code="TEST.AAS.K.2",
                        text="Second standard.",
                        strand="Alternate Achievement Standards",
                    ),
                    ParsedStandard(
                        code="TEST.AAS.K.3",
                        text="Third standard.",
                        strand="Alternate Achievement Standards",
                    ),
                ),
            ),
        ),
    )


def test_science_wrapper_removes_exact_overview_duplicate(monkeypatch) -> None:
    monkeypatch.setattr(
        hardened,
        "_parse_science",
        lambda extracted: _parsed(
            "alabama_aas_science_2017",
            "gate-e-alabama-aas-science-2017-v1",
        ),
    )

    parsed = hardened.parse_alabama_aas_science_2017(
        ExtractedDocument(lines=("synthetic",), normalized_sha256="a" * 64)
    )

    assert parsed.parser_version == "gate-e-alabama-aas-science-2017-v2"
    assert [standard.code for standard in parsed.courses[0].standards] == [
        "TEST.AAS.K.1",
        "TEST.AAS.K.2",
        "TEST.AAS.K.3",
    ]


def test_social_wrapper_preserves_same_code_with_distinct_authoritative_text(monkeypatch) -> None:
    source = _parsed(
        "alabama_aas_social_studies_2017",
        "gate-e-alabama-aas-social-studies-2017-v1",
    )
    course = source.courses[0]
    monkeypatch.setattr(
        hardened,
        "_parse_social_studies",
        lambda extracted: ParsedStandardsDocument(
            parser_key=source.parser_key,
            parser_version=source.parser_version,
            normalized_sha256=source.normalized_sha256,
            courses=(
                ParsedCourse(
                    course_key=course.course_key,
                    display_name=course.display_name,
                    source_course_code=course.source_course_code,
                    grade_band=course.grade_band,
                    standards=(
                        ParsedStandard(
                            code="SS.AAS.7.11",
                            text="First authoritative statement.",
                            strand="Alternate Achievement Standards",
                        ),
                        ParsedStandard(
                            code="SS.AAS.7.11",
                            text="Second authoritative statement.",
                            strand="Alternate Achievement Standards",
                        ),
                        ParsedStandard(
                            code="SS.AAS.7.12",
                            text="Third standard.",
                            strand="Alternate Achievement Standards",
                        ),
                    ),
                ),
            ),
        ),
    )

    parsed = hardened.parse_alabama_aas_social_studies_2017(
        ExtractedDocument(lines=("synthetic",), normalized_sha256="a" * 64)
    )

    assert parsed.parser_version == "gate-e-alabama-aas-social-studies-2017-v2"
    assert [standard.code for standard in parsed.courses[0].standards] == [
        "SS.AAS.7.11",
        "SS.AAS.7.11",
        "SS.AAS.7.12",
    ]
    assert [standard.text for standard in parsed.courses[0].standards[:2]] == [
        "First authoritative statement.",
        "Second authoritative statement.",
    ]
