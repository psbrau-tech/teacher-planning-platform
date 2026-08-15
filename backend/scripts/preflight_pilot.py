from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ALLOWED_DOMAIN = "anniston.k12.al.us"
LEGACY_DISTRICT_NAME = "Anniston City Schools"
LEGACY_SCHOOL_NAME = "Anniston High School"
DEFAULT_TIMEZONE = "America/Chicago"
ALLOWED_ROLES = frozenset(
    {"teacher", "school_admin", "district_admin", "platform_admin"}
)
LEGACY_ACCESS_KEYS = frozenset({"email", "display_name", "roles", "is_active"})
CONFIG_KEYS = frozenset({"districts", "schools", "access"})
DISTRICT_KEYS = frozenset({"name"})
SCHOOL_KEYS = frozenset({"name", "district", "timezone", "notifications"})
NOTIFICATION_KEYS = frozenset(
    {
        "teacher_reminders_enabled",
        "teacher_reminder_local_time",
        "admin_digest_enabled",
        "admin_digest_local_time",
    }
)
ACCESS_KEYS = frozenset(
    {"email", "display_name", "district", "school", "roles", "is_active"}
)


@dataclass(frozen=True, slots=True)
class AccessRecord:
    email: str
    display_name: str
    district_name: str
    school_name: str
    roles: tuple[str, ...]
    is_active: bool


@dataclass(frozen=True, slots=True)
class PreflightSummary:
    district_count: int
    school_count: int
    total_records: int
    active_records: int
    inactive_records: int
    active_teacher_records: int
    active_school_admin_records: int
    active_district_admin_records: int
    active_platform_admin_records: int


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)") from error


def _validate_timezone(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires an IANA timezone")
    timezone_name = value.strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"{name} contains an invalid IANA timezone") from error
    return timezone_name


def _validate_local_time(value: object, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"{name} must use HH:MM local time")
    try:
        parsed = time.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must use HH:MM local time") from error
    if (
        parsed.second
        or parsed.microsecond
        or parsed.tzinfo is not None
        or parsed.minute % 15 != 0
    ):
        raise ValueError(f"{name} must use a 15-minute HH:MM boundary")


def _validate_notifications(value: object, school_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"{school_name} notifications must be an object")
    payload = cast(dict[str, Any], value)
    unknown = set(payload) - NOTIFICATION_KEYS
    if unknown:
        raise ValueError(
            f"{school_name} notifications contain unsupported fields: {sorted(unknown)}"
        )
    teacher_enabled = payload.get("teacher_reminders_enabled", False)
    admin_enabled = payload.get("admin_digest_enabled", False)
    if not isinstance(teacher_enabled, bool) or not isinstance(admin_enabled, bool):
        raise ValueError(f"{school_name} notification enablement values must be boolean")
    _validate_local_time(
        payload.get("teacher_reminder_local_time"),
        f"{school_name} teacher_reminder_local_time",
    )
    _validate_local_time(
        payload.get("admin_digest_local_time"),
        f"{school_name} admin_digest_local_time",
    )


