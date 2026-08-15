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


def _two_school_config() -> dict[str, object]:
    return {
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
            },
            {
                "email": "middleadmin@anniston.k12.al.us",
                "display_name": "Middle Admin",
                "school": "Anniston Middle School",
                "roles": ["school_admin"],
            },
        ],
    }


def test_multi_school_config_requires_explicit_school_timezone_and_defaults_notifications_off(
    tmp_path: Path,
) -> None:
    provision = _module()
    config = provision._load_config(_write(tmp_path, _two_school_config()))

    assert [school.name for school in config.schools] == [
        "Anniston High School",
        "Anniston Middle School",
    ]
    high, middle = config.schools
    assert high.timezone == "America/Chicago"
    assert high.notifications.teacher_reminders_enabled is True
    assert (
        high.notifications.teacher_reminder_local_time.isoformat(timespec="minutes")
        == "14:00"
    )
    assert high.notifications.admin_digest_local_time.isoformat(timespec="minutes") == "15:30"
    assert middle.notifications.teacher_reminders_enabled is False
    assert middle.notifications.admin_digest_enabled is False
    assert config.access[0].school_name == "Anniston High School"
    assert config.access[1].school_name == "Anniston Middle School"


def test_each_professional_email_has_one_explicit_school(tmp_path: Path) -> None:
    provision = _module()
    payload = _two_school_config()
    access = payload["access"]
    assert isinstance(access, list)
    access.append(
        {
            "email": "middleadmin@anniston.k12.al.us",
            "display_name": "Middle Admin",
            "school": "Anniston High School",
            "roles": ["school_admin"],
        }
    )

    with pytest.raises(ValueError, match="duplicates an email"):
        provision._load_config(_write(tmp_path, payload))


def test_school_admin_and_district_admin_are_explicit_roles_not_multi_school_membership(
    tmp_path: Path,
) -> None:
    provision = _module()
    payload = _two_school_config()
    access = payload["access"]
    assert isinstance(access, list)
    access.append(
        {
            "email": "districtadmin@anniston.k12.al.us",
            "display_name": "District Admin",
            "school": "Anniston High School",
            "roles": ["district_admin"],
        }
    )

    config = provision._load_config(_write(tmp_path, payload))
    district = next(
        row for row in config.access if row.email == "districtadmin@anniston.k12.al.us"
    )
    middle = next(
        row for row in config.access if row.email == "middleadmin@anniston.k12.al.us"
    )
    assert district.school_name == "Anniston High School"
    assert district.roles == ("district_admin",)
    assert middle.school_name == "Anniston Middle School"
    assert middle.roles == ("school_admin",)


def test_multi_school_config_rejects_invalid_iana_timezone(tmp_path: Path) -> None:
    provision = _module()
    payload = _two_school_config()
    schools = payload["schools"]
    assert isinstance(schools, list)
    schools[0]["timezone"] = "Central"

    with pytest.raises(ValueError, match="invalid IANA timezone"):
        provision._load_config(_write(tmp_path, payload))


def test_multi_school_config_rejects_non_quarter_hour_notification_time(
    tmp_path: Path,
) -> None:
    provision = _module()
    payload = _two_school_config()
    schools = payload["schools"]
    assert isinstance(schools, list)
    notifications = schools[0]["notifications"]
    assert isinstance(notifications, dict)
    notifications["teacher_reminder_local_time"] = "14:07"

    with pytest.raises(ValueError, match="15-minute"):
        provision._load_config(_write(tmp_path, payload))


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
    assert config.access[0].school_name == "Anniston High School"


def test_source_contract_preserves_one_email_one_school_and_no_hardcoded_ahs_summary() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "on conflict (email) do update set" in script
    assert "school_id = excluded.school_id" in script
    assert '"school"' in script
    assert '"is_home"' not in script
    assert "ZoneInfo" in script
    assert "school_notification_settings" in script
    assert "pilot_access_allowlist_pkey primary key (email, school_id)" not in migration
    assert "is_home" not in migration
    assert "New-school automatic notification default: `disabled`" in workflow
    assert "- School: Anniston High School" not in workflow
