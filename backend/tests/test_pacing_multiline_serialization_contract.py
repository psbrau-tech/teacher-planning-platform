from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT / "frontend" / "src" / "curriculumRows.ts"


def test_multiline_learning_targets_are_reassembled_before_row_validation() -> None:
    parser = PARSER.read_text(encoding="utf-8")
    assert 'value.split("\\n")' in parser
    assert "delimiterCount(pending) < 4" in parser
    assert "serializedRows(value)" in parser
    assert "validatePacingRowLimits" in parser
