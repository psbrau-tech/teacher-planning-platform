from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_SCRIPT = ROOT / "scripts" / "run_standards_maintenance.py"


def test_parser_rematerialization_is_explicitly_scoped_to_reviewed_ela_source() -> None:
    script = MAINTENANCE_SCRIPT.read_text(encoding="utf-8")
    assert 'PARSER_REMATERIALIZATION_SOURCE_KEYS = frozenset(' in script
    assert '"alabama_academic_english_language_arts"' in script
    assert '"alabama_academic_arts_education"' not in script
    assert "source_result.source_key not in PARSER_REMATERIALIZATION_SOURCE_KEYS" in script
