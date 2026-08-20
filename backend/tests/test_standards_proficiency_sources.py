from app.standards_sources import _Anchor, _AnchorParser, resolve_from_anchors


def test_grade_9_proficiency_resolver_prefers_revised_2024_source() -> None:
    resolved = resolve_from_anchors(
        "alabama_ela_proficiency_grade_9_current",
        "https://english-language-arts.alsde.edu/proficiency-scales",
        (
            _Anchor(
                href="https://drive.google.com/file/d/grade9-old/preview",
                text="9th Grade Proficiency Scales 2022",
            ),
            _Anchor(
                href="https://drive.google.com/file/d/grade9-current/preview",
                text="9th Grade Proficiency Scales Rev. 2024.docx - Google Docs.pdf",
            ),
            _Anchor(
                href="https://drive.google.com/file/d/grade10-current/preview",
                text="10th Grade Proficiency Scales.docx - Google Docs.pdf",
            ),
        ),
    )

    assert resolved.document_url == (
        "https://drive.google.com/uc?export=download&id=grade9-current"
    )
    assert resolved.observed_version == "2024"
    assert "Rev. 2024" in resolved.anchor_text


def test_grade_6_proficiency_resolver_uses_grade_context_from_google_site() -> None:
    resolved = resolve_from_anchors(
        "alabama_ela_proficiency_grade_6_current",
        "https://english-language-arts.alsde.edu/proficiency-scales",
        (
            _Anchor(
                href="https://drive.google.com/file/d/grade6/preview",
                text="Sixth Grade",
            ),
            _Anchor(
                href="https://drive.google.com/file/d/grade7/preview",
                text="Seventh Grade",
            ),
        ),
    )

    assert resolved.document_url.endswith("id=grade6")
    assert resolved.anchor_text == "Sixth Grade"


def test_google_sites_data_src_and_aria_label_become_document_candidate() -> None:
    parser = _AnchorParser()
    parser.feed(
        '<iframe aria-label="Drive, 6th Grade Proficiency Scales.docx - Google Docs.pdf" '
        'data-src="https://drive.google.com/file/d/current-grade-6/preview"></iframe>'
    )

    resolved = resolve_from_anchors(
        "alabama_ela_proficiency_grade_6_current",
        "https://english-language-arts.alsde.edu/proficiency-scales",
        parser.document_candidates(),
    )

    assert resolved.document_url.endswith("id=current-grade-6")
    assert "6th Grade Proficiency Scales" in resolved.anchor_text
