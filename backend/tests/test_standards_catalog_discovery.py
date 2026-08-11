import pytest

from app.standards_catalog_discovery import (
    StandardsCatalogDiscoveryError,
    discover_academic_sources,
    discover_alabama_catalogs,
    discover_alternate_sources,
    discover_cte_cos_sources,
    discover_cte_program_sources,
)

ACADEMIC_HTML = """
<html><body>
<h3>English Language Arts</h3><h4>Title</h4>
<a href="/files/2021-ela.pdf">2021 Alabama Course of Study: English Language Arts</a>
<a href="/files/ela-dig.pdf">English Language Arts K-12: Differentiated
Instructional Guide (DIG)</a>
<h3>Arts Education</h3><h4>Title</h4>
<a href="/files/2024-arts.pdf">2024 Arts Education Course of Study</a>
<a href="/files/2017-arts.pdf">2017 Arts Education Course of Study</a>
<h3>Digital Literacy and Computer Science</h3><h4>Title</h4>
<a href="/files/2025-dlcs.pdf">2025 Alabama Course of Study: Digital Literacy
and Computer Science</a>
<a href="/files/2018-dlcs.pdf">2018 Alabama Course of Study: Digital Literacy
and Computer Science</a>
<h3>Mathematics</h3><h4>Title</h4>
<a href="/files/2019-math.pdf">2019 Alabama Course of Study: Mathematics</a>
<a href="/files/algebra-finance.pdf">Algebra with Finance</a>
<a href="/files/career-math.pdf">Career Mathematics</a>
<h3>Science</h3><h4>Title</h4>
<a href="/files/2023-science.pdf">2023 Alabama Course of Study: Science</a>
<a href="/files/2015-science.pdf">2015 Alabama Course of Study: Science</a>
<h3>Social Studies</h3><h4>Title</h4>
<a href="/files/2024-social.pdf">2024 Alabama Course of Study: Social Studies</a>
<h3>Supporting Documents</h3><h4>Title</h4>
<a href="/files/support.pdf">2026 Supporting Course of Study Notes</a>
</body></html>
"""

ALTERNATE_HTML = """
<html><body>
<h3>Standards and Courses of Study</h3><h4>Title</h4>
<a href="/files/2021-aas-ela.pdf">English Language Arts – Alternate Achievement Standards 2021</a>
<a href="/files/2017-aas-ela.pdf">English Language Arts – Alternate Achievement Standards</a>
<a href="/files/2019-aas-math.pdf">Math – Alternate Achievement Standards</a>
<a href="/files/2017-aas-science.pdf">Science – Alternative Achievement Standards</a>
<a href="/files/2017-aas-social.pdf">Social Studies – Alternate Achievement Standards</a>
<h3>Assistive Technology</h3><h4>Title</h4>
<a href="/files/unrelated.pdf">Alternate Format Textbooks</a>
</body></html>
"""

CTE_COS_HTML = """
<html><body>
<h3>General</h3><h4>Title</h4>
<a href="/cte/2023-wbl.pdf">2023 WBL Course of Study</a>
<a href="/cte/2023-career-prep.pdf">2023 Career Preparedness Course of Study</a>
<h3>Business Management and Administration</h3><h4>Title</h4>
<a href="/cte/2021-bma.pdf">2021 BMA Course of Study</a>
<h3>Human Services</h3><h4>Title</h4>
<a href="/cte/2024-human-services.pdf">2024 Alabama Course of Study: Human Services</a>
<a href="/cte/2022-cosmetology.pdf">2022 Alabama Course of Study: Cosmetology</a>
<h3>Art, A/V Technology and Communications</h3><h4>Title</h4>
<a href="/cte/2023-av.pdf">2023 Alabama Course of Study: Arts, A-V Technology,
and Communications</a>
<a href="/cte/2008-generic.pdf">2008 Alabama Course of Study Career and Technical Education</a>
</body></html>
"""

CTE_PROGRAM_HTML = """
<html><body>
<h3>Equipment Lists</h3>
<h4>Government &amp; Public Administration</h4>
<a href="/cte/jrotc-equipment.pdf">JROTC</a>
<h3>Program Guides</h3>
<h4>Government &amp; Public Administration</h4>
<a href="/cte/gpa-2025-2026.pdf">Government Public Admin Program Guide 2025-2026</a>
<a href="/cte/gpa-2024-2025.pdf">Government Public Admin Program Guide 2024-2025</a>
<h4>Human Services</h4>
<a href="/cte/cosmo-2025-2026.pdf">Cosmetology Program Guide 2025-2026</a>
<a href="/cte/human-2025-2026.pdf">Human Services Program Guide 2025-2026</a>
<h4>Architecture &amp; Construction</h4>
<a href="/cte/craft-2025-2026.pdf">Academy of Craft Training Program Guide 2025-2026</a>
<a href="/cte/architecture-2025-2026.pdf">Architecture and Construction Program Guide 2025-2026</a>
</body></html>
"""