def _parse_access_row(
    item: object,
    index: int,
    *,
    school_keys: frozenset[tuple[str, str]],
    legacy: bool,
) -> AccessRecord:
    if not isinstance(item, dict):
        raise ValueError(f"pilot access row {index} must be an object")
    record = cast(dict[str, Any], item)
    unknown = set(record) - (LEGACY_ACCESS_KEYS if legacy else ACCESS_KEYS)
    if unknown:
        raise ValueError(
            f"pilot access row {index} contains unsupported fields: {sorted(unknown)}"
        )

    email_value = record.get("email")
    display_name_value = record.get("display_name")
    roles_value = record.get("roles")
    active_value = record.get("is_active", True)
    district_value = LEGACY_DISTRICT_NAME if legacy else record.get("district")
    school_value = LEGACY_SCHOOL_NAME if legacy else record.get("school")

    if not isinstance(email_value, str) or not email_value.strip():
        raise ValueError(f"pilot access row {index} requires an email")
    email = email_value.strip().lower()
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        raise ValueError(
            f"pilot access row {index} must use the {ALLOWED_DOMAIN} school domain"
        )
    if not isinstance(display_name_value, str) or not display_name_value.strip():
        raise ValueError(f"pilot access row {index} requires a display_name")
    if not isinstance(district_value, str) or not isinstance(school_value, str):
        raise ValueError(f"pilot access row {index} requires district and school")
    if (district_value, school_value) not in school_keys:
        raise ValueError(
            f"pilot access row {index} requires a configured district/school assignment"
        )
    if not isinstance(roles_value, list) or not roles_value:
        raise ValueError(f"pilot access row {index} requires at least one role")
    if not all(isinstance(role, str) for role in roles_value):
        raise ValueError(f"pilot access row {index} roles must be strings")
    roles = tuple(dict.fromkeys(cast(list[str], roles_value)))
    invalid_roles = set(roles) - ALLOWED_ROLES
    if invalid_roles:
        raise ValueError(
            f"pilot access row {index} contains invalid roles: {sorted(invalid_roles)}"
        )
    if not isinstance(active_value, bool):
        raise ValueError(f"pilot access row {index} is_active must be boolean")

    return AccessRecord(
        email=email,
        display_name=display_name_value.strip(),
        district_name=district_value,
        school_name=school_value,
        roles=roles,
        is_active=active_value,
    )


