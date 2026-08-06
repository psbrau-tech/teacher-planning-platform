from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

ALLOWED_DOMAIN = "anniston.k12.al.us"
ALLOWED_ROLES = frozenset({"teacher", "school_admin", "platform_admin"})
ALLOWED_ACCESS_KEYS = frozenset({"email", "display_name", "roles", "is_active"})


@dataclass(frozen=True, slots=True)
class AccessRecord:
    email: str
    display_name: str
    roles: tuple[str, ...]
    is_active: bool


@dataclass(frozen=True, slots=True)
class PreflightSummary:
    total_records: int
    active_records: int
    inactive_records: int
    active_teacher_records: int
    active_school_admin_records: int
    active_platform_admin_records: int


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)") from error


def _load_access(path: Path) -> tuple[AccessRecord, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("pilot access JSON must be a non-empty array")

    records: list[AccessRecord] = []
    seen: set[str] = set()
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"pilot access row {index} must be an object")
        record = cast(dict[str, Any], item)
        unknown = set(record) - ALLOWED_ACCESS_KEYS
        if unknown:
            raise ValueError(
                f"pilot access row {index} contains unsupported fields: {sorted(unknown)}"
            )

        email_value = record.get("email")
        display_name_value = record.get("display_name")
        roles_value = record.get("roles")
        active_value = record.get("is_active", True)

        if not isinstance(email_value, str) or not email_value.strip():
            raise ValueError(f"pilot access row {index} requires an email")
        email = email_value.strip().lower()
        if not email.endswith(f"@{ALLOWED_DOMAIN}"):
            raise ValueError(
                f"pilot access row {index} must use the {ALLOWED_DOMAIN} school domain"
            )
        if email in seen:
            raise ValueError(f"pilot access row {index} duplicates an email")
        seen.add(email)

        if not isinstance(display_name_value, str) or not display_name_value.strip():
            raise ValueError(f"pilot access row {index} requires a display_name")
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

        records.append(
            AccessRecord(
                email=email,
                display_name=display_name_value.strip(),
                roles=roles,
                is_active=active_value,
            )
        )

    return tuple(records)


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

    records = _load_access(access_path)
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
        total_records=len(records),
        active_records=len(active_records),
        inactive_records=len(records) - len(active_records),
        active_teacher_records=role_counts["teacher"],
        active_school_admin_records=role_counts["school_admin"],
        active_platform_admin_records=role_counts["platform_admin"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate TPP pilot access and academic-year inputs without mutating AWS or "
            "Supabase."
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
    print(f"Total access records: {summary.total_records}")
    print(f"Active access records: {summary.active_records}")
    print(f"Inactive access records: {summary.inactive_records}")
    print(f"Active teacher role grants: {summary.active_teacher_records}")
    print(f"Active school_admin role grants: {summary.active_school_admin_records}")
    print(f"Active platform_admin role grants: {summary.active_platform_admin_records}")
    print("Platform Owner concurrent platform_admin + teacher roles verified.")
    print("Data boundary verified: staff access only; no student roles are accepted.")


if __name__ == "__main__":
    main()