def test_academic_discovery_keeps_current_course_studies_and_distinct_math_courses() -> None:
    sources = discover_academic_sources(ACADEMIC_HTML)
    by_key = {source.source_key: source for source in sources}

    assert by_key["alabama_academic_english_language_arts"].edition == "2021"
    assert by_key["alabama_academic_arts_education"].edition == "2024"
    assert by_key["alabama_academic_digital_literacy_computer_science"].edition == "2025"
    assert by_key["alabama_academic_science"].edition == "2023"
    assert by_key["alabama_academic_social_studies"].edition == "2024"
    assert "alabama_academic_mathematics" in by_key
    assert "alabama_academic_mathematics_algebra_with_finance" in by_key
    assert "alabama_academic_mathematics_career_mathematics" in by_key
    assert all("instructional" not in source.title.lower() for source in sources)
    assert all(source.category_name != "Supporting Documents" for source in sources)


def test_alternate_discovery_keeps_four_current_aas_subjects_and_ignores_retired_ela() -> None:
    sources = discover_alternate_sources(ALTERNATE_HTML)
    by_key = {source.source_key: source for source in sources}

    assert set(by_key) == {
        "alabama_alternate_english_language_arts",
        "alabama_alternate_mathematics",
        "alabama_alternate_science",
        "alabama_alternate_social_studies",
    }
    assert by_key["alabama_alternate_english_language_arts"].edition == "2021"
    assert by_key["alabama_alternate_english_language_arts"].parser_key_hint == (
        "alabama_aas_ela_2021"
    )
    assert by_key["alabama_alternate_mathematics"].edition == "2019"
    assert by_key["alabama_alternate_science"].edition == "2017"
    assert by_key["alabama_alternate_social_studies"].edition == "2017"
    assert all(source.family == "alabama_alternate" for source in sources)
    assert all(source.source_kind == "alternate_achievement_standards" for source in sources)


def test_cte_cos_discovery_keeps_distinct_general_and_human_services_sources() -> None:
    sources = discover_cte_cos_sources(CTE_COS_HTML)
    by_key = {source.source_key: source for source in sources}

    assert "alabama_cte_cos_general_work_based_learning" in by_key
    assert "alabama_cte_cos_general_career_preparedness" in by_key
    assert "alabama_cte_cos_business_management_administration" in by_key
    assert "alabama_cte_cos_human_services" in by_key
    assert "alabama_cte_cos_human_services_cosmetology" in by_key
    assert by_key["alabama_cte_cos_human_services"].category_type == "career_cluster"
    assert by_key["alabama_cte_cos_business_management_administration"].category_key == (
        "business_management_administration"
    )


def test_cte_program_discovery_uses_latest_guide_and_keeps_distinct_program_families() -> None:
    sources = discover_cte_program_sources(CTE_PROGRAM_HTML)
    by_key = {source.source_key: source for source in sources}

    government = by_key["alabama_cte_program_government_public_administration"]
    assert government.edition == "2025-2026"
    assert government.category_name == "Government & Public Administration"
    assert government.category_key == "government_public_administration"
    assert government.source_kind == "program_guide"
    assert "2024-2025" not in government.document_url

    assert "alabama_cte_program_human_services_cosmetology" in by_key
    assert "alabama_cte_program_human_services" in by_key
    assert "alabama_cte_program_architecture_construction_academy_of_craft_training" in by_key
    assert "alabama_cte_program_architecture_construction" in by_key
    assert all("equipment" not in source.title.lower() for source in sources)


def test_combined_catalog_deduplicates_by_stable_logical_source_key() -> None:
    sources = discover_alabama_catalogs(
        academic_html=ACADEMIC_HTML,
        alternate_html=ALTERNATE_HTML,
        cte_cos_html=CTE_COS_HTML,
        cte_program_html=CTE_PROGRAM_HTML,
    )

    keys = [source.source_key for source in sources]
    assert len(keys) == len(set(keys))
    assert any(source.family == "alabama_academic" for source in sources)
    assert any(source.family == "alabama_alternate" for source in sources)
    assert any(source.family == "alabama_cte" for source in sources)
    assert any(source.family == "alabama_cte_program" for source in sources)


def test_discovery_rejects_document_links_outside_alabama_allowlist() -> None:
    html = """
    <h3>Science</h3><h4>Title</h4>
    <a href="https://example.com/science.pdf">2026 Alabama Course of Study: Science</a>
    """

    with pytest.raises(StandardsCatalogDiscoveryError):
        discover_academic_sources(html)
