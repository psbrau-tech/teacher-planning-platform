from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

ACADEMIC_CATALOG_URL = "https://www.alabamaachieves.org/acad-stand/"
ALTERNATE_STANDARDS_CATALOG_URL = (
    "https://www.alabamaachieves.org/special-education/subject-resources/"
)
CTE_COS_CATALOG_URL = "https://www.alabamaachieves.org/cte/cte-course-of-study/"
CTE_PROGRAM_CATALOG_URL = "https://www.alabamaachieves.org/cte/"
ALABAMA_AUTHORITY = "Alabama State Department of Education"

_ALLOWED_HOSTS = frozenset({"www.alabamaachieves.org", "alabamaachieves.org"})
_IGNORED_ACADEMIC_CATEGORIES = frozenset(
    {
        "career preparedness",
        "supporting documents",
        "all standards and courses of study",
    }
)
_CATEGORY_ALIASES = {
    "agriculture_food_and_natural_resources": "agriculture_food_natural_resources",
    "architecture_and_construction": "architecture_construction",
    "art_a_v_technology_and_communications": "arts_av_technology_communications",
    "arts_a_v_technology_and_communications": "arts_av_technology_communications",
    "business_management_and_administration": "business_management_administration",
    "digital_literacy_and_computer_science": "digital_literacy_computer_science",
    "driver_and_traffic_safety_education": "driver_traffic_safety",
    "education_and_training": "education_training",
    "foreign_languages": "world_languages",
    "government_and_public_administration": "government_public_administration",
    "health_education": "health",
    "hospitality_and_tourism": "hospitality_tourism",
    "law_public_safety_corrections_and_security": "law_public_safety_corrections_security",
    "science_technology_engineering_and_mathematics": "stem",
    "transportation_distribution_and_logistics": "transportation_distribution_logistics",
}
_ALTERNATE_SPECS = {
    "english language arts – alternate achievement standards 2021": (
        "english_language_arts",
        "English Language Arts",
        "2021",
        "alabama_aas_ela_2021",
    ),
    "english language arts - alternate achievement standards 2021": (
        "english_language_arts",
        "English Language Arts",
        "2021",
        "alabama_aas_ela_2021",
    ),
    "math – alternate achievement standards": (
        "mathematics",
        "Mathematics",
        "2019",
        "alabama_aas_math_2019",
    ),
    "math - alternate achievement standards": (
        "mathematics",
        "Mathematics",
        "2019",
        "alabama_aas_math_2019",
    ),
    "science – alternative achievement standards": (
        "science",
        "Science",
        "2017",
        "alabama_aas_science_2017",
    ),
    "science - alternative achievement standards": (
        "science",
        "Science",
        "2017",
        "alabama_aas_science_2017",
    ),
    "social studies – alternate achievement standards": (
        "social_studies",
        "Social Studies",
        "2017",
        "alabama_aas_social_studies_2017",
    ),
    "social studies - alternate achievement standards": (
        "social_studies",
        "Social Studies",
        "2017",
        "alabama_aas_social_studies_2017",
    ),
}


class StandardsCatalogDiscoveryError(RuntimeError):
    """Bounded failure while reading the authoritative Alabama standards catalogs."""


@dataclass(frozen=True, slots=True)
class DiscoveredStandardsSource:
    source_key: str
    family: str
    category_key: str
    category_name: str
    category_type: str
    authority: str
    title: str
    edition: str
    landing_url: str
    document_url: str
    document_format: str
    parser_key_hint: str
    source_kind: str


@dataclass(frozen=True, slots=True)
class _CatalogLink:
    h3: str | None
    h4: str | None
    href: str
    text: str


class _CatalogParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[_CatalogLink] = []
        self._heading_tag: str | None = None
        self._heading_parts: list[str] = []
        self._h3: str | None = None
        self._h4: str | None = None
        self._href: str | None = None
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"h3", "h4"}:
            self._heading_tag = lowered
            self._heading_parts = []
            return
        if lowered != "a":
            return
        href = next((value for key, value in attrs if key.lower() == "href"), None)
        if href:
            self._href = href
            self._anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self._heading_tag is not None:
            self._heading_parts.append(data)
        if self._href is not None:
            self._anchor_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._heading_tag == lowered:
            heading = _clean(" ".join(self._heading_parts))
            if lowered == "h3":
                self._h3 = heading or None
                self._h4 = None
            else:
                self._h4 = heading or None
            self._heading_tag = None
            self._heading_parts = []
        if lowered == "a" and self._href is not None:
            text = _clean(" ".join(self._anchor_parts))
            if text:
                self.links.append(
                    _CatalogLink(
                        h3=self._h3,
                        h4=self._h4,
                        href=self._href,
                        text=text,
                    )
                )
            self._href = None
            self._anchor_parts = []


