import pytest

from app.standards import StandardsFamily, source_for


def test_initial_sources_cover_academic_cte_and_jrotc() -> None:
    english = source_for(StandardsFamily.ALABAMA_ACADEMIC, "English Language Arts")
    business = source_for(
        StandardsFamily.ALABAMA_CTE,
        "Business Management and Administration",
    )
    jrotc = source_for(StandardsFamily.ARMY_JROTC, "Army JROTC LET 1-4")

    assert english.edition.startswith("2021")
    assert business.edition == "2021 BMA Course of Study"
    assert jrotc.authority == "U.S. Army JROTC"


def test_unknown_source_is_not_silently_invented() -> None:
    with pytest.raises(LookupError, match="No standards source registered"):
        source_for(StandardsFamily.ALABAMA_CTE, "Unknown Cluster")
