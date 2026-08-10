from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StandardsFamily(StrEnum):
    ALABAMA_ACADEMIC = "alabama_academic"
    ALABAMA_ALTERNATE = "alabama_alternate"
    ALABAMA_CTE = "alabama_cte"
    ARMY_JROTC = "army_jrotc"


@dataclass(frozen=True, slots=True)
class StandardsSource:
    family: StandardsFamily
    subject_or_cluster: str
    edition: str
    effective_school_year: str | None
    source_url: str
    authority: str


_ALTERNATE_SOURCE_URL = "https://www.alabamaachieves.org/special-education/subject-resources/"

INITIAL_STANDARDS_SOURCES = (
    StandardsSource(
        family=StandardsFamily.ALABAMA_ACADEMIC,
        subject_or_cluster="English Language Arts",
        edition="2021 Alabama Course of Study: English Language Arts",
        effective_school_year="2022-2023",
        source_url="https://www.alabamaachieves.org/acad-stand/",
        authority="Alabama State Department of Education",
    ),
    StandardsSource(
        family=StandardsFamily.ALABAMA_ALTERNATE,
        subject_or_cluster="English Language Arts",
        edition="2021 Alternate Achievement Standards: English Language Arts",
        effective_school_year=None,
        source_url=_ALTERNATE_SOURCE_URL,
        authority="Alabama State Department of Education",
    ),
    StandardsSource(
        family=StandardsFamily.ALABAMA_ALTERNATE,
        subject_or_cluster="Mathematics",
        edition="2019 Alternate Achievement Standards: Mathematics",
        effective_school_year=None,
        source_url=_ALTERNATE_SOURCE_URL,
        authority="Alabama State Department of Education",
    ),
    StandardsSource(
        family=StandardsFamily.ALABAMA_ALTERNATE,
        subject_or_cluster="Science",
        edition="2017 Alternate Achievement Standards: Science",
        effective_school_year=None,
        source_url=_ALTERNATE_SOURCE_URL,
        authority="Alabama State Department of Education",
    ),
    StandardsSource(
        family=StandardsFamily.ALABAMA_ALTERNATE,
        subject_or_cluster="Social Studies",
        edition="2017 Alternate Achievement Standards: Social Studies",
        effective_school_year=None,
        source_url=_ALTERNATE_SOURCE_URL,
        authority="Alabama State Department of Education",
    ),
    StandardsSource(
        family=StandardsFamily.ALABAMA_CTE,
        subject_or_cluster="Business Management and Administration",
        edition="2021 BMA Course of Study",
        effective_school_year=None,
        source_url="https://www.alabamaachieves.org/cte/cte-course-of-study/",
        authority="Alabama State Department of Education",
    ),
    StandardsSource(
        family=StandardsFamily.ARMY_JROTC,
        subject_or_cluster="Army JROTC LET 1-4",
        edition="Current JROTC Curriculum Guide",
        effective_school_year=None,
        source_url="https://usarmyjrotc.army.mil/curriculum/",
        authority="U.S. Army JROTC",
    ),
)


def source_for(family: StandardsFamily, subject_or_cluster: str) -> StandardsSource:
    for source in INITIAL_STANDARDS_SOURCES:
        if source.family == family and source.subject_or_cluster == subject_or_cluster:
            return source
    raise LookupError(f"No standards source registered for {family}: {subject_or_cluster}")