def discover_alabama_catalogs(
    *,
    academic_html: str,
    alternate_html: str,
    cte_cos_html: str,
    cte_program_html: str,
) -> tuple[DiscoveredStandardsSource, ...]:
    sources = (
        *discover_academic_sources(academic_html),
        *discover_alternate_sources(alternate_html),
        *discover_cte_cos_sources(cte_cos_html),
        *discover_cte_program_sources(cte_program_html),
    )
    deduped: dict[str, DiscoveredStandardsSource] = {}
    for source in sources:
        existing = deduped.get(source.source_key)
        if existing is None or _edition_rank(source.edition) > _edition_rank(existing.edition):
            deduped[source.source_key] = source
    return tuple(
        sorted(
            deduped.values(),
            key=lambda item: (item.family, item.category_name, item.source_key),
        )
    )


def discover_academic_sources(html: str) -> tuple[DiscoveredStandardsSource, ...]:
    links = _parse_links(html)
    candidates: list[DiscoveredStandardsSource] = []
    for link in links:
        category = _clean(link.h3 or "")
        if not category or category.lower() in _IGNORED_ACADEMIC_CATEGORIES:
            continue
        if not _is_course_of_study_link(link.text):
            continue
        if _is_instructional_companion(link.text):
            continue
        category_key = _category_key(category)
        logical_document_key = _academic_document_key(category_key, link.text)
        candidates.append(
            _source(
                source_key=f"alabama_academic_{logical_document_key}",
                family="alabama_academic",
                category_key=category_key,
                category_name=category,
                category_type="academic_subject",
                title=link.text,
                edition=_edition(link.text),
                landing_url=ACADEMIC_CATALOG_URL,
                href=link.href,
                parser_key_hint="alabama_cos_generic",
                source_kind="course_of_study",
            )
        )
    return _latest_logical_sources(candidates)


def discover_alternate_sources(html: str) -> tuple[DiscoveredStandardsSource, ...]:
    links = _parse_links(html)
    discovered: dict[str, DiscoveredStandardsSource] = {}
    for link in links:
        if _clean(link.h3 or "").casefold() != "standards and courses of study":
            continue
        normalized_title = _clean(link.text).casefold()
        spec = _ALTERNATE_SPECS.get(normalized_title)
        if spec is None:
            continue
        category_key, category_name, edition, parser_key = spec
        source_key = f"alabama_alternate_{category_key}"
        discovered[source_key] = _source(
            source_key=source_key,
            family="alabama_alternate",
            category_key=category_key,
            category_name=category_name,
            category_type="alternate_achievement_subject",
            title=link.text,
            edition=edition,
            landing_url=ALTERNATE_STANDARDS_CATALOG_URL,
            href=link.href,
            parser_key_hint=parser_key,
            source_kind="alternate_achievement_standards",
        )
    return tuple(sorted(discovered.values(), key=lambda item: item.source_key))


def discover_cte_cos_sources(html: str) -> tuple[DiscoveredStandardsSource, ...]:
    links = _parse_links(html)
    candidates: list[DiscoveredStandardsSource] = []
    for link in links:
        category = _clean(link.h3 or "")
        if not category or not _is_course_of_study_link(link.text):
            continue
        category_key = _category_key(category)
        logical_document_key = _cte_cos_document_key(category_key, link.text)
        candidates.append(
            _source(
                source_key=f"alabama_cte_cos_{logical_document_key}",
                family="alabama_cte",
                category_key=category_key,
                category_name=category,
                category_type="career_cluster" if category.lower() != "general" else "general",
                title=link.text,
                edition=_edition(link.text),
                landing_url=CTE_COS_CATALOG_URL,
                href=link.href,
                parser_key_hint="alabama_cte_cos_generic",
                source_kind="course_of_study",
            )
        )
    return _latest_logical_sources(candidates)


def discover_cte_program_sources(html: str) -> tuple[DiscoveredStandardsSource, ...]:
    links = _parse_links(html)
    candidates: list[DiscoveredStandardsSource] = []
    for link in links:
        if _clean(link.h3 or "").lower() != "program guides":
            continue
        category = _clean(link.h4 or "")
        if not category or "program guide" not in link.text.lower():
            continue
        category_key = _category_key(category)
        logical_program_key = _program_document_key(category_key, link.text)
        candidates.append(
            _source(
                source_key=f"alabama_cte_program_{logical_program_key}",
                family="alabama_cte_program",
                category_key=category_key,
                category_name=category,
                category_type="career_cluster",
                title=link.text,
                edition=_edition(link.text),
                landing_url=CTE_PROGRAM_CATALOG_URL,
                href=link.href,
                parser_key_hint="alabama_cte_program_generic",
                source_kind="program_guide",
            )
        )
    return _latest_logical_sources(candidates)


