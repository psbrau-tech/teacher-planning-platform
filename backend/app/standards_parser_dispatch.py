from __future__ import annotations

from .standards_alabama_parsers import (
    parse_alabama_cte_course_of_study,
    parse_alabama_ela_k12,
)
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
    return parse_document(parser_key, extracted)
