from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parents[1] / "scripts" / "preflight_pilot.py"


def _run_preflight(
    tmp_path: Path, records: list[dict[str, Any]]
) -> subprocess.CompletedProcess[str]:
    access_path = tmp_path / "pilot-access.json"
    access_path.write_text(json.dumps(records), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--access-json",
            str(access_path),
            "--platform-owner-email",
            "owner@anniston.k12.al.us",
            "--academic-year-name",
            "2026-2027",
            "--starts-on",
            "2026-08-06",
            "--ends-on",
            "2027-05-28",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _valid_records() -> list[dict[str, Any]]:
    return [
        {
            "email": "owner@anniston.k12.al.us",
            "display_name": "Platform Owner",
            "roles": ["platform_admin", "teacher"],
            "is_active": True,
        },
        {
            "email": "administrator@anniston.k12.al.us",
            "display_name": "School Administrator",
            "roles": ["school_admin"],
            "is_active": True,
        },
        {
            "email": "teacher@anniston.k12.al.us",
            "display_name": "Pilot Teacher",
            "roles": ["teacher"],
            "is_active": True,
        },
    ]


def test_preflight_accepts_governed_pilot_access(tmp_path: Path) -> None:
    result = _run_preflight(tmp_path, _valid_records())

    assert result.returncode == 0, result.stderr
    assert "TPP pilot access preflight passed." in result.stdout
    assert "Active access records: 3" in result.stdout
    assert "Platform Owner concurrent platform_admin + teacher roles verified." in result.stdout


def test_preflight_rejects_owner_without_teacher_role(tmp_path: Path) -> None:
    records = _valid_records()
    records[0]["roles"] = ["platform_admin"]

    result = _run_preflight(tmp_path, records)

    assert result.returncode != 0
    assert "concurrent platform_admin and teacher roles" in result.stderr


def test_preflight_rejects_duplicate_email(tmp_path: Path) -> None:
    records = _valid_records()
    records.append(
        {
            "email": "TEACHER@anniston.k12.al.us",
            "display_name": "Duplicate Teacher",
            "roles": ["teacher"],
            "is_active": True,
        }
    )

    result = _run_preflight(tmp_path, records)

    assert result.returncode != 0
    assert "duplicates an email" in result.stderr


def test_preflight_requires_active_school_admin(tmp_path: Path) -> None:
    records = _valid_records()
    records[1]["is_active"] = False

    result = _run_preflight(tmp_path, records)

    assert result.returncode != 0
    assert "at least one active school_admin" in result.stderr


def test_preflight_rejects_non_school_domain(tmp_path: Path) -> None:
    records = _valid_records()
    records[2]["email"] = "teacher@example.com"

    result = _run_preflight(tmp_path, records)

    assert result.returncode != 0
    assert "must use the anniston.k12.al.us school domain" in result.stderr
