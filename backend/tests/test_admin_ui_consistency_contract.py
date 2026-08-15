from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "frontend" / "src" / "main.tsx"
CONSISTENCY = ROOT / "frontend" / "src" / "UiConsistencyExperience.tsx"
STYLES = ROOT / "frontend" / "src" / "ui-consistency.css"
REFLECTION = ROOT / "frontend" / "src" / "AiReflectionPanel.tsx"


def test_success_and_error_toasts_auto_dismiss_after_five_seconds() -> None:
    main = MAIN.read_text(encoding="utf-8")
    source = CONSISTENCY.read_text(encoding="utf-8")

    assert 'import { UiConsistencyExperience }' in main
    assert "<UiConsistencyExperience />" in main
    assert "TOAST_DISMISS_MS = 5000" in source
    assert 'querySelectorAll<HTMLElement>(".toast-alert")' in source
    assert 'button[aria-label="Dismiss"]' in source
    assert "MutationObserver" in source
    assert "window.setTimeout" in source


def test_pdf_preview_headers_share_top_right_close_layout() -> None:
    source = REFLECTION.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")

    assert 'className="pdf-modal-header"' in source
    assert "Close preview" in source
    assert ".pdf-modal-header" in styles
    assert "justify-content: space-between" in styles
    assert "align-items: center" in styles


def test_assessment_trend_flows_directly_into_reflection_informed_plc() -> None:
    main = MAIN.read_text(encoding="utf-8")

    assessment = main.index("<DailyAssessmentAnalyticsExperience />")
    friday = main.index("<FridayStatusExperience />")
    plc = main.index("<PlcFacilitationArtifactExperience />")
    assert assessment < friday < plc
    # FridayStatusExperience is teacher-Dashboard-only, so it creates no administrator
    # content between the assessment trend and the PLC portal content.
