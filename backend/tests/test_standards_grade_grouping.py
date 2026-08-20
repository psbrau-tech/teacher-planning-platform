from pathlib import Path


LIVE_STANDARDS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "StandardsPanel.tsx"
)


def test_grade_mapped_standards_use_one_grade_group_and_keep_strand_badges() -> None:
    source = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert "function mappedGradeLabel" in source
    assert "Grade ${numericGrade} Standards" in source
    assert "standardsGradeLabel" in source
    assert 'standardsGradeLabel ? <details className="standard-group" open>' in source
    assert "visibleStandards.map(renderStandard)" in source
    assert 'standard.strand ? <span className="badge">{standard.strand}</span>' in source


def test_non_grade_courses_keep_existing_strand_or_unit_fallback_grouping() -> None:
    source = LIVE_STANDARDS.read_text(encoding="utf-8")

    assert "function standardGroup" in source
    assert "Unit ${match[1]} · Chapter ${match[2]}" in source
    assert "groupedStandards.map(([group, standards])" in source
