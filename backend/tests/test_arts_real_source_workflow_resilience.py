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


def test_real_source_verification_has_tls_verified_validating_doh_route() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "def doh_payload" in source
    assert "def resolve_ipv4" in source
    assert '"https://cloudflare-dns.com/dns-query"' in source
    assert '"cloudflare-dns.com"' in source
    assert '"1.1.1.1"' in source
    assert '"https://dns.google/resolve"' in source
    assert '"dns.google"' in source
    assert '"8.8.8.8"' in source
    assert '"accept: application/dns-json"' in source
    assert "validation=on" in source
    assert 'transport = "validated-doh-route"' in source


def test_dns_outage_recovery_keeps_tls_and_exact_content_pins() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert 'KNOWN_SOURCE_SHA256 = (' in source
    assert '"add310883b958ebb8a617d9b405a596aeda3488d75ddf24f2aef1bf463995498"' in source
    assert 'KNOWN_NORMALIZED_SHA256 = (' in source
    assert '"9cb3249ec617c4253c6812c1a8822a8c19dbbf2ab0a33869b0506105216b5fc8"' in source
    assert 'RECOVERY_SOURCE_IP = "157.149.4.100"' in source
    assert "def fetch_with_explicit_route" in source
    assert 'transport = "pinned-route-tls-hash"' in source
    assert "source_digest != KNOWN_SOURCE_SHA256" in source
    assert "extracted.normalized_sha256 != KNOWN_NORMALIZED_SHA256" in source
    assert "len(parsed.courses) != 82" in source
    assert "!= 1634" in source
    assert 'f"www.alabamaachieves.org:443:{source_ip}"' in source
    assert 'f"alabamaachieves.org:443:{source_ip}"' in source
    assert '"--insecure"' not in source
    assert '"--doh-insecure"' not in source
    assert "content.startswith(b\"%PDF\")" in source
    assert "MAX_SOURCE_BYTES" in source


def test_recovery_ip_is_routing_hint_not_alternate_content_source() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "Routing hint only, never an authenticity signal" in source
    assert "https://www.alabamaachieves.org/wp-content/uploads/2025/01/" in source
    assert "AS_20250108_2024-Alabama-Course-of-Study-Arts-Education_V1.0.pdf" in source
    assert "requested_url=url" in source
    assert "url," in source
    assert "alternate content source is permitted" in source
    assert "RECOVERY_SOURCE_IP" not in source.split("url = (", 1)[1].split(")", 1)[0]


def test_real_source_verification_still_parses_and_writes_nothing() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert 'fetched = fetch_source(url, "pdf")' in source
    assert "parse_alabama_arts_2024(extracted)" in source
    assert 'print("database_writes=0")' in source
    assert "source_sha256" in source
    assert "normalized_sha256" in source
