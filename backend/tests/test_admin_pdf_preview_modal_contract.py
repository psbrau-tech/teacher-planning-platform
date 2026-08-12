from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


def test_admin_pdf_preview_rendered_classes_have_modal_styles() -> None:
    panel = (FRONTEND / "AdminSubmissionPanel.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "AdminSubmissionPanel.css").read_text(encoding="utf-8")

    assert 'className="submission-preview-backdrop"' in panel
    assert 'className="submission-preview"' in panel
    assert 'className="submission-preview-heading"' in panel
    assert ".submission-preview-backdrop" in styles
    assert ".submission-preview {" in styles
    assert ".submission-preview-heading" in styles
    assert ".submission-preview iframe" in styles
    assert "height: min(900px, 94vh)" in styles
    assert "width: min(1180px, 96vw)" in styles
