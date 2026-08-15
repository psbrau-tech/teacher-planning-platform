from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "arts-real-source-verify.yml"
ARCHITECTURE = ROOT / "docs" / "GATE_E_STANDARDS_ARCHITECTURE.md"


def test_live_source_verification_is_scoped_to_arts_parser_transport_changes() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "Determine whether live Arts source verification is required" in source
    assert '"backend/app/standards_alabama_arts.py"' in source
    assert '"backend/app/standards_ingest.py"' in source
    assert '"backend/pyproject.toml"' in source
    assert '["git", "diff", "--name-only", base_sha, head_sha]' in source
    assert "protected_paths.intersection(changed)" in source
    assert "live_required = bool(protected_changes)" in source
    assert "Arts parser/source transport unchanged" in source
    assert "if: steps.scope.outputs.live_required == 'true'" in source


def test_manual_dispatch_always_runs_live_source_verification() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in source
    assert 'if event_name != "pull_request":' in source
    assert "live_required = True" in source
    assert 'reason = "manual verification"' in source


def test_live_source_verification_retries_only_bounded_source_unavailability() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "for attempt in range(1, 5)" in source
    assert "StandardsIngestError" in source
    assert 'str(error) != "Authoritative standards source is unavailable"' in source
    assert "if attempt == 4" in source
    assert "wait_seconds = 15 * attempt" in source
    assert "raise" in source


def test_live_source_verification_still_uses_only_authoritative_source_and_writes_nothing() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "https://www.alabamaachieves.org/wp-content/uploads/2025/01/" in source
    assert "AS_20250108_2024-Alabama-Course-of-Study-Arts-Education_V1.0.pdf" in source
    assert 'fetched = fetch_source(url, "pdf")' in source
    assert "parse_alabama_arts_2024(extracted)" in source
    assert 'print("database_writes=0")' in source
    assert "--insecure" not in source
    assert "RECOVERY_SOURCE_IP" not in source
    assert "KNOWN_SOURCE_SHA256" not in source


def test_architecture_explicitly_preserves_snapshot_during_source_outage_and_scopes_pr_check() -> None:
    source = ARCHITECTURE.read_text(encoding="utf-8")

    assert "last approved snapshot remains active" in source
    assert "does not re-fetch unchanged standards documents for unrelated product changes" in source
    assert "Arts parser, shared source-ingestion transport, or backend dependency contract" in source
    assert "controlled manual live-source verification remains available" in source
