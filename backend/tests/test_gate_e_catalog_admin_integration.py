from datetime import date
from uuid import uuid4

from app import standards_monthly_run
from app.standards_catalog_discovery import DiscoveredStandardsSource
from app.standards_catalog_materialize import CatalogMaterializeResult
from app.standards_catalog_reconcile import CatalogReconcileItem, CatalogReconcileResult
from app.standards_maintenance import MaintenanceResult


def _discovered(source_key: str) -> DiscoveredStandardsSource:
    return DiscoveredStandardsSource(
        source_key=source_key,
        family="alabama_academic",
        category_key="science",
        category_name="Science",
        category_type="academic_subject",
        authority="Alabama State Department of Education",
        title=f"Synthetic {source_key}",
        edition="2026",
        landing_url="https://www.alabamaachieves.org/academic-standards/",
        document_url=f"https://www.alabamaachieves.org/files/{source_key}.pdf",
        document_format="pdf",
        parser_key_hint="synthetic",
        source_kind="course_of_study",
    )


def _maintenance(source_key: str) -> MaintenanceResult:
    return MaintenanceResult(
        source_key=source_key,
        status="unchanged",
        approved_snapshot_id=uuid4(),
        candidate_snapshot_id=None,
        observed_source_sha256="a" * 64,
        normalized_sha256="b" * 64,
        parser_succeeded=True,
        detail="Synthetic governed source is unchanged",
    )


def test_annual_full_materializes_changed_and_new_catalog_candidates(monkeypatch) -> None:
    changed = _discovered("alabama_academic_english_language_arts")
    new = _discovered("alabama_academic_science")
    unchanged = _discovered("alabama_academic_mathematics")
    catalog = CatalogReconcileResult(
        run_id=uuid4(),
        catalog_sha256="c" * 64,
        items=(
            CatalogReconcileItem(
                source_key=changed.source_key,
                state="changed",
                existing_source_id=uuid4(),
                discovered=changed,
                previous={"source_key": changed.source_key},
            ),
            CatalogReconcileItem(
                source_key=new.source_key,
                state="new",
                existing_source_id=None,
                discovered=new,
                previous=None,
            ),
            CatalogReconcileItem(
                source_key=unchanged.source_key,
                state="unchanged",
                existing_source_id=uuid4(),
                discovered=unchanged,
                previous={"source_key": unchanged.source_key},
            ),
        ),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "fetch_current_alabama_catalog",
        lambda: (changed, new, unchanged),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "reconcile_and_record_catalog",
        lambda client, discovered, check_month, trigger_kind: catalog,
    )

    staged: list[str] = []

    def materialize(client, discovered):
        staged.append(discovered.source_key)
        return CatalogMaterializeResult(
            source_key=discovered.source_key,
            status="candidate_staged",
            source_id=uuid4(),
            candidate_snapshot_id=uuid4(),
            parser_ready=True,
            parser_succeeded=True,
            detail="Synthetic candidate staged",
        )

    monkeypatch.setattr(standards_monthly_run, "materialize_discovered_source", materialize)
    monkeypatch.setattr(
        standards_monthly_run,
        "list_governed_source_keys",
        lambda client: ("existing_governed_source",),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "validate_governed_source",
        lambda client, source_key, check_month: _maintenance(source_key),
    )

    result = standards_monthly_run.run_standards_reconciliation(
        object(),
        check_date=date(2026, 8, 8),
        reconciliation_kind="annual_full",
        trigger_kind="manual",
    )

    assert staged == [changed.source_key, new.source_key]
    assert result.requires_review
    assert result.source_results[0].source_key == "existing_governed_source"


def test_quarterly_monitor_never_materializes_catalog_candidates(monkeypatch) -> None:
    new = _discovered("alabama_academic_science")
    catalog = CatalogReconcileResult(
        run_id=uuid4(),
        catalog_sha256="d" * 64,
        items=(
            CatalogReconcileItem(
                source_key=new.source_key,
                state="new",
                existing_source_id=None,
                discovered=new,
                previous=None,
            ),
        ),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "fetch_current_alabama_catalog",
        lambda: (new,),
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "reconcile_and_record_catalog",
        lambda client, discovered, check_month, trigger_kind: catalog,
    )

    def unexpected_materialization(client, discovered):
        raise AssertionError("quarterly monitoring must not materialize catalog candidates")

    monkeypatch.setattr(
        standards_monthly_run,
        "materialize_discovered_source",
        unexpected_materialization,
    )
    monkeypatch.setattr(
        standards_monthly_run,
        "validate_proficiency_source",
        lambda client, source_key, check_month: _maintenance(source_key),
    )

    result = standards_monthly_run.run_standards_reconciliation(
        object(),
        check_date=date(2026, 10, 1),
        reconciliation_kind="quarterly_monitor",
        trigger_kind="scheduled",
    )

    expected_keys = standards_monthly_run.proficiency_source_keys()
    assert tuple(item.source_key for item in result.source_results) == expected_keys
    assert result.requires_review
