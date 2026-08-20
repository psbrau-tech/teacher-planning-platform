from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
MAIN = FRONTEND / "main.tsx"
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


def test_proficiency_scale_is_visually_attached_to_exact_standard() -> None:
    css = OVERRIDES.read_text(encoding="utf-8")

    assert ".standard-option-with-guidance:has(> .proficiency-scale) > .standard-option" in css
    assert "border-radius: 14px 14px 0 0" in css
    assert ".standard-option-with-guidance > .proficiency-scale" in css
    assert "margin: -1px 0 0" in css
    assert "border-top: 0" in css
    assert "border-radius: 0 0 14px 14px" in css
    assert ".proficiency-scale > summary" in css
