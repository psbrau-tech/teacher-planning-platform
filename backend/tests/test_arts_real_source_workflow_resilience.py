from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "arts-real-source-verify.yml"


def test_real_source_verification_retries_only_bounded_source_unavailability() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "for attempt in range(1, 5)" in source
    assert "StandardsIngestError" in source
    assert 'str(error) != "Authoritative standards source is unavailable"' in source
    assert "if attempt < 4" in source
    assert "wait_seconds = 15 * attempt" in source
    assert "raise" in source


def test_real_source_verification_has_tls_verified_explicit_doh_without_bypass() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "def doh_payload" in source
    assert "def resolve_ipv4" in source
    assert '"https://cloudflare-dns.com/dns-query?name=' in source
    assert '"cloudflare-dns.com"' in source
    assert '"1.1.1.1"' in source
    assert '"https://dns.google/resolve?name=' in source
    assert '"dns.google"' in source
    assert '"8.8.8.8"' in source
    assert '"accept: application/dns-json"' in source
    assert 'f"www.alabamaachieves.org:443:{source_ips[0]}"' in source
    assert 'f"alabamaachieves.org:443:{root_ips[0]}"' in source
    assert '"--fail"' in source
    assert '"--location"' in source
    assert '"--insecure"' not in source
    assert '"--doh-insecure"' not in source
    assert "content.startswith(b\"%PDF\")" in source
    assert "MAX_SOURCE_BYTES" in source
    assert 'transport = "explicit-doh-resolve"' in source


def test_real_source_verification_still_uses_authoritative_source_and_writes_nothing() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "https://www.alabamaachieves.org/wp-content/uploads/2025/01/" in source
    assert "AS_20250108_2024-Alabama-Course-of-Study-Arts-Education_V1.0.pdf" in source
    assert 'fetched = fetch_source(url, "pdf")' in source
    assert "parse_alabama_arts_2024(extracted)" in source
    assert 'print("database_writes=0")' in source
    assert "source_sha256" in source
    assert "normalized_sha256" in source
