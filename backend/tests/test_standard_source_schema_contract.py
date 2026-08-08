from uuid import UUID

from app.standards_catalog_discovery import DiscoveredStandardsSource
from app.standards_catalog_materialize import _upsert_pending_source
from app.standards_source_registry import source_ingest_plan

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")


class CaptureClient:
    def __init__(self) -> None:
        self.payload = None

    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        assert method == "POST"
        assert resource == "standard_sources"
        assert params is None
        assert prefer == "return=representation"
        self.payload = payload
        return [{"id": str(SOURCE_ID)}]


def test_pending_source_payload_matches_live_standard_sources_schema() -> None:
    source = DiscoveredStandardsSource(
        source_key="alabama_academic_arts_education",
        family="alabama_academic",
        category_key="arts_education",
        category_name="Arts Education",
        category_type="academic_subject",
        authority="Alabama State Department of Education",
        title="2024 Arts Education Course of Study",
        edition="2024",
        landing_url="https://www.alabamaachieves.org/acad-stand/",
        document_url=(
            "https://www.alabamaachieves.org/wp-content/uploads/2025/01/"
            "AS_20250108_2024-Alabama-Course-of-Study-Arts-Education_V1.0.pdf"
        ),
        document_format="pdf",
        parser_key_hint="alabama_cos_generic",
        source_kind="course_of_study",
    )
    client = CaptureClient()

    source_id = _upsert_pending_source(client, source, source_ingest_plan(source), None)

    assert source_id == SOURCE_ID
    assert client.payload is not None
    assert "metadata" not in client.payload
    assert set(client.payload) == {
        "source_key",
        "family",
        "authority",
        "title",
        "edition",
        "landing_url",
        "document_url",
        "document_format",
        "resolver_key",
        "parser_key",
        "source_kind",
        "provides_standard_entries",
        "catalog_category_key",
        "catalog_category_name",
        "catalog_category_type",
        "discovery_status",
        "is_active",
    }
