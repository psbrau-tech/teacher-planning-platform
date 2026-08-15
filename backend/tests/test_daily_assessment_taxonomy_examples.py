from app.daily_assessment_analytics import classify_daily_assessment


def test_common_formative_assessment_phrases_map_transparently() -> None:
    examples = {
        "Exit ticket": ["exit_ticket"],
        "Quick write": ["quick_write"],
        "5-question quiz": ["quiz"],
        "Kahoot check": ["digital_check"],
        "Mini-whiteboards": ["whiteboard_response"],
        "Fist-to-five": ["response_signal"],
        "Think-pair-share discussion": ["questioning_discussion"],
        "Bellringer retrieval": ["retrieval_warmup"],
        "Teacher observation checklist": ["observation_conference"],
        "Peer review": ["peer_self_assessment"],
        "Performance demonstration": ["performance_demonstration"],
    }
    for phrase, expected in examples.items():
        assert classify_daily_assessment(phrase, "") == expected
