from uuid import UUID, uuid4

import pytest

from app.standards_catalog_discovery import DiscoveredStandardsSource
from app.standards_catalog_reconcile import (
    StandardsCatalogReconcileError,
    catalog_sha256,
    compare_catalog,
    reconcile_and_record_catalog,
)
from app.supabase_rest import SupabaseRestError

RUN_ID = uuid4()
ELA_ID = uuid4()
SCIENCE_ID = uuid4()
MISSING_ID = uuid4()


def _discovered(
    source_key: str,
    *,
    category_key: str,
    category_name: str,
    title: str,
    edition: str,
    document_url: str,
    family: str = "alabama_academic",
    category_type: str = "academic_subject",
) -> DiscoveredStandardsSource:
    return DiscoveredStandardsSource(
        source_key=source_key,
        family=family,
        category_key=category_key,
        category_name=category_name,
        category_type=category_type,
        authority="Alabama State Department of Education",
        title=title,
        edition=edition,
        landing_url="https://www.alabamaachieves.org/acad-stand/",
        document_url=document_url,
        document_format="pdf",
        parser_key_hint="alabama_cos_generic",
        source_kind="course_of_study",
    )


def _existing(
    source_id: UUID,
    source_key: str,
    *,
    category_key: str,
    category_name: str,
    title: str,
    edition: str,
    document_url: str,
    family: str = "alabama_academic",
    category_type: str = "academic_subject",
    source_kind: str = "course_of_study",
) -> dict[str, object]:
    return {
        "id": str(source_id),
        "source_key": source_key,
        "family": family,
        "authority": "Alabama State Department of Education",
        "title": title,
        "edition": edition,
        "landing_url": "https://www.alabamaachieves.org/acad-stand/",
        "document_url": document_url,
        "document_format": "pdf",
        "parser_key": "existing_parser",
        "catalog_category_key": category_key,
        "catalog_category_name": category_name,
        "catalog_category_type": category_type,
        "source_kind": source_kind,
        "discovery_status": "approved",
        "is_active": True,
    }


class FakeClient:
    def __init__(self, existing: list[dict[str, object]]) -> None:
        self.existing = existing
        self.calls: list[tuple[str, str, object, object, object]] = []

    def request(
        self,
        method: str,
        resource: str,
        *,
        params=None,
        payload=None,
        prefer=None,
    ) -> object:
        self.calls.append((method, resource, params, payload, prefer))
        if method == "GET" and resource == "standard_sources":
            return self.existing
        if method == "POST" and resource == "standard_catalog_discovery_runs":
            return [{"id": str(RUN_ID)}]
        if method == "POST" and resource == "standard_catalog_discovery_items":
            return None
        if method == "PATCH" and resource == "standard_catalog_discovery_runs":
            return None
        raise AssertionError(f"Unexpected catalog reconciliation request: {method} {resource}")


class FailingItemClient(FakeClient):
    def request(
        self,
        method: str,
        resource: str,
        *,
        params=None,
        payload=None,
        prefer=None,
    ) -> object:
        if method == "POST" and resource == "standard_catalog_discovery_items":
            self.calls.append((method, resource, params, payload, prefer))
            raise SupabaseRestError(
                "catalog evidence constraint rejected the batch",
                status_code=400,
                code="23514",
            )
        return super().request(
            method,
            resource,
            params=params,
            payload=payload,
            prefer=prefer,
        )


def test_compare_catalog_classifies_unchanged_changed_new_and_missing() -> None:
    ela = _discovered(
        "alabama_academic_english_language_arts",
        category_key="english_language_arts",
        category_name="English Language Arts",
        title="2021 Alabama Course of Study: English Language Arts",
        edition="2021",
        document_url="https://www.alabamaachieves.org/files/ela.pdf",
    )
    science = _discovered(
        "alabama_academic_science",
        category_key="science",
        category_name="Science",
        title="2024 Alabama Course of Study: Science",
        edition="2024",
        document_url="https://www.alabamaachieves.org/files/science-2024.pdf",
    )
    math = _discovered(
        "alabama_academic_mathematics",
        category_key="mathematics",
        category_name="Mathematics",
        title="2019 Alabama Course of Study: Mathematics",
        edition="2019",
        document_url="https://www.alabamaachieves.org/files/math.pdf",
    )
    existing = (
        _existing(
            ELA_ID,
            ela.source_key,
            category_key=ela.category_key,
            category_name=ela.category_name,
            title=ela.title,
            edition=ela.edition,
            document_url=ela.document_url,
        ),
        _existing(
            SCIENCE_ID,
            science.source_key,
            category_key=science.category_key,
            category_name=science.category_name,
            title="2023 Alabama Course of Study: Science",
            edition="2023",
            document_url="https://www.alabamaachieves.org/files/science-2023.pdf",
        ),
        _existing(
            MISSING_ID,
            "alabama_academic_driver_traffic_safety",
            category_key="driver_traffic_safety",
            category_name="Driver and Traffic Safety Education",
            title="2020 Driver and Traffic Safety Education Course of Study",
            edition="2020",
            document_url="https://www.alabamaachieves.org/files/driver.pdf",
        ),
    )

    items = compare_catalog(existing, (ela, science, math))
    states = {item.source_key: item.state for item in items}

    assert states == {
        "alabama_academic_driver_traffic_safety": "missing",
        "alabama_academic_english_language_arts": "unchanged",
        "alabama_academic_mathematics": "new",
        "alabama_academic_science": "changed",
    }


