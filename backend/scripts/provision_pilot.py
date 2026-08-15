from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg
from psycopg import Connection

ALLOWED_DOMAIN = "anniston.k12.al.us"
DISTRICT_NAME = "Anniston City Schools"
LEGACY_SCHOOL_NAME = "Anniston High School"
DEFAULT_TIMEZONE = "America/Chicago"
ALLOWED_ROLES = frozenset({"teacher", "school_admin", "district_admin", "platform_admin"})
LEGACY_ACCESS_KEYS = frozenset({"email", "display_name", "roles", "is_active"})
CONFIG_KEYS = frozenset({"schools", "access"})
SCHOOL_KEYS = frozenset({"name", "timezone", "notifications"})
NOTIFICATION_KEYS = frozenset(
    {
        "teacher_reminders_enabled",
        "teacher_reminder_local_time",
        "admin_digest_enabled",
        "admin_digest_local_time",
    }
)
ACCESS_KEYS = frozenset(
    {"email", "display_name", "school", "roles", "is_home", "is_active"}
)


@dataclass(frozen=True, slots=True)
class NotificationSettings:
    teacher_reminders_enabled: bool = False
    teacher_reminder_local_time: time = time(14, 0)
    admin_digest_enabled: bool = False
    admin_digest_local_time: time = time(15, 30)


@dataclass(frozen=True, slots=True)
class SchoolRecord:
    name: str
    timezone: str
    notifications: NotificationSettings


@dataclass(frozen=True, slots=True)
class AccessRecord:
    email: str
    display_name: str
    school_name: str
    roles: tuple[str, ...]
    is_home: bool
    is_active: bool


@dataclass(frozen=True, slots=True)
class PilotConfig:
    schools: tuple[SchoolRecord, ...]
    access: tuple[AccessRecord, ...]


