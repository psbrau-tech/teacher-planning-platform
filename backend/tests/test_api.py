from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assignments_include_four_independent_curricula() -> None:
    response = client.get("/api/v1/assignments")
    assert response.status_code == 200
    assignments = response.json()
    assert len(assignments) == 4
    assert {item["course_name"] for item in assignments} == {
        "LET 1",
        "LET 2",
        "LET 3",
        "LET 4",
    }
    assert next(item for item in assignments if item["course_name"] == "LET 4")[
        "schedule_type"
    ] == "block"


def test_anniston_hqi_field_contract_is_exposed() -> None:
    response = client.get("/api/v1/templates/anniston-hqi/fields")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field_count"] == 57
    assert "clt_mon" in payload["fields"]
    assert "reflect_12" in payload["fields"]


def test_admin_and_cost_reports_preserve_synthetic_boundary() -> None:
    admin = client.get("/api/v1/admin/summary")
    costs = client.get("/api/v1/admin/costs")

    assert admin.status_code == 200
    assert admin.json()["data_boundary"] == "synthetic-only"
    assert admin.json()["assignments_configured"] == 4

    assert costs.status_code == 200
    assert costs.json()["cost_basis"] == "estimated synthetic usage"
    assert costs.json()["total_estimated_cost_usd"] == "0.0042"


def test_weekly_plan_rejects_unsupported_level() -> None:
    response = client.get(
        "/api/v1/weekly-plan",
        params={"level": "LET 5", "week_start": "2026-08-10"},
    )
    assert response.status_code == 422
