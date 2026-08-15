from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYTICS = ROOT / "backend" / "app" / "daily_assessment_analytics.py"
API = ROOT / "backend" / "app" / "daily_assessment_api.py"


def test_daily_assessment_classification_has_no_ai_provider_dependency() -> None:
    source = (ANALYTICS.read_text(encoding="utf-8") + API.read_text(encoding="utf-8")).lower()
    assert "request_structured_response" not in source
    assert "openai" not in source
    assert "ai_usage" not in source
