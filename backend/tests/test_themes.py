import pytest

from app.themes import ANNISTON_THEME, GENERIC_THEME, get_theme


def test_anniston_theme_uses_approved_header_and_footer() -> None:
    assert ANNISTON_THEME.district_name == "Anniston City Schools"
    assert ANNISTON_THEME.document_title == "Instructional Planning Framework"
    assert ANNISTON_THEME.footer_text == "Prepared with Teacher Planning Platform"


def test_theme_is_presentation_only_and_exposes_css_variables() -> None:
    variables = ANNISTON_THEME.css_variables()
    assert variables["--theme-primary"].startswith("#")
    assert variables["--theme-neutral"] == "#FFFFFF"
    assert "curriculum" not in variables
    assert "standards" not in variables


def test_generic_theme_retains_logo_placeholder() -> None:
    assert GENERIC_THEME.logo_path is None
    assert GENERIC_THEME.district_name == "School or District Name"


def test_unknown_theme_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown district theme"):
        get_theme("missing")