def _load_access(path: Path) -> tuple[int, int, tuple[AccessRecord, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        if not payload:
            raise ValueError("pilot access JSON must be a non-empty array")
        school_keys = frozenset({(LEGACY_DISTRICT_NAME, LEGACY_SCHOOL_NAME)})
        records = tuple(
            _parse_access_row(
                item,
                index,
                school_keys=school_keys,
                legacy=True,
            )
            for index, item in enumerate(payload, start=1)
        )
        district_count = 1
        school_count = 1
    elif isinstance(payload, dict):
        config = cast(dict[str, Any], payload)
        unknown = set(config) - CONFIG_KEYS
        if unknown:
            raise ValueError(
                f"pilot access config contains unsupported fields: {sorted(unknown)}"
            )
        raw_districts = config.get("districts")
        raw_schools = config.get("schools")
        raw_access = config.get("access")
        if not isinstance(raw_districts, list) or not raw_districts:
            raise ValueError("multi-school pilot config requires a non-empty districts array")
        if not isinstance(raw_schools, list) or not raw_schools:
            raise ValueError("multi-school pilot config requires a non-empty schools array")
        if not isinstance(raw_access, list) or not raw_access:
            raise ValueError("multi-school pilot config requires a non-empty access array")

        district_names: list[str] = []
        for index, item in enumerate(raw_districts, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"district row {index} must be an object")
            district = cast(dict[str, Any], item)
            unknown_district = set(district) - DISTRICT_KEYS
            if unknown_district:
                raise ValueError(
                    "district row "
                    f"{index} contains unsupported fields: {sorted(unknown_district)}"
                )
            name_value = district.get("name")
            if not isinstance(name_value, str) or not name_value.strip():
                raise ValueError(f"district row {index} requires a name")
            district_names.append(name_value.strip())
        if len(set(district_names)) != len(district_names):
            raise ValueError("multi-school pilot config contains duplicate district names")
        district_name_set = frozenset(district_names)

        school_keys_list: list[tuple[str, str]] = []
        for index, item in enumerate(raw_schools, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"school row {index} must be an object")
            school = cast(dict[str, Any], item)
            unknown_school = set(school) - SCHOOL_KEYS
            if unknown_school:
                raise ValueError(
                    f"school row {index} contains unsupported fields: {sorted(unknown_school)}"
                )
            name_value = school.get("name")
            district_value = school.get("district")
            if not isinstance(name_value, str) or not name_value.strip():
                raise ValueError(f"school row {index} requires a name")
            if not isinstance(district_value, str) or district_value not in district_name_set:
                raise ValueError(f"school row {index} requires a configured district")
            _validate_timezone(school.get("timezone"), f"school row {index}")
            _validate_notifications(school.get("notifications"), name_value.strip())
            school_keys_list.append((district_value, name_value.strip()))
        if len(set(school_keys_list)) != len(school_keys_list):
            raise ValueError(
                "multi-school pilot config contains duplicate district/school assignments"
            )
        school_keys = frozenset(school_keys_list)

        records = tuple(
            _parse_access_row(
                item,
                index,
                school_keys=school_keys,
                legacy=False,
            )
            for index, item in enumerate(raw_access, start=1)
        )
        district_count = len(district_names)
        school_count = len(school_keys)
    else:
        raise ValueError("pilot access JSON must be a legacy array or multi-school object")

    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        if record.email in seen:
            raise ValueError(f"pilot access row {index} duplicates an email")
        seen.add(record.email)
    return district_count, school_count, records


def validate_preflight(
    *,
    access_path: Path,
    platform_owner_email: str,
    academic_year_name: str,
    starts_on: date,
    ends_on: date,
) -> PreflightSummary:
    if not academic_year_name.strip():
        raise ValueError("academic_year_name must not be blank")
    if ends_on < starts_on:
        raise ValueError("academic year end must be on or after its start")

    district_count, school_count, records = _load_access(access_path)
    owner_email = platform_owner_email.strip().lower()
    if not owner_email.endswith(f"@{ALLOWED_DOMAIN}"):
        raise ValueError(f"platform owner must use the {ALLOWED_DOMAIN} school domain")

    owner = next((record for record in records if record.email == owner_email), None)
    if owner is None:
        raise ValueError("the configured platform owner is missing from the pilot access list")
    if not owner.is_active:
        raise ValueError("the configured platform owner must be active")
    if not {"platform_admin", "teacher"}.issubset(owner.roles):
        raise ValueError(
            "the configured platform owner must have concurrent platform_admin and teacher roles"
        )

    active_records = tuple(record for record in records if record.is_active)
    role_counts: Counter[str] = Counter(
        role for record in active_records for role in record.roles
    )
    if role_counts["teacher"] == 0:
        raise ValueError("the pilot access list requires at least one active teacher")
    if role_counts["school_admin"] == 0:
        raise ValueError("the pilot access list requires at least one active school_admin")

    return PreflightSummary(
        district_count=district_count,
        school_count=school_count,
        total_records=len(records),
        active_records=len(active_records),
        inactive_records=len(records) - len(active_records),
        active_teacher_records=role_counts["teacher"],
        active_school_admin_records=role_counts["school_admin"],
        active_district_admin_records=role_counts["district_admin"],
        active_platform_admin_records=role_counts["platform_admin"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate TPP pilot district, school, access, and academic-year inputs "
            "without mutating AWS or Supabase."
        )
    )
    parser.add_argument("--access-json", required=True, type=Path)
    parser.add_argument("--platform-owner-email", required=True)
    parser.add_argument("--academic-year-name", required=True)
    parser.add_argument("--starts-on", required=True)
    parser.add_argument("--ends-on", required=True)
    arguments = parser.parse_args()

    summary = validate_preflight(
        access_path=arguments.access_json,
        platform_owner_email=arguments.platform_owner_email,
        academic_year_name=arguments.academic_year_name,
        starts_on=_parse_date(arguments.starts_on, "starts_on"),
        ends_on=_parse_date(arguments.ends_on, "ends_on"),
    )

    print("TPP pilot access preflight passed.")
    print(f"Configured districts: {summary.district_count}")
    print(f"Configured schools: {summary.school_count}")
    print(f"Total access records: {summary.total_records}")
    print(f"Active access records: {summary.active_records}")
    print(f"Inactive access records: {summary.inactive_records}")
    print(f"Active teacher role grants: {summary.active_teacher_records}")
    print(f"Active school_admin role grants: {summary.active_school_admin_records}")
    print(f"Active district_admin role grants: {summary.active_district_admin_records}")
    print(f"Active platform_admin role grants: {summary.active_platform_admin_records}")
    print("Platform Owner concurrent platform_admin + teacher roles verified.")
    print("District-to-school assignments verified for configured professional accounts.")
    print("Data boundary verified: staff access only; no student roles are accepted.")


if __name__ == "__main__":
    main()
