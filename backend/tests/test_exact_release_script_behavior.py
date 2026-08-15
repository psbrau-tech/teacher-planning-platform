from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY_SCRIPT = ROOT / "scripts" / "verify_exact_release_candidate.sh"
STAGE_SCRIPT = ROOT / "scripts" / "stage_migrations_through.sh"
TARGET = "20260815001500"
LATER = "20260815011000"
EARLIER = "20260814190000"
SHA = "a" * 40


def _migration_dir(root: Path) -> Path:
    migrations = root / "supabase" / "migrations"
    migrations.mkdir(parents=True)
    return migrations


def _run(
    script: Path,
    *,
    cwd: Path,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        ["bash", str(script), *(args or [])],
        cwd=cwd,
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_stage_script_keeps_target_and_moves_only_later_migrations(tmp_path: Path) -> None:
    migrations = _migration_dir(tmp_path)
    earlier = migrations / f"{EARLIER}_reflection.sql"
    target = migrations / f"{TARGET}_assessment.sql"
    later = migrations / f"{LATER}_scheduled.sql"
    for path in (earlier, target, later):
        path.write_text("select 1;\n", encoding="utf-8")

    deferred = tmp_path / "deferred"
    output = tmp_path / "github-output.txt"
    result = _run(
        STAGE_SCRIPT,
        cwd=tmp_path,
        args=[TARGET, str(deferred)],
        env={"GITHUB_OUTPUT": str(output)},
    )

    assert result.returncode == 0, result.stderr
    assert earlier.exists()
    assert target.exists()
    assert not later.exists()
    assert (deferred / later.name).exists()
    assert f"Staged migrations through {TARGET}; deferred 1 later migration(s)." in result.stdout
    summary = output.read_text(encoding="utf-8")
    assert "deferred_count=1" in summary
    assert f"staged_head={TARGET}" in summary


def test_stage_script_rejects_unknown_target_without_moving_files(tmp_path: Path) -> None:
    migrations = _migration_dir(tmp_path)
    later = migrations / f"{LATER}_scheduled.sql"
    later.write_text("select 1;\n", encoding="utf-8")

    result = _run(
        STAGE_SCRIPT,
        cwd=tmp_path,
        args=[TARGET, str(tmp_path / "deferred")],
    )

    assert result.returncode != 0
    assert "Expected exactly one target migration" in result.stderr
    assert later.exists()


def test_verify_script_accepts_exact_main_sha_and_known_target(tmp_path: Path) -> None:
    migrations = _migration_dir(tmp_path)
    target = migrations / f"{TARGET}_assessment.sql"
    target.write_text("select 1;\n", encoding="utf-8")
    output = tmp_path / "github-output.txt"

    result = _run(
        VERIFY_SCRIPT,
        cwd=tmp_path,
        env={
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": SHA,
            "EXPECTED_MAIN_SHA": SHA,
            "EXPECTED_MIGRATION_HEAD": TARGET,
            "GITHUB_OUTPUT": str(output),
        },
    )

    assert result.returncode == 0, result.stderr
    assert f"Exact release candidate verified: commit={SHA} migration={TARGET}" in result.stdout
    assert f"migration_file=supabase/migrations/{target.name}" in output.read_text(
        encoding="utf-8"
    )


def test_verify_script_rejects_wrong_branch_or_moved_sha(tmp_path: Path) -> None:
    migrations = _migration_dir(tmp_path)
    (migrations / f"{TARGET}_assessment.sql").write_text("select 1;\n", encoding="utf-8")
    common = {
        "GITHUB_SHA": SHA,
        "EXPECTED_MAIN_SHA": SHA,
        "EXPECTED_MIGRATION_HEAD": TARGET,
    }

    wrong_branch = _run(
        VERIFY_SCRIPT,
        cwd=tmp_path,
        env={**common, "GITHUB_REF": "refs/heads/release-candidate"},
    )
    assert wrong_branch.returncode != 0
    assert "must run from refs/heads/main" in wrong_branch.stderr

    moved_sha = _run(
        VERIFY_SCRIPT,
        cwd=tmp_path,
        env={
            **common,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "b" * 40,
        },
    )
    assert moved_sha.returncode != 0
    assert "Release candidate moved" in moved_sha.stderr


def test_verify_script_requires_applied_confirmation_when_deploy_gate_enabled(
    tmp_path: Path,
) -> None:
    migrations = _migration_dir(tmp_path)
    (migrations / f"{TARGET}_assessment.sql").write_text("select 1;\n", encoding="utf-8")
    env = {
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SHA,
        "EXPECTED_MAIN_SHA": SHA,
        "EXPECTED_MIGRATION_HEAD": TARGET,
        "REQUIRE_MIGRATION_APPLIED_CONFIRMATION": "true",
    }

    blocked = _run(VERIFY_SCRIPT, cwd=tmp_path, env=env)
    assert blocked.returncode != 0
    assert "confirmed applied" in blocked.stderr

    allowed = _run(
        VERIFY_SCRIPT,
        cwd=tmp_path,
        env={**env, "MIGRATION_APPLIED_CONFIRMED": "true"},
    )
    assert allowed.returncode == 0, allowed.stderr
