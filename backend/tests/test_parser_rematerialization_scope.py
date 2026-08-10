from __future__ import annotations

from scripts.run_standards_maintenance import PARSER_REMATERIALIZATION_SOURCE_KEYS


def test_parser_rematerialization_is_explicitly_scoped_to_reviewed_ela_source() -> None:
    assert PARSER_REMATERIALIZATION_SOURCE_KEYS == frozenset(
        {"alabama_academic_english_language_arts"}
    )
    assert "alabama_academic_arts_education" not in PARSER_REMATERIALIZATION_SOURCE_KEYS
