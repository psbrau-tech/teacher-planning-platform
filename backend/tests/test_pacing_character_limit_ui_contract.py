from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
LIMITS = FRONTEND / "pacingLimits.ts"
EDITOR = FRONTEND / "PacingSequenceEditor.tsx"
PARSER = FRONTEND / "curriculumRows.ts"
STYLES = FRONTEND / "pacing-sequence.css"
API = ROOT / "backend" / "app" / "curriculum_api.py"


def test_pacing_editor_has_shared_generous_character_limits_and_counters() -> None:
    limits = LIMITS.read_text(encoding="utf-8")
    editor = EDITOR.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert "unit: 300" in limits
    assert "lesson: 1000" in limits
    assert "targets: 3000" in limits
    assert "assessment: 2000" in limits
    assert "maxLength={PACING_LIMITS.unit}" in editor
    assert "maxLength={PACING_LIMITS.lesson}" in editor
    assert "maxLength={PACING_LIMITS.targets}" in editor
    assert "maxLength={PACING_LIMITS.assessment}" in editor
    assert "characters remaining" in editor
    assert "Character limit reached" in editor
    assert "pacing-character-counter" in styles
    assert "limit-reached" in styles


def test_excel_and_serialized_pacing_rows_are_validated_before_save() -> None:
    editor = EDITOR.read_text(encoding="utf-8")
    parser = PARSER.read_text(encoding="utf-8")

    assert "validatePacingRowLimits(row, index + 1)" in editor
    assert "validatePacingRowLimits({ unit, lesson, targets, assessment }, rowNumber)" in parser
    assert "exceeds the" in LIMITS.read_text(encoding="utf-8")


def test_curriculum_api_accepts_the_new_pacing_limits() -> None:
    api = API.read_text(encoding="utf-8")

    assert "unit_title: str = Field(min_length=1, max_length=300)" in api
    assert "lesson_title: str = Field(min_length=1, max_length=1000)" in api
    assert 'assessment: str = Field(default="", max_length=2000)' in api
