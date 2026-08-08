from __future__ import annotations

from .standards_alabama_health import parse_alabama_health_2019
from .standards_alabama_math import parse_alabama_math_2019
from .standards_alabama_parsers import (
    parse_alabama_cte_course_of_study,
    parse_alabama_ela_k12,
)
from .standards_alabama_science import parse_alabama_science_2023
from .standards_alabama_social_studies import parse_alabama_social_studies_2024
from .standards_ingest import (
    ExtractedDocument,
    ParsedStandardsDocument,
    parse_document,
)


def parse_governed_standards_document(
    parser_key: str,
    extracted: ExtractedDocument,
) -> ParsedStandardsDocument:
    if parser_key == "alabama_ela_2021":
        return parse_alabama_ela_k12(extracted)
    if parser_key in {"alabama_bma_2021", "alabama_cte_cos_generic"}:
        return parse_alabama_cte_course_of_study(parser_key, extracted)
    if parser_key == "alabama_health_2019":
        return parse_alabama_health_2019(extracted)
    if parser_key == "alabama_math_2019":
        return parse_alabama_math_2019(extracted)
    if parser_key == "alabama_science_2023":
        return parse_alabama_science_2023(extracted)
    if parser_key == "alabama_social_studies_2024":
        return parse_alabama_social_studies_2024(extracted)
    return parse_document(parser_key, extracted)
