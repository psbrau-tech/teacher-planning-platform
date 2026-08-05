from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DistrictTheme:
    """Presentation-only configuration for district-branded exports.

    Theme data must not contain curriculum, scheduling, standards, or user data.
    """

    key: str
    district_name: str
    document_title: str
    footer_text: str
    primary_hex: str
    secondary_hex: str
    neutral_hex: str
    surface_hex: str
    border_hex: str
    logo_path: Path | None = None

    def css_variables(self) -> dict[str, str]:
        return {
            "--theme-primary": self.primary_hex,
            "--theme-secondary": self.secondary_hex,
            "--theme-neutral": self.neutral_hex,
            "--theme-surface": self.surface_hex,
            "--theme-border": self.border_hex,
        }


ANNISTON_THEME = DistrictTheme(
    key="anniston",
    district_name="Anniston City Schools",
    document_title="Instructional Planning Framework",
    footer_text="Prepared with Teacher Planning Platform",
    # Pilot palette follows the approved black, white, gray, and red direction.
    # Exact district brand values may be substituted after the official asset package is received.
    primary_hex="#B5121B",
    secondary_hex="#111111",
    neutral_hex="#FFFFFF",
    surface_hex="#F2F2F2",
    border_hex="#8A8A8A",
    logo_path=None,
)

GENERIC_THEME = DistrictTheme(
    key="generic",
    district_name="School or District Name",
    document_title="Instructional Planning Framework",
    footer_text="Prepared with Teacher Planning Platform",
    primary_hex="#333333",
    secondary_hex="#111111",
    neutral_hex="#FFFFFF",
    surface_hex="#F4F4F4",
    border_hex="#999999",
    logo_path=None,
)

THEMES: dict[str, DistrictTheme] = {
    ANNISTON_THEME.key: ANNISTON_THEME,
    GENERIC_THEME.key: GENERIC_THEME,
}


def get_theme(key: str) -> DistrictTheme:
    try:
        return THEMES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown district theme: {key}") from exc