def _parse_date(value: str, name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO date (YYYY-MM-DD)") from error


def _parse_local_time(value: object, name: str, default: time) -> time:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{name} must use HH:MM local time")
    try:
        parsed = time.fromisoformat(value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must use HH:MM local time") from error
    if parsed.second or parsed.microsecond or parsed.tzinfo is not None:
        raise ValueError(f"{name} must use HH:MM local time")
    return parsed


def _validate_timezone(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires an IANA timezone")
    timezone_name = value.strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"{name} contains an invalid IANA timezone") from error
    return timezone_name


def _parse_notifications(value: object, school_name: str) -> NotificationSettings:
    if value is None:
        return NotificationSettings()
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

    return NotificationSettings(
        teacher_reminders_enabled=teacher_enabled,
        teacher_reminder_local_time=_parse_local_time(
            payload.get("teacher_reminder_local_time"),
            f"{school_name} teacher_reminder_local_time",
            time(14, 0),
        ),
        admin_digest_enabled=admin_enabled,
        admin_digest_local_time=_parse_local_time(
            payload.get("admin_digest_local_time"),
            f"{school_name} admin_digest_local_time",
            time(15, 30),
        ),
    )


def _parse_school(item: object, index: int) -> SchoolRecord:
    if not isinstance(item, dict):
        raise ValueError(f"school row {index} must be an object")
    payload = cast(dict[str, Any], item)
    unknown = set(payload) - SCHOOL_KEYS
    if unknown:
        raise ValueError(f"school row {index} contains unsupported fields: {sorted(unknown)}")

    name_value = payload.get("name")
    if not isinstance(name_value, str) or not name_value.strip():
        raise ValueError(f"school row {index} requires a name")
    school_name = name_value.strip()
    timezone_name = _validate_timezone(payload.get("timezone"), f"school row {index}")
    return SchoolRecord(
        name=school_name,
        timezone=timezone_name,
        notifications=_parse_notifications(payload.get("notifications"), school_name),
    )


def _parse_access_record(
    item: object,
    index: int,
    *,
    school_names: frozenset[str],
    legacy_school: str | None = None,
) -> AccessRecord:
    if not isinstance(item, dict):
        raise ValueError(f"pilot access row {index} must be an object")
    payload = cast(dict[str, Any], item)
    allowed_keys = LEGACY_ACCESS_KEYS if legacy_school is not None else ACCESS_KEYS
    unknown = set(payload) - allowed_keys
    if unknown:
        raise ValueError(
            f"pilot access row {index} contains unsupported fields: {sorted(unknown)}"
        )

    email_value = payload.get("email")
    display_name_value = payload.get("display_name")
    roles_value = payload.get("roles")
    active_value = payload.get("is_active", True)
    home_value = True if legacy_school is not None else payload.get("is_home", True)
    school_value = legacy_school if legacy_school is not None else payload.get("school")

    if not isinstance(email_value, str) or not email_value.strip():
        raise ValueError(f"pilot access row {index} requires an email")
    email = email_value.strip().lower()
    if not email.endswith(f"@{ALLOWED_DOMAIN}"):
        raise ValueError(
            f"pilot access row {index} must use the {ALLOWED_DOMAIN} school domain"
        )
    if not isinstance(display_name_value, str) or not display_name_value.strip():
        raise ValueError(f"pilot access row {index} requires a display_name")
    if not isinstance(school_value, str) or school_value not in school_names:
        raise ValueError(f"pilot access row {index} requires a configured school")
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
    if not isinstance(home_value, bool):
        raise ValueError(f"pilot access row {index} is_home must be boolean")

    return AccessRecord(
        email=email,
        display_name=display_name_value.strip(),
        school_name=school_value,
        roles=roles,
        is_home=home_value,
        is_active=active_value,
    )


def _validate_access_memberships(records: tuple[AccessRecord, ...]) -> None:
    seen_memberships: set[tuple[str, str]] = set()
    active_by_email: dict[str, list[AccessRecord]] = defaultdict(list)
    for index, record in enumerate(records, start=1):
        membership = (record.email, record.school_name)
        if membership in seen_memberships:
            raise ValueError(
                f"pilot access row {index} duplicates an email/school membership"
            )
        seen_memberships.add(membership)
        if record.is_active:
            active_by_email[record.email].append(record)

    for email, memberships in active_by_email.items():
        home_count = sum(1 for membership in memberships if membership.is_home)
        if home_count != 1:
            raise ValueError(
                f"active professional account {email} requires exactly one home school"
            )


def _load_config(path: Path) -> PilotConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))

    # Backward compatibility keeps the currently deployed AHS secret valid until the operator
    # intentionally replaces it with the new multi-school shape.
    if isinstance(payload, list):
        if not payload:
            raise ValueError("pilot access JSON must be a non-empty array")
        schools = (
            SchoolRecord(
                name=LEGACY_SCHOOL_NAME,
                timezone=DEFAULT_TIMEZONE,
                notifications=NotificationSettings(),
            ),
        )
        access = tuple(
            _parse_access_record(
                item,
                index,
                school_names=frozenset({LEGACY_SCHOOL_NAME}),
                legacy_school=LEGACY_SCHOOL_NAME,
            )
            for index, item in enumerate(payload, start=1)
        )
        _validate_access_memberships(access)
        return PilotConfig(schools=schools, access=access)

    if not isinstance(payload, dict):
        raise ValueError("pilot access JSON must be a legacy array or multi-school object")
    config = cast(dict[str, Any], payload)
    unknown = set(config) - CONFIG_KEYS
    if unknown:
        raise ValueError(f"pilot access config contains unsupported fields: {sorted(unknown)}")

    raw_schools = config.get("schools")
    raw_access = config.get("access")
    if not isinstance(raw_schools, list) or not raw_schools:
        raise ValueError("multi-school pilot config requires a non-empty schools array")
    if not isinstance(raw_access, list) or not raw_access:
        raise ValueError("multi-school pilot config requires a non-empty access array")

    schools = tuple(_parse_school(item, index) for index, item in enumerate(raw_schools, 1))
    school_names = [school.name for school in schools]
    if len(set(school_names)) != len(school_names):
        raise ValueError("multi-school pilot config contains duplicate school names")

    access = tuple(
        _parse_access_record(
            item,
            index,
            school_names=frozenset(school_names),
        )
        for index, item in enumerate(raw_access, start=1)
    )
    _validate_access_memberships(access)
    return PilotConfig(schools=schools, access=access)


