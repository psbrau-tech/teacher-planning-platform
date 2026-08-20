from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
MAIN = FRONTEND / "main.tsx"
STANDARDS = FRONTEND / "StandardsPanel.tsx"
OVERRIDES = FRONTEND / "standards-browser-overrides.css"


def test_single_mapped_standards_group_is_visually_flattened() -> None:
    main = MAIN.read_text(encoding="utf-8")
    css = OVERRIDES.read_text(encoding="utf-8")

    assert 'import "./standards-browser-overrides.css";' in main
    assert ".standards-browser > .standard-group:only-of-type" in css
    assert ".standard-group:only-of-type > summary" in css
    assert "display: none" in css
    assert ".standard-group:only-of-type > .standard-list" in css
    assert "padding: 0" in css


def test_flattening_rule_preserves_multi_group_fallback() -> None:
    css = OVERRIDES.read_text(encoding="utf-8")

    assert ":only-of-type" in css
    assert ".standard-group:not(" not in css


def test_proficiency_guidance_has_one_course_level_control_before_content_standards() -> None:
    source = STANDARDS.read_text(encoding="utf-8")
    css = OVERRIDES.read_text(encoding="utf-8")

    assert "function isContentStandard" in source
    assert "const renderProficiencyCollection" in source
    assert "const renderMappedStandards" in source
    assert "standards.findIndex(isContentStandard)" in source
    assert "index === proficiencyInsertIndex ? renderProficiencyCollection() : null" in source
    assert source.count("<summary><strong>View ALSDE proficiency scale</strong></summary>") == 1
    assert "proficiencyByCode" not in source
    assert "standard-option-with-guidance" not in source
    assert ".proficiency-scale-collection" in css
    assert ".standard-option-with-guidance" not in css
