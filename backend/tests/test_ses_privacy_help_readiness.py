from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "docs" / "governance" / "SES_PRIVACY_HELP_READINESS_2026-08-19.md"
FEEDBACK = ROOT / "docs" / "governance" / "SES_FEEDBACK_CONTROLS_RUNBOOK_2026-08-19.md"
PRIVACY = ROOT / "docs" / "legal" / "PRIVACY_POLICY.md"
SUBPROCESSORS = ROOT / "docs" / "legal" / "SUBPROCESSORS.md"
HELP = ROOT / "frontend" / "src" / "HelpPage.tsx"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_feedback_controls_are_accepted_without_activating_email() -> None:
    source = normalized(FEEDBACK)

    assert "accepted provider evidence — 2026-08-19" in source
    assert "account-level suppression enabled for both `bounce` and `complaint`" in source
    assert "tpp-pilot-ses-feedback" in source
    assert "email feedback forwarding disabled" in source
    assert "mailbox-simulator bounce and complaint notifications received" in source
    assert "feedback_controls_confirmed=true" in source
    assert "does not itself activate tpp ses application sending" in source


def test_privacy_help_readiness_is_narrow_and_not_legal_effectiveness() -> None:
    source = normalized(READINESS)

    assert "privacy_help_review_confirmed=true" in source
    assert "pre-release draft / not yet effective" in source
    assert "does **not** make any customer-facing legal document effective" in source
    assert "qualified legal review" in source
    assert "friday schedulers" in source
    assert "notifications@planner.guidedscholar.ai" in source
    assert "peter@brauconsulting.com" in source
    assert "student pii" in source


def test_privacy_draft_still_covers_minimized_professional_email() -> None:
    source = normalized(PRIVACY)

    assert "pre-release draft — not yet effective" in source
    assert "recipient's professional account email address" in source
    assert "professional operational email" in source
    assert "does not persist the recipient email address" in source
    assert "student personally identifiable information" in source


def test_subprocessor_draft_records_provider_ready_but_application_fail_closed() -> None:
    source = normalized(SUBPROCESSORS)

    assert "pre-release draft" in source
    assert "production sending access" in source
    assert "account-level suppression" in source
    assert "`bounce`" in source
    assert "`complaint`" in source
    assert "monitored sns bounce/complaint feedback" in source
    assert "email feedback forwarding is disabled" in source
    assert "tpp application ses sending remains fail-closed" in source
    assert "friday dispatchers remain separate controlled activations" in source


def test_help_matches_minimized_governed_notification_content() -> None:
    source = normalized(HELP)

    assert "friday professional operational email" in source
    assert "notifications@planner.guidedscholar.ai" in source
    assert "aggregate school status" in source
    assert "does not include teacher names, class-level exception lists" in source
    assert "named operational follow-up remains inside the authenticated application" in source
    assert "automatic delivery is enabled only through a controlled release" in source
