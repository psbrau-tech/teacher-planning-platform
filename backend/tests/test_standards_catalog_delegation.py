from app.standards_catalog_discovery import (
    discover_academic_sources,
    discover_cte_cos_sources,
)


def test_career_preparedness_academic_listing_is_delegated_to_cte_catalog() -> None:
    academic_html = """
    <html><body>
    <h3>Career Preparedness</h3><h4>Title</h4>
    <a href="/cte/2023-wbl.pdf">2023 WBL Course of Study</a>
    <a href="/cte/2023-career-prep.pdf">2023 Career Preparedness Course of Study</a>
    </body></html>
    """
    cte_html = """
    <html><body>
    <h3>General</h3><h4>Title</h4>
    <a href="/cte/2023-wbl.pdf">2023 WBL Course of Study</a>
    <a href="/cte/2023-career-prep.pdf">2023 Career Preparedness Course of Study</a>
    </body></html>
    """

    assert discover_academic_sources(academic_html) == ()
    cte_sources = discover_cte_cos_sources(cte_html)
    assert {source.source_key for source in cte_sources} == {
        "alabama_cte_cos_general_work_based_learning",
        "alabama_cte_cos_general_career_preparedness",
    }
