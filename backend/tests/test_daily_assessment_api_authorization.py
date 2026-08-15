from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = ROOT / "backend" / "app" / "daily_assessment_api.py"
ROUTER = ROOT / "backend" / "app" / "ai_reflection_api.py"


def test_daily_assessment_api_requires_school_reporting_admin() -> None:
    source = API.read_text(encoding="utf-8")
    assert "Depends(require_school_reporting_admin)" in source
    assert "identity.school_id" in source
    assert '"target_school_id": school_id' in source


def test_daily_assessment_api_is_registered_in_governed_router() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "daily_assessment_router" in source
    assert "router.include_router(daily_assessment_router)" in source
