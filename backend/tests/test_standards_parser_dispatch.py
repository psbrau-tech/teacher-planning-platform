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

    def algebra_finance_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("algebra_finance")
        return _parsed("alabama_algebra_finance_revised")

    def career_math_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("career_math")
        return _parsed("alabama_career_mathematics")

    def driver_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("driver")
        return _parsed("alabama_driver_traffic_safety_2007")

    def health_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("health")
        return _parsed("alabama_health_2019")

    def math_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("math")
        return _parsed("alabama_math_2019")

    def physical_education_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("physical_education")
        return _parsed("alabama_physical_education_2019")

    def science_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("science")
        return _parsed("alabama_science_2023")

    def social_parser(value: ExtractedDocument) -> ParsedStandardsDocument:
        assert value is extracted
        called.append("social")
        return _parsed("alabama_social_studies_2024")

    monkeypatch.setattr(dispatch, "parse_alabama_algebra_finance", algebra_finance_parser)
    monkeypatch.setattr(dispatch, "parse_alabama_career_mathematics", career_math_parser)
    monkeypatch.setattr(
        dispatch,
        "parse_alabama_driver_traffic_safety_2007",
        driver_parser,
    )
    monkeypatch.setattr(dispatch, "parse_alabama_health_2019", health_parser)
    monkeypatch.setattr(dispatch, "parse_alabama_math_2019", math_parser)
    monkeypatch.setattr(
        dispatch,
        "parse_alabama_physical_education_2019",
        physical_education_parser,
    )
    monkeypatch.setattr(dispatch, "parse_alabama_science_2023", science_parser)
    monkeypatch.setattr(dispatch, "parse_alabama_social_studies_2024", social_parser)

    assert (
        dispatch.parse_governed_standards_document(
            "alabama_algebra_finance_revised",
            extracted,
        ).parser_key
        == "alabama_algebra_finance_revised"
    )
    assert (
        dispatch.parse_governed_standards_document(
            "alabama_career_mathematics",
            extracted,
        ).parser_key
        == "alabama_career_mathematics"
    )
    assert (
        dispatch.parse_governed_standards_document(
            "alabama_driver_traffic_safety_2007",
            extracted,
        ).parser_key
        == "alabama_driver_traffic_safety_2007"
    )
    assert (
        dispatch.parse_governed_standards_document("alabama_health_2019", extracted).parser_key
        == "alabama_health_2019"
    )
    assert (
        dispatch.parse_governed_standards_document("alabama_math_2019", extracted).parser_key
        == "alabama_math_2019"
    )
    assert (
        dispatch.parse_governed_standards_document(
            "alabama_physical_education_2019",
            extracted,
        ).parser_key
        == "alabama_physical_education_2019"
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
    assert called == [
        "algebra_finance",
        "career_math",
        "driver",
        "health",
        "math",
        "physical_education",
        "science",
        "social",
    ]
