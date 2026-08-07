import pytest

from app.standards_sources import (
    StandardsSourceResolutionError,
    _Anchor,
    resolve_from_anchors,
)


def test_ela_resolver_prefers_latest_authoritative_pdf() -> None:
    resolved = resolve_from_anchors(
        "alabama_ela_current",
        "https://www.alabamaachieves.org/content-areas-specialty/english-language-arts/",
        (
            _Anchor(
                href="/files/2016-Alabama-Course-of-Study-English-Language-Arts.pdf",
                text="2016 Course of Study",
            ),
            _Anchor(
                href=(
                    "/wp-content/uploads/2023/06/"
                    "AS_202353_2021-Alabama-Course-of-Study-English-Language-Arts_V1.0.pdf"
                ),
                text="2021 Alabama Course of Study: English Language Arts",
            ),
        ),
    )

    assert "2021-Alabama-Course-of-Study-English-Language-Arts" in resolved.document_url
    assert resolved.observed_version == "2021"


def test_bma_resolver_selects_business_management_course_of_study() -> None:
    resolved = resolve_from_anchors(
        "alabama_bma_current",
        "https://www.alabamaachieves.org/cte/cte-course-of-study/",
        (
            _Anchor(
                href="/wp-content/uploads/2021/08/2021-BMA-Course-of-StudyMARCH2021.pdf",
                text="Business Management and Administration",
            ),
            _Anchor(
                href="/wp-content/uploads/2024/01/2024-Marketing-Course-of-Study.pdf",
                text="Marketing",
            ),
        ),
    )

    assert resolved.document_url.endswith("2021-BMA-Course-of-StudyMARCH2021.pdf")
    assert resolved.observed_version == "2021"


def test_army_resolver_prefers_highest_curriculum_guide_version() -> None:
    resolved = resolve_from_anchors(
        "army_jrotc_current",
        "https://usarmyjrotc.army.mil/jsocc-course-documents/",
        (
            _Anchor(
                href="/wp-content/uploads/2024/02/JROTC-Curriculum-Guide-v11.docx",
                text="JROTC Curriculum Guide v11",
            ),
            _Anchor(
                href="/wp-content/uploads/2025/07/JROTC-Curriculum-Guide-25JUN25-4.docx",
                text="JROTC Curriculum Guide v12",
            ),
        ),
    )

    assert resolved.document_url.endswith("JROTC-Curriculum-Guide-25JUN25-4.docx")
    assert resolved.observed_version == "v12"


def test_resolver_rejects_document_link_outside_authoritative_hosts() -> None:
    with pytest.raises(StandardsSourceResolutionError, match="not allowlisted"):
        resolve_from_anchors(
            "army_jrotc_current",
            "https://usarmyjrotc.army.mil/jsocc-course-documents/",
            (
                _Anchor(
                    href="https://example.com/JROTC-Curriculum-Guide-v99.docx",
                    text="JROTC Curriculum Guide v99",
                ),
            ),
        )


def test_resolver_fails_closed_when_expected_link_disappears() -> None:
    with pytest.raises(StandardsSourceResolutionError, match="was not found"):
        resolve_from_anchors(
            "alabama_ela_current",
            "https://www.alabamaachieves.org/content-areas-specialty/english-language-arts/",
            (_Anchor(href="/unrelated.pdf", text="Unrelated document"),),
        )