def test_compare_catalog_ignores_non_alabama_supplemental_issuer() -> None:
    army = {
        "id": str(uuid4()),
        "source_key": "army_jrotc_curriculum",
        "family": "army_jrotc",
        "authority": "U.S. Army Cadet Command",
        "title": "Army JROTC Curriculum Guide",
        "edition": "v12",
    }

    assert compare_catalog((army,), ()) == ()


def test_reconciliation_does_not_mark_separately_monitored_proficiency_sources_missing() -> None:
    ela = _discovered(
        "alabama_academic_english_language_arts",
        category_key="english_language_arts",
        category_name="English Language Arts",
        title="2021 Alabama Course of Study: English Language Arts",
        edition="2021",
        document_url="https://www.alabamaachieves.org/files/ela.pdf",
    )
    proficiency = _existing(
        uuid4(),
        "alabama_ela_proficiency_grade_6",
        category_key="ela_proficiency_grade_6",
        category_name="Grade 6 ELA Proficiency Scale",
        title="Grade 6 ELA Proficiency Scale",
        edition="2025",
        document_url="https://www.alabamaachieves.org/files/grade-6-proficiency.pdf",
        source_kind="proficiency_scale",
    )
    client = FakeClient(
        [
            _existing(
                ELA_ID,
                ela.source_key,
                category_key=ela.category_key,
                category_name=ela.category_name,
                title=ela.title,
                edition=ela.edition,
                document_url=ela.document_url,
            ),
            proficiency,
        ]
    )

    result = reconcile_and_record_catalog(client, (ela,), trigger_kind="manual")

    assert result.missing_count == 0
    evidence_call = next(
        call
        for call in client.calls
        if call[0] == "POST" and call[1] == "standard_catalog_discovery_items"
    )
    evidence = evidence_call[3]
    assert isinstance(evidence, list)
    assert [item["source_key"] for item in evidence] == [ela.source_key]


def test_catalog_hash_is_stable_across_discovery_order() -> None:
    one = _discovered(
        "alabama_academic_science",
        category_key="science",
        category_name="Science",
        title="2024 Alabama Course of Study: Science",
        edition="2024",
        document_url="https://www.alabamaachieves.org/files/science.pdf",
    )
    two = _discovered(
        "alabama_academic_mathematics",
        category_key="mathematics",
        category_name="Mathematics",
        title="2019 Alabama Course of Study: Mathematics",
        edition="2019",
        document_url="https://www.alabamaachieves.org/files/math.pdf",
    )

    assert catalog_sha256((one, two)) == catalog_sha256((two, one))
    assert len(catalog_sha256((one, two))) == 64


def test_reconciliation_records_evidence_without_mutating_standard_sources() -> None:
    science = _discovered(
        "alabama_academic_science",
        category_key="science",
        category_name="Science",
        title="2024 Alabama Course of Study: Science",
        edition="2024",
        document_url="https://www.alabamaachieves.org/files/science-2024.pdf",
    )
    fake = FakeClient(
        [
            _existing(
                SCIENCE_ID,
                science.source_key,
                category_key=science.category_key,
                category_name=science.category_name,
                title="2023 Alabama Course of Study: Science",
                edition="2023",
                document_url="https://www.alabamaachieves.org/files/science-2023.pdf",
            )
        ]
    )

    result = reconcile_and_record_catalog(
        fake,
        (science,),
        check_month=__import__("datetime").date(2026, 8, 1),
        trigger_kind="scheduled",
    )

    assert result.run_id == RUN_ID
    assert result.changed_count == 1
    assert result.new_count == 0
    run_call = next(call for call in fake.calls if call[1] == "standard_catalog_discovery_runs")
    assert run_call[3]["trigger_kind"] == "scheduled"
    assert run_call[3]["changed_count"] == 1
    items_call = next(call for call in fake.calls if call[1] == "standard_catalog_discovery_items")
    assert items_call[3][0]["result_state"] == "changed"
    assert items_call[3][0]["existing_source_id"] == str(SCIENCE_ID)
    assert not any(
        call[0] in {"PATCH", "PUT", "DELETE"} and call[1] == "standard_sources"
        for call in fake.calls
    )
    assert not any(
        call[0] == "POST" and call[1] == "standard_sources"
        for call in fake.calls
    )


def test_reconciliation_marks_run_error_when_item_evidence_write_fails() -> None:
    science = _discovered(
        "alabama_academic_science",
        category_key="science",
        category_name="Science",
        title="2024 Alabama Course of Study: Science",
        edition="2024",
        document_url="https://www.alabamaachieves.org/files/science-2024.pdf",
    )
    fake = FailingItemClient([])

    with pytest.raises(
        StandardsCatalogReconcileError,
        match="discovery items could not be recorded",
    ):
        reconcile_and_record_catalog(fake, (science,))

    patch_call = next(
        call
        for call in fake.calls
        if call[0] == "PATCH" and call[1] == "standard_catalog_discovery_runs"
    )
    assert patch_call[2] == {"id": f"eq.{RUN_ID}"}
    assert patch_call[3] == {
        "status": "error",
        "error_summary": "Standards catalog discovery items could not be recorded",
    }
