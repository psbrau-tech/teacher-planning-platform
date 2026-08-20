from uuid import uuid4

from fastapi.testclient import TestClient

import app.standards_catalog_api as catalog_api
from app.main import app

client = TestClient(app)
HEADERS = {"X-TPP-Teacher-ID": "teacher-proficiency-test"}
SOURCE_ID = uuid4()
SNAPSHOT_ID = uuid4()


class FakeClient:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, object]] = []

    def request(self, method: str, resource: str, *, params=None, payload=None, prefer=None):
        self.calls.append((method, resource, params))
        return self.responses.get(resource, [])


def _install(monkeypatch, fake: FakeClient) -> None:
    monkeypatch.setattr(catalog_api, "_client", lambda identity, settings: fake)


def test_teacher_reads_approved_grade_proficiency_guidance(monkeypatch) -> None:
    fake = FakeClient(
        {
            "standard_sources": [
                {
                    "id": str(SOURCE_ID),
                    "authority": "Alabama State Department of Education",
                    "title": "Grade 9 ELA Proficiency Scales",
                    "landing_url": "https://english-language-arts.alsde.edu/proficiency-scales",
                    "approved_snapshot_id": str(SNAPSHOT_ID),
                }
            ],
            "standard_snapshots": [
                {
                    "id": str(SNAPSHOT_ID),
                    "source_version": "2024",
                    "retrieved_at": "2026-08-20T16:00:00Z",
                    "resolved_document_url": "https://drive.google.com/uc?export=download&id=current",
                }
            ],
            "standard_proficiency_scales": [
                {
                    "standard_code": "4",
                    "standard_text": "Analyze how authors use characterization.",
                    "literacy_type": "Critical Literacy",
                    "focus_area": "Reception",
                    "category": "Reading",
                    "levels": {
                        "4.0": "Extend the analysis beyond taught applications.",
                        "3.0": "Analyze how authors use characterization.",
                        "2.0": "Identify characterization in a text.",
                    },
                }
            ],
        }
    )
    _install(monkeypatch, fake)

    response = client.get("/api/v1/standards/proficiency/grade/9", headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["grade_band"] == "9"
    assert body["source_version"] == "2024"
    assert body["scales"][0]["standard_code"] == "4"
    assert body["scales"][0]["levels"]["3.0"].startswith("Analyze")
    scale_call = next(call for call in fake.calls if call[1] == "standard_proficiency_scales")
    assert scale_call[2]["snapshot_id"] == f"eq.{SNAPSHOT_ID}"


def test_proficiency_endpoint_is_bounded_to_grades_6_12() -> None:
    response = client.get("/api/v1/standards/proficiency/grade/5", headers=HEADERS)
    assert response.status_code == 404


def test_unapproved_proficiency_source_does_not_surface_guidance(monkeypatch) -> None:
    fake = FakeClient(
        {
            "standard_sources": [
                {
                    "id": str(SOURCE_ID),
                    "authority": "Alabama State Department of Education",
                    "title": "Grade 6 ELA Proficiency Scales",
                    "landing_url": "https://english-language-arts.alsde.edu/proficiency-scales",
                    "approved_snapshot_id": None,
                }
            ]
        }
    )
    _install(monkeypatch, fake)

    response = client.get("/api/v1/standards/proficiency/grade/6", headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["scales"] == []
