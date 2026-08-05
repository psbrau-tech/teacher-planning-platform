from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

import psycopg
from psycopg import Connection

ALLOWED_DOMAIN = "anniston.k12.al.us"
ALLOWED_ROLES = frozenset({"teacher", "school_admin", "platform_admin"})
ALLOWED_ACCESS_KEYS = frozenset({"email", "display_name", "roles", "is_active"})


@dataclass(frozen=True, slots=True)
class AccessRecord:
    email: str
    display_name: str
    roles: tuple[str, ...]
    is_active: bool


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


def _single_id(connection: Connection[tuple[Any, ...]], query: str, values: tuple[Any, ...]) -> str:
    with connection.cursor() as cursor:
        cursor.execute(query, values)
        row = cursor.fetchone()
    if row is None or not isinstance(row[0], str):
        raise RuntimeError("pilot provisioning did not return a required identifier")
    return row[0]


def provision(
    *,
    database_url: str,
    access_path: Path,
    platform_owner_email: str,
    academic_year_name: str,
    starts_on: date,
    ends_on: date,
    replace_access: bool,
) -> tuple[int, int]:
    if ends_on < starts_on:
        raise ValueError("academic year end must be on or after its start")
    records = _load_access(access_path)
    owner_email = platform_owner_email.strip().lower()
    owner = next((record for record in records if record.email == owner_email), None)
    if owner is None:
        raise ValueError("the configured platform owner is missing from the pilot access list")
    if not {"platform_admin", "teacher"}.issubset(owner.roles):
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
                ("Anniston City Schools", "Anniston City Schools"),
            )
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
                  select %s::uuid, %s, 'America/Chicago'
                  where not exists (select 1 from existing)
                  returning id
                )
                select id::text from existing
                union all
                select id::text from inserted
                limit 1
                """,
                (
                    district_id,
                    "Anniston High School",
                    district_id,
                    "Anniston High School",
                ),
            )

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

                if replace_access:
                    cursor.execute(
                        """
                        update private.pilot_access_allowlist
                        set is_active = false,
                            updated_at = now()
                        where school_id = %s::uuid
                        """,
                        (school_id,),
                    )

                for record in records:
                    cursor.execute(
                        """
                        insert into private.pilot_access_allowlist (
                          email, school_id, display_name, roles, is_active
                        ) values (
                          %s, %s::uuid, %s, %s::public.app_role[], %s
                        )
                        on conflict (email) do update set
                          school_id = excluded.school_id,
                          display_name = excluded.display_name,
                          roles = excluded.roles,
                          is_active = excluded.is_active,
                          updated_at = now()
                        """,
                        (
                            record.email,
                            school_id,
                            record.display_name,
                            list(record.roles),
                            record.is_active,
                        ),
                    )

            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select count(*)::integer
                    from private.pilot_access_allowlist
                    where school_id = %s::uuid and is_active
                    """,
                    (school_id,),
                )
                active_count_row = cursor.fetchone()
                cursor.execute(
                    """
                    select count(*)::integer
                    from public.profile_roles
                    where school_id = %s::uuid
                    """,
                    (school_id,),
                )
                role_count_row = cursor.fetchone()

    active_count = int(active_count_row[0]) if active_count_row else 0
    role_count = int(role_count_row[0]) if role_count_row else 0
    return active_count, role_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision the governed Anniston teacher-planning pilot tenant and access list."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--access-json", required=True, type=Path)
    parser.add_argument("--platform-owner-email", required=True)
    parser.add_argument("--academic-year-name", required=True)
    parser.add_argument("--starts-on", required=True)
    parser.add_argument("--ends-on", required=True)
    parser.add_argument("--replace-access", action="store_true")
    arguments = parser.parse_args()

    active_count, role_count = provision(
        database_url=arguments.database_url,
        access_path=arguments.access_json,
        platform_owner_email=arguments.platform_owner_email,
        academic_year_name=arguments.academic_year_name,
        starts_on=_parse_date(arguments.starts_on, "starts_on"),
        ends_on=_parse_date(arguments.ends_on, "ends_on"),
        replace_access=arguments.replace_access,
    )
    print(f"Pilot provisioning complete: {active_count} active access records.")
    print(f"Existing authenticated users currently hold {role_count} governed role records.")


if __name__ == "__main__":
    main()
