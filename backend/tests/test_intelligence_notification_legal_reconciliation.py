from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI_NOTICE = ROOT / "docs" / "legal" / "AI_USE_AND_ACCURACY_NOTICE.md"
PRIVACY = ROOT / "docs" / "legal" / "PRIVACY_POLICY.md"
SUBPROCESSORS = ROOT / "docs" / "legal" / "SUBPROCESSORS.md"
SECURITY = ROOT / "docs" / "legal" / "SECURITY_AND_DATA_PRACTICES.md"
COUNSEL = ROOT / "docs" / "legal" / "COUNSEL_REVIEW_BRIEF_2026-08-13.md"
HELP = ROOT / "frontend" / "src" / "HelpPage.tsx"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_ai_notice_preserves_teacher_authorship_of_required_reflection() -> None:
    source = normalized(AI_NOTICE)

    assert "teacher-authored weekly reflection / plc discussion" in source
    assert "does not use generative ai to suggest, generate, complete, or rewrite" in source
    assert "submitted professional reflections" in source
    assert "do not replace the underlying teacher-authored reflection" in source
    assert "teacher-quality" in source
    assert "student data" in source

    # This was the stale pre-Reflection-Intelligence wording in the legal packet.
    assert "weekly reflections, and other planning fields" not in source


def test_counsel_brief_distinguishes_deployed_state_from_unactivated_email_work() -> None:
    source = normalized(COUNSEL)

    assert "weekly reflection / plc discussion remains teacher-authored" in source
    assert "does not use generative ai to suggest, generate, complete, or rewrite" in source
    assert "source-controlled notification infrastructure not yet activated" in source
    assert "send pilot/production email" in source
    assert "activation still requires separate human-controlled" in source
    assert "notifications@planner.guidedscholar.ai" in source
    assert "planned formative-assessment analytics" in source
    assert "personnel/evaluation boundary" in source


def test_privacy_draft_covers_professional_learning_and_minimized_notifications() -> None:
    source = normalized(PRIVACY)

    assert "teacher-authored reflections" in source
    assert "private ai-generated teacher recaps" in source
    assert "anonymous/aggregate school plc themes" in source
    assert "planned daily formative-assessment types" in source
    assert "professional operational email" in source
    assert "recipient's professional account email address" in source
    assert "does not persist the recipient email address" in source
    assert "not designed to make automated employment decisions" in source
    assert "student personally identifiable information" in source


def test_subprocessor_and_security_drafts_do_not_claim_ses_is_already_active() -> None:
    subprocessors = normalized(SUBPROCESSORS)
    security = normalized(SECURITY)

    assert "amazon ses" in subprocessors
    assert "remains fail-closed" in subprocessors
    assert "does not establish that email delivery is active" in subprocessors
    assert "fail-closed infrastructure for amazon ses" in security
    assert "remain controlled release actions" in security
    assert "interactive web task must not receive that credential" in security
    assert "does not trigger a second ai request" in security


def test_help_explains_new_admin_features_without_expanding_data_boundary() -> None:
    source = normalized(HELP)

    assert "school reflection summary and plc meeting guide" in source
    assert "at least two distinct anonymous teacher sources" in source
    assert "daily formative-assessment analytics" in source
    assert "planned formative-assessment signals" in source
    assert "professional operational email" in source
    assert "notifications@planner.guidedscholar.ai" in source
    assert "does not include teacher names, class-level exception lists" in source
    assert "named operational follow-up remains inside the authenticated application" in source
    assert "no-student-information boundary" in source
    assert "not teacher-performance measures" in source
