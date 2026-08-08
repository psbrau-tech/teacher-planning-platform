from __future__ import annotations

from dataclasses import dataclass

from .standards_catalog_discovery import DiscoveredStandardsSource


@dataclass(frozen=True, slots=True)
class SourceIngestPlan:
    parser_key: str
    source_kind: str
    provides_standard_entries: bool
    parser_ready: bool
    readiness_detail: str


def source_ingest_plan(source: DiscoveredStandardsSource) -> SourceIngestPlan:
    if source.family == "alabama_cte_program":
        return SourceIngestPlan(
            parser_key="alabama_cte_program_generic",
            source_kind="program_guide",
            provides_standard_entries=False,
            parser_ready=True,
            readiness_detail="Generic Alabama CTE Program Guide course-listing parser",
        )

    if source.family == "alabama_cte":
        return SourceIngestPlan(
            parser_key="alabama_cte_cos_generic",
            source_kind="course_of_study",
            provides_standard_entries=True,
            parser_ready=True,
            readiness_detail="Generic Alabama CTE Course of Study standards parser",
        )

    if source.family == "alabama_academic":
        parser_key = _ACADEMIC_PARSERS.get(source.source_key)
        if parser_key is not None:
            return SourceIngestPlan(
                parser_key=parser_key,
                source_kind="course_of_study",
                provides_standard_entries=True,
                parser_ready=True,
                readiness_detail="Verified source-specific Alabama academic parser",
            )
        return SourceIngestPlan(
            parser_key="alabama_academic_parser_pending",
            source_kind="course_of_study",
            provides_standard_entries=True,
            parser_ready=False,
            readiness_detail=(
                "Source discovered and governed, but deterministic parser verification is pending"
            ),
        )

    return SourceIngestPlan(
        parser_key="unsupported_source_parser_pending",
        source_kind="reference",
        provides_standard_entries=False,
        parser_ready=False,
        readiness_detail="Source family requires explicit parser/source-role review",
    )


_ACADEMIC_PARSERS = {
    "alabama_academic_english_language_arts": "alabama_ela_2021",
    "alabama_academic_mathematics": "alabama_math_2019",
    "alabama_academic_science": "alabama_science_2023",
    "alabama_academic_social_studies": "alabama_social_studies_2024",
}
