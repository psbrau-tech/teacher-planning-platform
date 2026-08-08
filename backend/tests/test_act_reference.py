from app.act_reference import ActReferenceError, load_act_candidate_entries, parse_act_ccr_html


class FakeClient:
    def request(self, method, resource, *, params=None, payload=None, prefer=None):
        assert method == "GET"
        assert resource == "act_reference_entries"
        return [
            {
                "reference_code": "CLR 401",
                "domain": "Reading",
                "category": "CLR",
                "score_range": "20-23",
                "exact_text": "Locate important details in somewhat challenging passages",
            },
            {
                "reference_code": "IOD 401",
                "domain": "Science",
                "category": "IOD",
                "score_range": "20-23",
                "exact_text": "Select data from a complex data presentation",
            },
        ]


def test_act_parser_preserves_codes_text_and_score_range() -> None:
    html = """
    <html><body><table><tr><td>
      CLR 201. Locate basic facts in a passage.
      CLR 301. Locate simple details in a passage.
      CLR 401. Locate important details in a passage.
      CLR 501. Locate subtly stated details in a passage.
      CLR 601. Locate important details in complex passages.
      CLR 701. Locate details in highly complex passages.
      IDT 201. Identify a topic.
      IDT 301. Identify a central idea.
      IDT 401. Infer a central idea.
      IDT 501. Infer a theme.
      IDT 601. Summarize supporting ideas.
      IDT 701. Identify a theme in a complex passage.
    </td></tr></table></body></html>
    """
    parsed = parse_act_ccr_html(
        source_key="act_ccrs_reading",
        domain="Reading",
        raw_html=html,
    )
    assert parsed.parser_version == "act-public-html-v1"
    assert len(parsed.entries) == 12
    assert parsed.entries[2].reference_code == "CLR 401"
    assert parsed.entries[2].score_range == "20-23"
    assert parsed.entries[2].exact_text == "Locate important details in a passage."


def test_act_parser_rejects_conflicting_reference_codes() -> None:
    html = (
        "<p>"
        + " ".join(
            [
                "CLR 201. One.",
                "CLR 301. Two.",
                "CLR 401. Three.",
                "CLR 501. Four.",
                "CLR 601. Five.",
                "CLR 701. Six.",
                "IDT 201. Seven.",
                "IDT 301. Eight.",
                "IDT 401. Nine.",
                "IDT 501. Ten.",
                "IDT 601. Eleven.",
                "CLR 401. Duplicate.",
            ]
        )
        + "</p>"
    )
    try:
        parse_act_ccr_html(source_key="act_ccrs_reading", domain="Reading", raw_html=html)
    except ActReferenceError as error:
        assert "Conflicting ACT reference wording" in str(error)
    else:
        raise AssertionError("conflicting ACT reference codes must fail closed")


def test_act_candidate_selection_is_bounded_and_lexical() -> None:
    rows = load_act_candidate_entries(
        FakeClient(),
        "Students will locate important textual details and cite evidence from a passage.",
        limit=1,
    )
    assert [row["reference_code"] for row in rows] == ["CLR 401"]
