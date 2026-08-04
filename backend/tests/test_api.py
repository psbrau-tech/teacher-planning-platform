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
    assert payload["template_installed"] is True
    assert payload["documents"] == [
        "instructional-framework",
        "week-at-a-glance",
        "weekly-reflection",
    ]


def test_document_generation_uses_approved_template() -> None:
    response = client.post(
        "/api/v1/documents/anniston-hqi",
        json={"teacher": "Synthetic Teacher", "course": "LET 1"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_independent_document_adds_continuation_pages() -> None:
    response = client.post(
        "/api/v1/documents/anniston-hqi/instructional-framework",
        json={
            "teacher": "Synthetic Teacher",
            "course": "LET 1",
            "week_of": "August 10, 2026",
            "standards": "Official standard detail. " * 240,
        },
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert int(response.headers["x-tpp-page-count"]) >= 2
    assert int(response.headers["x-tpp-continuation-pages"]) >= 1


def test_combined_packet_reports_three_documents() -> None:
    response = client.post(
        "/api/v1/documents/anniston-hqi-packet",
        json={
            "teacher": "Synthetic Teacher",
            "course": "LET 1",
            "standards": "Official standard detail. " * 240,
            "reflect_1": "Reflection detail. " * 240,
        },
    )
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["x-tpp-document-count"] == "3"
    assert int(response.headers["x-tpp-continuation-pages"]) >= 2


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
