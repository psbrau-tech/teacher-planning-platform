from __future__ import annotations

from .standards_alabama_algebra_finance import parse_alabama_algebra_finance
from .standards_alabama_arts import parse_alabama_arts_2024
from .standards_alabama_career_mathematics import parse_alabama_career_mathematics
from .standards_alabama_dlcs import parse_alabama_dlcs_2025
from .standards_alabama_driver_traffic_safety import (
    parse_alabama_driver_traffic_safety_2007,
)
from .standards_alabama_ela import parse_alabama_ela_2021
from .standards_alabama_health import parse_alabama_health_2019
from .standards_alabama_math import parse_alabama_math_2019
from .standards_alabama_parsers import parse_alabama_cte_course_of_study
from .standards_alabama_physical_education import parse_alabama_physical_education_2019
from .standards_alabama_science import parse_alabama_science_2023
from .standards_alabama_social_studies import parse_alabama_social_studies_2024
from .standards_alabama_world_languages import parse_alabama_world_languages_2017
from .standards_ingest import (
    ExtractedDocument,
    ParsedStandardsDocument,
    parse_document,
)


def parse_governed_standards_document(
    parser_key: str,
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    if parser_key == "alabama_algebra_finance_revised":
        return parse_alabama_algebra_finance(extracted)
    if parser_key == "alabama_arts_2024":
        return parse_alabama_arts_2024(extracted)
    if parser_key == "alabama_career_mathematics":
        return parse_alabama_career_mathematics(extracted)
    if parser_key == "alabama_dlcs_2025":
        return parse_alabama_dlcs_2025(extracted)
    if parser_key == "alabama_driver_traffic_safety_2007":
        return parse_alabama_driver_traffic_safety_2007(extracted)
    if parser_key == "alabama_ela_2021":
        return parse_alabama_ela_2021(extracted)
    if parser_key in {"alabama_bma_2021", "alabama_cte_cos_generic"}:
        return parse_alabama_cte_course_of_study(parser_key, extracted)
    if parser_key == "alabama_health_2019":
        return parse_alabama_health_2019(extracted)
    if parser_key == "alabama_math_2019":
        return parse_alabama_math_2019(extracted)
    if parser_key == "alabama_physical_education_2019":
        return parse_alabama_physical_education_2019(extracted)
    if parser_key == "alabama_science_2023":
        return parse_alabama_science_2023(extracted)
    if parser_key == "alabama_social_studies_2024":
        return parse_alabama_social_studies_2024(extracted)
    if parser_key == "alabama_world_languages_2017":
        return parse_alabama_world_languages_2017(extracted)
    return parse_document(parser_key, extracted)
