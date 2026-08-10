from pathlib import Path

from app.standards_catalog_discovery import discover_alternate_sources

MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
AAS_CATALOG_GOVERNANCE = (
    MIGRATIONS / "20260810232500_alabama_alternate_catalog_governance.sql"
)

ALTERNATE_HTML = """
<html><body>
<h3>Standards and Courses of Study</h3><h4>Title</h4>
<a href="/files/2021-aas-ela.pdf">English Language Arts – Alternate Achievement Standards 2021</a>
<a href="/files/2019-aas-math.pdf">Math – Alternate Achievement Standards</a>
<a href="/files/2017-aas-science.pdf">Science – Alternative Achievement Standards</a>
<a href="/files/2017-aas-social.pdf">Social Studies – Alternate Achievement Standards</a>
</body></html>
"""


def test_aas_discovery_contract_is_supported_by_catalog_schema() -> None:
    sources = discover_alternate_sources(ALTERNATE_HTML)
    migration = AAS_CATALOG_GOVERNANCE.read_text(encoding="utf-8")

    assert len(sources) == 4
    assert all(source.family == "alabama_alternate" for source in sources)
    assert all(source.category_type == "alternate_achievement_subject" for source in sources)
    assert all(source.source_kind == "alternate_achievement_standards" for source in sources)

    assert "'alternate_achievement_subject'" in migration
    assert "'alternate_achievement_standards'" in migration
    assert "standard_catalog_discovery_item_category_type" in migration
    assert "standard_sources_catalog_category_type" in migration
    assert "standard_sources_source_kind" in migration
    assert "standard_catalog_category_type" in migration


def test_aas_approval_projection_stays_distinct_from_general_academic_catalog() -> None:
    migration = AAS_CATALOG_GOVERNANCE.read_text(encoding="utf-8")

    assert "src.source_kind in ('course_of_study', 'alternate_achievement_standards')" in migration
    assert "then 'primary'" in migration
    assert "projected_category_key := 'alternate_achievement_' || src.catalog_category_key" in migration
    assert (
        "projected_category_name := src.catalog_category_name || "
        "' — Alternate Achievement Standards'"
    ) in migration
    assert "projected_category_type := 'alternate_achievement_subject'" in migration


def test_aas_catalog_migration_repairs_only_incomplete_discovery_evidence() -> None:
    migration = AAS_CATALOG_GOVERNANCE.read_text(encoding="utf-8")

    assert "where r.status = 'completed'" in migration
    assert "and r.discovered_source_count > 0" in migration
    assert "not exists" in migration
    assert "where i.run_id = r.id" in migration
    assert "set status = 'error'" in migration
    assert "orphaned_catalog_run_without_items" in migration

    # This migration expands governed schema/projection only. Snapshot approval remains a
    # separate platform-administrator action and is never performed automatically here.
    assert "set status = 'approved'" not in migration
    assert "approved_snapshot_id =" not in migration
