from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend" / "scripts" / "provision_pilot.py"
WORKFLOW = ROOT / ".github" / "workflows" / "provision-pilot-access.yml"
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815215500_multi_school_notification_controls.sql"
)


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tpp_provision_pilot_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "pilot-access.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_multi_school_config_requires_explicit_school_timezone_and_defaults_notifications_off(
    tmp_path: Path,
) -> None:
    provision = _module()
    path = _write(
        tmp_path,
        {
            "schools": [
                {
                    "name": "Anniston High School",
                    "timezone": "America/Chicago",
                    "notifications": {
                        "teacher_reminders_enabled": True,
                        "teacher_reminder_local_time": "14:00",
                        "admin_digest_enabled": True,
                        "admin_digest_local_time": "15:30",
                    },
                },
                {
                    "name": "Anniston Middle School",
                    "timezone": "America/Chicago",
                },
            ],
            "access": [
                {
                    "email": "owner@anniston.k12.al.us",
                    "display_name": "Owner",
                    "school": "Anniston High School",
                    "roles": ["platform_admin", "teacher"],
                    "is_home": True,
                },
                {
                    "email": "middleadmin@anniston.k12.al.us",
                    "display_name": "Middle Admin",
                    "school": "Anniston Middle School",
                    "roles": ["school_admin"],
                    "is_home": True,
                },
            ],
        },
    )

    config = provision._load_config(path)
    assert [school.name for school in config.schools] == [
        "Anniston High School",
        "Anniston Middle School",
    ]
    high, middle = config.schools
    assert high.timezone == "America/Chicago"
    assert high.notifications.teacher_reminders_enabled is True
    assert high.notifications.teacher_reminder_local_time.isoformat(timespec="minutes") == "14:00"
    assert high.notifications.admin_digest_local_time.isoformat(timespec="minutes") == "15:30"
    assert middle.notifications.teacher_reminders_enabled is False
    assert middle.notifications.admin_digest_enabled is False


def test_one_account_can_hold_memberships_in_multiple_schools_with_one_home(
    tmp_path: Path,
) -> None:
    provision = _module()
    path = _write(
        tmp_path,
        {
            "schools": [
                {"name": "Anniston High School", "timezone": "America/Chicago"},
                {"name": "Anniston Middle School", "timezone": "America/Chicago"},
            ],
            "access": [
                {
                    "email": "owner@anniston.k12.al.us",
                    "display_name": "Owner",
                    "school": "Anniston High School",
                    "roles": ["platform_admin", "teacher"],
                    "is_home": True,
                },
                {
                    "email": "crossadmin@anniston.k12.al.us",
                    "display_name": "Cross Admin",
                    "school": "Anniston High School",
                    "roles": ["school_admin"],
                    "is_home": True,
                },
                {
                    "email": "crossadmin@anniston.k12.al.us",
                    "display_name": "Cross Admin",
                    "school": "Anniston Middle School",
                    "roles": ["school_admin"],
                    "is_home": False,
                },
            ],
        },
    )

    config = provision._load_config(path)
    cross_admin = [
        row for row in config.access if row.email == "crossadmin@anniston.k12.al.us"
    ]
    assert len(cross_admin) == 2
    assert sum(1 for row in cross_admin if row.is_home) == 1


def test_multi_school_config_rejects_two_active_home_schools(tmp_path: Path) -> None:
    provision = _module()
    path = _write(
        tmp_path,
        {
            "schools": [
                {"name": "Anniston High School", "timezone": "America/Chicago"},
                {"name": "Anniston Middle School", "timezone": "America/Chicago"},
            ],
            "access": [
                {
                    "email": "owner@anniston.k12.al.us",
                    "display_name": "Owner",
                    "school": "Anniston High School",
                    "roles": ["platform_admin", "teacher"],
                    "is_home": True,
                },
                {
                    "email": "owner@anniston.k12.al.us",
                    "display_name": "Owner",
                    "school": "Anniston Middle School",
                    "roles": ["school_admin"],
                    "is_home": True,
                },
            ],
        },
    )

    with pytest.raises(ValueError, match="exactly one home school"):
        provision._load_config(path)


def test_multi_school_config_rejects_invalid_iana_timezone(tmp_path: Path) -> None:
    provision = _module()
    path = _write(
        tmp_path,
        {
            "schools": [{"name": "Anniston High School", "timezone": "Central"}],
            "access": [
                {
                    "email": "owner@anniston.k12.al.us",
                    "display_name": "Owner",
                    "school": "Anniston High School",
                    "roles": ["platform_admin", "teacher"],
                    "is_home": True,
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="invalid IANA timezone"):
        provision._load_config(path)


def test_legacy_access_secret_remains_compatible_but_notifications_fail_closed(
    tmp_path: Path,
) -> None:
    provision = _module()
    path = _write(
        tmp_path,
        [
            {
                "email": "owner@anniston.k12.al.us",
                "display_name": "Owner",
                "roles": ["platform_admin", "teacher"],
                "is_active": True,
            }
        ],
    )

    config = provision._load_config(path)
    assert len(config.schools) == 1
    assert config.schools[0].name == "Anniston High School"
    assert config.schools[0].timezone == "America/Chicago"
    assert config.schools[0].notifications.teacher_reminders_enabled is False
    assert config.schools[0].notifications.admin_digest_enabled is False


def test_source_contract_uses_school_membership_keys_and_never_hardcodes_ahs_summary() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "on conflict (email, school_id)" in script
    assert '"school"' in script
    assert "ZoneInfo" in script
    assert "school_notification_settings" in script
    assert "pilot_access_allowlist_pkey primary key (email, school_id)" in migration
    assert "pilot_access_one_active_home_per_email_idx" in migration
    assert "New-school automatic notification default: `disabled`" in workflow
    assert "- School: Anniston High School" not in workflow
