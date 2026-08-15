from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROVISION_SCRIPT = ROOT / "backend" / "scripts" / "provision_pilot.py"
PREFLIGHT_SCRIPT = ROOT / "backend" / "scripts" / "preflight_pilot.py"
WORKFLOW = ROOT / ".github" / "workflows" / "provision-pilot-access.yml"
DISTRICT_REPORTING_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260809002600_district_reporting_and_weekly_submissions.sql"
)
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260815215500_multi_school_notification_controls.sql"
)


def _module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _provision_module() -> ModuleType:
    return _module(PROVISION_SCRIPT, "tpp_provision_pilot_test")


def _preflight_module() -> ModuleType:
    return _module(PREFLIGHT_SCRIPT, "tpp_preflight_pilot_test")


def _write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "pilot-access.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _two_school_config() -> dict[str, object]:
    return {
        "districts": [{"name": "Anniston City Schools"}],
        "schools": [
            {
                "name": "Anniston High School",
                "district": "Anniston City Schools",
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
                "district": "Anniston City Schools",
                "timezone": "America/Chicago",
            },
        ],
        "access": [
            {
                "email": "owner@anniston.k12.al.us",
                "display_name": "Owner",
                "district": "Anniston City Schools",
                "school": "Anniston High School",
                "roles": ["platform_admin", "teacher"],
            },
            {
                "email": "middleadmin@anniston.k12.al.us",
                "display_name": "Middle Admin",
                "district": "Anniston City Schools",
                "school": "Anniston Middle School",
                "roles": ["school_admin"],
            },
        ],
    }


def test_multi_school_config_requires_explicit_district_school_and_timezone(
    tmp_path: Path,
) -> None:
    provision = _provision_module()
    config = provision._load_config(_write(tmp_path, _two_school_config()))

    assert [district.name for district in config.districts] == ["Anniston City Schools"]
    assert [school.name for school in config.schools] == [
        "Anniston High School",
        "Anniston Middle School",
    ]
    high, middle = config.schools
    assert high.district_name == "Anniston City Schools"
    assert middle.district_name == "Anniston City Schools"
    assert high.timezone == "America/Chicago"
    assert high.notifications.teacher_reminders_enabled is True
    assert (
        high.notifications.teacher_reminder_local_time.isoformat(timespec="minutes")
        == "14:00"
    )
    assert high.notifications.admin_digest_local_time.isoformat(timespec="minutes") == "15:30"
    assert middle.notifications.teacher_reminders_enabled is False
    assert middle.notifications.admin_digest_enabled is False
    assert config.access[0].district_name == "Anniston City Schools"
    assert config.access[1].school_name == "Anniston Middle School"


def test_each_professional_email_has_one_explicit_district_school_assignment(
    tmp_path: Path,
) -> None:
    provision = _provision_module()
    payload = _two_school_config()
    access = payload["access"]
    assert isinstance(access, list)
    access.append(
        {
            "email": "middleadmin@anniston.k12.al.us",
            "display_name": "Middle Admin",
            "district": "Anniston City Schools",
            "school": "Anniston High School",
            "roles": ["school_admin"],
        }
    )

    with pytest.raises(ValueError, match="duplicates an email"):
        provision._load_config(_write(tmp_path, payload))


def test_school_must_reference_a_configured_district(tmp_path: Path) -> None:
    provision = _provision_module()
    payload = _two_school_config()
    schools = payload["schools"]
    assert isinstance(schools, list)
    schools[1]["district"] = "Other District"

    with pytest.raises(ValueError, match="configured district"):
        provision._load_config(_write(tmp_path, payload))


def test_access_district_and_school_must_match_configured_pair(tmp_path: Path) -> None:
    provision = _provision_module()
    payload = _two_school_config()
    districts = payload["districts"]
    schools = payload["schools"]
    access = payload["access"]
    assert isinstance(districts, list)
    assert isinstance(schools, list)
    assert isinstance(access, list)
    districts.append({"name": "Neighbor District"})
    schools.append(
        {
            "name": "Anniston Middle School",
            "district": "Neighbor District",
            "timezone": "America/Chicago",
        }
    )
    access[1]["district"] = "Neighbor District"

    config = provision._load_config(_write(tmp_path, payload))
    middle_admin = next(
        row for row in config.access if row.email == "middleadmin@anniston.k12.al.us"
    )
    assert middle_admin.district_name == "Neighbor District"
    assert middle_admin.school_name == "Anniston Middle School"


