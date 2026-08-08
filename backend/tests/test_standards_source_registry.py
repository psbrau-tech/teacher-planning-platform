from app.standards_catalog_discovery import DiscoveredStandardsSource
from app.standards_source_registry import source_ingest_plan


def _source(source_key: str, family: str) -> DiscoveredStandardsSource:
    return DiscoveredStandardsSource(
        source_key=source_key,
        family=family,
        category_key="synthetic_category",
        category_name="Synthetic Category",
        category_type="academic_subject" if family == "alabama_academic" else "career_cluster",
        authority="Alabama State Department of Education",
        title="Synthetic authoritative source",
        edition="2026",
        landing_url="https://www.alabamaachieves.org/acad-stand/",
        document_url="https://www.alabamaachieves.org/files/synthetic.pdf",
        document_format="pdf",
        parser_key_hint="synthetic",
        source_kind="course_of_study",
    )


def test_verified_academic_sources_have_source_specific_parsers() -> None:
    expected = {
        "alabama_academic_arts_education": "alabama_arts_2024",
        "alabama_academic_digital_literacy_computer_science": "alabama_dlcs_2025",
        "alabama_academic_driver_traffic_safety": "alabama_driver_traffic_safety_2007",
        "alabama_academic_english_language_arts": "alabama_ela_2021",
        "alabama_academic_health": "alabama_health_2019",
        "alabama_academic_mathematics": "alabama_math_2019",
        "alabama_academic_mathematics_algebra_with_finance": (
            "alabama_algebra_finance_revised"
        ),
        "alabama_academic_mathematics_career_mathematics": "alabama_career_mathematics",
        "alabama_academic_physical_education": "alabama_physical_education_2019",
        "alabama_academic_science": "alabama_science_2023",
        "alabama_academic_social_studies": "alabama_social_studies_2024",
        "alabama_academic_world_languages": "alabama_world_languages_2017",
    }

    for source_key, parser_key in expected.items():
        plan = source_ingest_plan(_source(source_key, "alabama_academic"))
        assert plan.parser_ready is True
        assert plan.parser_key == parser_key
        assert plan.source_kind == "course_of_study"
        assert plan.provides_standard_entries is True


def test_unverified_academic_source_is_governed_but_not_approvable_yet() -> None:
    plan = source_ingest_plan(
        _source("alabama_academic_future_subject", "alabama_academic")
    )

    assert plan.parser_ready is False
    assert plan.parser_key == "alabama_academic_parser_pending"
    assert plan.provides_standard_entries is True
    assert "deterministic parser verification is pending" in plan.readiness_detail


def test_all_cte_course_of_study_sources_use_generic_standards_parser() -> None:
    plan = source_ingest_plan(
        _source("alabama_cte_cos_finance", "alabama_cte")
    )

    assert plan.parser_ready is True
    assert plan.parser_key == "alabama_cte_cos_generic"
    assert plan.source_kind == "course_of_study"
    assert plan.provides_standard_entries is True


def test_cte_program_guide_is_course_listing_only() -> None:
    plan = source_ingest_plan(
        _source("alabama_cte_program_finance", "alabama_cte_program")
    )

    assert plan.parser_ready is True
    assert plan.parser_key == "alabama_cte_program_generic"
    assert plan.source_kind == "program_guide"
    assert plan.provides_standard_entries is False
