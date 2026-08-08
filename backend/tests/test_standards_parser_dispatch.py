from app import standards_parser_dispatch as dispatch
from app.standards_ingest import ExtractedDocument, ParsedStandardsDocument


def _parsed(parser_key: str) -> ParsedStandardsDocument:
    return ParsedStandardsDocument(
        parser_key=parser_key,
        parser_version="synthetic-v1",
        normalized_sha256="a" * 64,
        courses=(),
    )


def test_governed_dispatch_routes_verified_comprehensive_academic_parsers(monkeypatch) -> None:
    extracted = ExtractedDocument(lines=("synthetic",), normalized_sha256="a" * 64)
    called: list[str] = []

    def math_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("math")
        return _parsed("alabama_math_2019")

    def science_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("science")
        return _parsed("alabama_science_2023")

    def social_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("social")
        return _parsed("alabama_social_studies_2024")

    monkeypatch.setattr(dispatch, "parse_alabama_math_2019", math_parser)
    monkeypatch.setattr(dispatch, "parse_alabama_science_2023", science_parser)
    monkeypatch.setattr(dispatch, "parse_alabama_social_studies_2024", social_parser)

    assert (
        dispatch.parse_governed_standards_document("alabama_math_2019", extracted).parser_key
        == "alabama_math_2019"
    )
    assert (
        dispatch.parse_governed_standards_document("alabama_science_2023", extracted).parser_key
        == "alabama_science_2023"
    )
    assert (
        dispatch.parse_governed_standards_document(
            "alabama_social_studies_2024",
            extracted,
        ).parser_key
        == "alabama_social_studies_2024"
    )
    assert called == ["math", "science", "social"]