def test_district_admin_scope_is_derived_from_assigned_schools_district(
    tmp_path: Path,
) -> None:
    provision = _provision_module()
    payload = _two_school_config()
    access = payload["access"]
    assert isinstance(access, list)
    access.append(
        {
            "email": "districtadmin@anniston.k12.al.us",
            "display_name": "District Admin",
            "district": "Anniston City Schools",
            "school": "Anniston High School",
            "roles": ["district_admin"],
        }
    )

    config = provision._load_config(_write(tmp_path, payload))
    district_admin = next(
        row for row in config.access if row.email == "districtadmin@anniston.k12.al.us"
    )
    assert district_admin.district_name == "Anniston City Schools"
    assert district_admin.school_name == "Anniston High School"
    assert district_admin.roles == ("district_admin",)

    reporting = DISTRICT_REPORTING_MIGRATION.read_text(encoding="utf-8")
    assert "select s.district_id" in reporting
    assert "join public.schools s on s.id = p.school_id" in reporting
    assert "s.district_id = private.current_district_id()" in reporting


def test_preflight_accepts_district_admin_and_validates_district_school_graph(
    tmp_path: Path,
) -> None:
    preflight = _preflight_module()
    payload = _two_school_config()
    access = payload["access"]
    assert isinstance(access, list)
    access.append(
        {
            "email": "districtadmin@anniston.k12.al.us",
            "display_name": "District Admin",
            "district": "Anniston City Schools",
            "school": "Anniston High School",
            "roles": ["district_admin"],
        }
    )

    summary = preflight.validate_preflight(
        access_path=_write(tmp_path, payload),
        platform_owner_email="owner@anniston.k12.al.us",
        academic_year_name="2026-2027",
        starts_on=preflight.date(2026, 8, 6),
        ends_on=preflight.date(2027, 5, 24),
    )
    assert summary.district_count == 1
    assert summary.school_count == 2
    assert summary.active_district_admin_records == 1


def test_multi_school_config_rejects_invalid_iana_timezone(tmp_path: Path) -> None:
    provision = _provision_module()
    payload = _two_school_config()
    schools = payload["schools"]
    assert isinstance(schools, list)
    schools[0]["timezone"] = "Central"

    with pytest.raises(ValueError, match="invalid IANA timezone"):
        provision._load_config(_write(tmp_path, payload))


def test_multi_school_config_rejects_non_quarter_hour_notification_time(
    tmp_path: Path,
) -> None:
    provision = _provision_module()
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
    provision = _provision_module()
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
    assert len(config.districts) == 1
    assert config.districts[0].name == "Anniston City Schools"
    assert len(config.schools) == 1
    assert config.schools[0].name == "Anniston High School"
    assert config.schools[0].district_name == "Anniston City Schools"
    assert config.schools[0].timezone == "America/Chicago"
    assert config.schools[0].notifications.teacher_reminders_enabled is False
    assert config.schools[0].notifications.admin_digest_enabled is False
    assert config.access[0].school_name == "Anniston High School"


def test_source_contract_preserves_one_email_one_school_and_explicit_district() -> None:
    script = PROVISION_SCRIPT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "on conflict (email) do update set" in script
    assert "school_id = excluded.school_id" in script
    assert '"districts"' in script
    assert '"district"' in script
    assert '"school"' in script
    assert "ZoneInfo" in script
    assert "school_notification_settings" in script
    assert "pilot_access_allowlist_pkey primary key (email, school_id)" not in migration
    assert "New-school automatic notification default:" in workflow
    assert "disabled" in workflow
    assert "- District: Anniston City Schools" not in workflow
