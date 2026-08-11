import pytest

from app.standards import StandardsFamily, source_for


def test_initial_sources_cover_academic_alternate_cte_and_jrotc() -> None:
    english = source_for(StandardsFamily.ALABAMA_ACADEMIC, "English Language Arts")
    alternate_english = source_for(
        StandardsFamily.ALABAMA_ALTERNATE,
        "English Language Arts",
    )
    alternate_math = source_for(StandardsFamily.ALABAMA_ALTERNATE, "Mathematics")
    alternate_science = source_for(StandardsFamily.ALABAMA_ALTERNATE, "Science")
    alternate_social = source_for(StandardsFamily.ALABAMA_ALTERNATE, "Social Studies")
    business = source_for(
        StandardsFamily.ALABAMA_CTE,
        "Business Management and Administration",
    )
    jrotc = source_for(StandardsFamily.ARMY_JROTC, "Army JROTC LET 1-4")

    assert english.edition.startswith("2021")
    assert alternate_english.edition.startswith("2021")
    assert alternate_math.edition.startswith("2019")
    assert alternate_science.edition.startswith("2017")
    assert alternate_social.edition.startswith("2017")
    assert business.edition == "2021 BMA Course of Study"
    assert jrotc.authority == "U.S. Army JROTC"


def test_unknown_source_is_not_silently_invented() -> None:
    with pytest.raises(LookupError, match="No standards source registered"):
        source_for(StandardsFamily.ALABAMA_CTE, "Unknown Cluster")