def _parse_links(html: str) -> tuple[_CatalogLink, ...]:
    parser = _CatalogParser()
    try:
        parser.feed(html)
    except Exception as error:
        raise StandardsCatalogDiscoveryError(
            "Authoritative Alabama standards catalog could not be parsed"
        ) from error
    return tuple(parser.links)


def _source(
    *,
    source_key: str,
    family: str,
    category_key: str,
    category_name: str,
    category_type: str,
    title: str,
    edition: str,
    landing_url: str,
    href: str,
    parser_key_hint: str,
    source_kind: str,
) -> DiscoveredStandardsSource:
    document_url = urljoin(landing_url, href)
    _require_allowed_url(document_url)
    document_format = _document_format(document_url)
    return DiscoveredStandardsSource(
        source_key=source_key,
        family=family,
        category_key=category_key,
        category_name=category_name,
        category_type=category_type,
        authority=ALABAMA_AUTHORITY,
        title=title,
        edition=edition,
        landing_url=landing_url,
        document_url=document_url,
        document_format=document_format,
        parser_key_hint=parser_key_hint,
        source_kind=source_kind,
    )


def _require_allowed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise StandardsCatalogDiscoveryError(
            "Authoritative Alabama standards URL is not allowlisted"
        )


def _document_format(url: str) -> str:
    path = urlparse(url).path.lower()
    if path.endswith(".pdf"):
        return "pdf"
    if path.endswith(".docx"):
        return "docx"
    # Alabama catalog links occasionally route through a CMS path without an extension.
    # The maintenance fetch path resolves redirects/content type before source activation.
    return "unknown"


def _is_course_of_study_link(text: str) -> bool:
    lowered = text.lower()
    return (
        "course of study" in lowered
        or lowered in {"algebra with finance", "career mathematics"}
    )


def _is_instructional_companion(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in (
            "differentiated instructional guide",
            "instructional guide",
            "companion",
        )
    )


def _academic_document_key(category_key: str, title: str) -> str:
    lowered = title.lower()
    if "algebra with finance" in lowered:
        return "mathematics_algebra_with_finance"
    if "career mathematics" in lowered:
        return "mathematics_career_mathematics"
    return category_key


def _cte_cos_document_key(category_key: str, title: str) -> str:
    lowered = title.lower()
    if "cosmetology" in lowered:
        return "human_services_cosmetology"
    if category_key == "general" and "career preparedness" in lowered:
        return "general_career_preparedness"
    if category_key == "general" and ("wbl" in lowered or "work-based" in lowered):
        return "general_work_based_learning"
    return category_key


def _program_document_key(category_key: str, title: str) -> str:
    lowered = title.lower()
    if category_key == "architecture_construction" and "academy of craft" in lowered:
        return "architecture_construction_academy_of_craft_training"
    if category_key == "human_services" and "cosmetology" in lowered:
        return "human_services_cosmetology"
    return category_key


def _latest_logical_sources(
    candidates: list[DiscoveredStandardsSource],
) -> tuple[DiscoveredStandardsSource, ...]:
    selected: dict[str, DiscoveredStandardsSource] = {}
    for candidate in candidates:
        existing = selected.get(candidate.source_key)
        if existing is None or _edition_rank(candidate.edition) > _edition_rank(existing.edition):
            selected[candidate.source_key] = candidate
    return tuple(sorted(selected.values(), key=lambda item: item.source_key))


def _edition(text: str) -> str:
    school_years = re.findall(r"(20\d{2})\s*[-–]\s*(20\d{2})", text)
    if school_years:
        start, end = school_years[-1]
        return f"{start}-{end}"
    years = re.findall(r"20\d{2}", text)
    return years[-1] if years else "current-undated"


def _edition_rank(value: str) -> tuple[int, int]:
    years = [int(year) for year in re.findall(r"20\d{2}", value)]
    if not years:
        return (0, 0)
    return (years[0], years[-1])


def _category_key(value: str) -> str:
    slug = _slug(value)
    return _CATEGORY_ALIASES.get(slug, slug)


def _slug(value: str) -> str:
    normalized = value.lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "catalog"


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
