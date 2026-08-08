from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_cloudformation_injects_only_gate_e_interactive_runtime_credentials() -> None:
    template = _read("infra/pilot-stack.yml")

    assert "OpenAiApiKeySecretArn:" in template
    assert "Name: TPP_OPENAI_API_KEY" in template
    assert "ValueFrom: !Ref OpenAiApiKeySecretArn" in template
    assert "Type: AWS::ElasticLoadBalancingV2::LoadBalancer" in template

    for prohibited in (
        "Name: TPP_SUPABASE_SERVICE_ROLE_KEY",
        "Name: TPP_DATABASE_URL",
        "Name: TPP_GOOGLE_OAUTH_CLIENT_ID",
        "Name: TPP_GOOGLE_OAUTH_CLIENT_SECRET",
    ):
        assert prohibited not in template


def test_controlled_deploy_supports_one_time_legacy_to_gate_e_secret_migration() -> None:
    workflow = _read(".github/workflows/deploy-pilot.yml")

    assert "OPENAI_API_KEY_SECRET_ID" in workflow
    assert "resolve_secret openai_api_key" in workflow
    assert 'OpenAiApiKeySecretArn="${{ steps.secrets.outputs.openai_api_key }}"' in workflow
    assert "legacy_secret_set=$'TPP_SUPABASE_ANON_KEY\\nTPP_SUPABASE_URL'" in workflow
    assert (
        "gate_e_secret_set=$'TPP_OPENAI_API_KEY\\nTPP_SUPABASE_ANON_KEY\\nTPP_SUPABASE_URL'"
        in workflow
    )
    assert (
        "expected_secret_names=$'TPP_OPENAI_API_KEY\\nTPP_SUPABASE_ANON_KEY\\nTPP_SUPABASE_URL'"
        in workflow
    )


def test_bootstrap_tls_and_read_only_verifier_require_gate_e_secret_set() -> None:
    bootstrap_workflow = _read(".github/workflows/bootstrap-pilot.yml")
    bootstrap_script = _read("scripts/bootstrap_pilot.sh")
    tls_workflow = _read(".github/workflows/enable-pilot-tls.yml")
    verifier = _read("scripts/verify_pilot_deployment.sh")

    assert "OPENAI_API_KEY_SECRET_ID" in bootstrap_workflow
    assert "OPENAI_API_KEY_SECRET_ID" in bootstrap_script
    assert 'OpenAiApiKeySecretArn="$openai_api_key_secret_arn"' in bootstrap_script
    assert "OPENAI_API_KEY_SECRET_ID" in tls_workflow
    assert "OpenAiApiKeySecretArn=" in tls_workflow

    exact_set = (
        "expected_secret_names=$'TPP_OPENAI_API_KEY\\n"
        "TPP_SUPABASE_ANON_KEY\\nTPP_SUPABASE_URL'"
    )
    assert exact_set in bootstrap_script
    assert exact_set in tls_workflow
    assert exact_set in verifier

    prohibited_block = verifier.split("for prohibited_secret in", maxsplit=1)[1].split(
        "; do", maxsplit=1
    )[0]
    assert "TPP_OPENAI_API_KEY" not in prohibited_block
    for prohibited in (
        "TPP_DATABASE_URL",
        "TPP_GOOGLE_OAUTH_CLIENT_ID",
        "TPP_GOOGLE_OAUTH_CLIENT_SECRET",
        "TPP_SUPABASE_SERVICE_ROLE_KEY",
    ):
        assert prohibited in prohibited_block
