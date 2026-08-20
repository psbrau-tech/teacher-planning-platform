from pathlib import Path

LIVE_STANDARDS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "StandardsPanel.tsx"
)


def test_mapped_standards_course_uses_one_group_and_keeps_strand_badges() -> None:
    source = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert "function mappedStandardsLabel" in source
    assert "catalog.catalog_course?.display_name" in source
    assert "standardsCourseLabel" in source
    assert 'standardsCourseLabel ? <details className="standard-group" open>' in source
    assert "visibleStandards.map(renderStandard)" in source
    assert 'standard.strand ? <span className="badge">{standard.strand}</span>' in source
    assert "catalog.catalog_category.display_name" in source
    assert "catalog.catalog_course.display_name" in source


def test_legacy_unmapped_course_shape_keeps_existing_grouping_fallback() -> None:
    source = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert "function standardGroup" in source
    assert "Unit ${match[1]} · Chapter ${match[2]}" in source
    assert "groupedStandards.map(([group, standards])" in source