def _single_id(
    connection: Connection[tuple[Any, ...]], query: str, values: tuple[Any, ...]
) -> str:
    with connection.cursor() as cursor:
        cursor.execute(query, values)
        row = cursor.fetchone()
    if row is None or not isinstance(row[0], str):
        raise RuntimeError("pilot provisioning did not return a required identifier")
    return row[0]


def _school_id(
    connection: Connection[tuple[Any, ...]], *, district_id: str, school: SchoolRecord
) -> str:
    school_id = _single_id(
        connection,
        """
        with existing as (
          select id from public.schools
          where district_id = %s::uuid and name = %s
          order by created_at
          limit 1
        ), inserted as (
          insert into public.schools (district_id, name, timezone)
          select %s::uuid, %s, %s
          where not exists (select 1 from existing)
          returning id
        )
        select id::text from existing
        union all
        select id::text from inserted
        limit 1
        """,
        (district_id, school.name, district_id, school.name, school.timezone),
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "update public.schools set timezone = %s where id = %s::uuid",
            (school.timezone, school_id),
        )
    return school_id


def provision(
    *,
    database_url: str,
    access_path: Path,
    platform_owner_email: str,
    academic_year_name: str,
    starts_on: date,
    ends_on: date,
    replace_access: bool,
) -> tuple[int, int, int]:
    if ends_on < starts_on:
        raise ValueError("academic year end must be on or after its start")
    config = _load_config(access_path)
    owner_email = platform_owner_email.strip().lower()
    owner_memberships = [
        record for record in config.access if record.email == owner_email and record.is_active
    ]
    if not owner_memberships:
        raise ValueError("the configured platform owner is missing from the pilot access list")
    owner_roles = {role for record in owner_memberships for role in record.roles}
    if not {"platform_admin", "teacher"}.issubset(owner_roles):
        raise ValueError(
            "the configured platform owner must have concurrent platform_admin and teacher roles"
        )

    with psycopg.connect(database_url) as connection:
        with connection.transaction():
            district_id = _single_id(
                connection,
                """
                with existing as (
                  select id from public.districts
                  where name = %s
                  order by created_at
                  limit 1
                ), inserted as (
                  insert into public.districts (name)
                  select %s
                  where not exists (select 1 from existing)
                  returning id
                )
                select id::text from existing
                union all
                select id::text from inserted
                limit 1
                """,
                (DISTRICT_NAME, DISTRICT_NAME),
            )

            school_ids: dict[str, str] = {}
            for school in config.schools:
                school_id = _school_id(connection, district_id=district_id, school=school)
                school_ids[school.name] = school_id
                with connection.cursor() as cursor:
                    cursor.execute(
                        "update public.academic_years set is_active = false where school_id = %s::uuid",
                        (school_id,),
                    )
                    cursor.execute(
                        """
                        insert into public.academic_years (
                          school_id, name, starts_on, ends_on, is_active
                        ) values (%s::uuid, %s, %s, %s, true)
                        on conflict do nothing
                        """,
                        (school_id, academic_year_name.strip(), starts_on, ends_on),
                    )
                    cursor.execute(
                        """
                        update public.academic_years
                        set starts_on = %s,
                            ends_on = %s,
                            is_active = true
                        where school_id = %s::uuid and name = %s
                        """,
                        (starts_on, ends_on, school_id, academic_year_name.strip()),
                    )
                    cursor.execute(
                        """
                        insert into public.school_notification_settings (
                          school_id,
                          teacher_reminders_enabled,
                          teacher_reminder_local_time,
                          admin_digest_enabled,
                          admin_digest_local_time,
                          updated_at
                        ) values (%s::uuid, %s, %s, %s, %s, now())
                        on conflict (school_id) do update set
                          teacher_reminders_enabled = excluded.teacher_reminders_enabled,
                          teacher_reminder_local_time = excluded.teacher_reminder_local_time,
                          admin_digest_enabled = excluded.admin_digest_enabled,
                          admin_digest_local_time = excluded.admin_digest_local_time,
                          updated_at = now()
                        """,
                        (
                            school_id,
                            school.notifications.teacher_reminders_enabled,
                            school.notifications.teacher_reminder_local_time,
                            school.notifications.admin_digest_enabled,
                            school.notifications.admin_digest_local_time,
                        ),
                    )

            with connection.cursor() as cursor:
                if replace_access:
                    for school_id in school_ids.values():
                        cursor.execute(
                            """
                            update private.pilot_access_allowlist
                            set is_active = false,
                                is_home = false,
                                updated_at = now()
                            where school_id = %s::uuid
                            """,
                            (school_id,),
                        )

                # Clear home flags first so a governed home-school reassignment cannot violate
                # the one-active-home unique index while the replacement rows are being applied.
                for email in sorted({record.email for record in config.access}):
                    cursor.execute(
                        """
                        update private.pilot_access_allowlist
                        set is_home = false,
                            updated_at = now()
                        where email = %s
                        """,
                        (email,),
                    )

                for record in config.access:
                    cursor.execute(
                        """
                        insert into private.pilot_access_allowlist (
                          email, school_id, display_name, roles, is_home, is_active, updated_at
                        ) values (
                          %s, %s::uuid, %s, %s::public.app_role[], %s, %s, now()
                        )
                        on conflict (email, school_id) do update set
                          display_name = excluded.display_name,
                          roles = excluded.roles,
                          is_home = excluded.is_home,
                          is_active = excluded.is_active,
                          updated_at = now()
                        """,
                        (
                            record.email,
                            school_ids[record.school_name],
                            record.display_name,
                            list(record.roles),
                            record.is_home,
                            record.is_active,
                        ),
                    )

                cursor.execute(
                    """
                    select count(*)::integer
                    from private.pilot_access_allowlist a
                    join public.schools s on s.id = a.school_id
                    where s.district_id = %s::uuid and a.is_active
                    """,
                    (district_id,),
                )
                active_count_row = cursor.fetchone()
                cursor.execute(
                    """
                    select count(*)::integer
                    from public.profile_roles pr
                    join public.schools s on s.id = pr.school_id
                    where s.district_id = %s::uuid
                    """,
                    (district_id,),
                )
                role_count_row = cursor.fetchone()

    active_count = int(active_count_row[0]) if active_count_row else 0
    role_count = int(role_count_row[0]) if role_count_row else 0
    return len(config.schools), active_count, role_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision governed Anniston TPP schools, notification settings, and staff access."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--access-json", required=True, type=Path)
    parser.add_argument("--platform-owner-email", required=True)
    parser.add_argument("--academic-year-name", required=True)
    parser.add_argument("--starts-on", required=True)
    parser.add_argument("--ends-on", required=True)
    parser.add_argument("--replace-access", action="store_true")
    arguments = parser.parse_args()

    school_count, active_count, role_count = provision(
        database_url=arguments.database_url,
        access_path=arguments.access_json,
        platform_owner_email=arguments.platform_owner_email,
        academic_year_name=arguments.academic_year_name,
        starts_on=_parse_date(arguments.starts_on, "starts_on"),
        ends_on=_parse_date(arguments.ends_on, "ends_on"),
        replace_access=arguments.replace_access,
    )
    print(f"Pilot provisioning complete: {school_count} configured schools.")
    print(f"Governed access complete: {active_count} active school memberships.")
    print(f"Existing authenticated users currently hold {role_count} governed role records.")


if __name__ == "__main__":
    main()
