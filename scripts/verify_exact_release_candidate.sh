#!/usr/bin/env bash
set -euo pipefail

expected_main_sha="${EXPECTED_MAIN_SHA:-}"
expected_migration_head="${EXPECTED_MIGRATION_HEAD:-}"
require_applied_confirmation="${REQUIRE_MIGRATION_APPLIED_CONFIRMATION:-false}"
applied_confirmed="${MIGRATION_APPLIED_CONFIRMED:-false}"

if [[ "${GITHUB_REF:-}" != "refs/heads/main" ]]; then
  echo "Controlled release workflows must run from refs/heads/main; received ${GITHUB_REF:-unset}." >&2
  exit 1
fi

if [[ -z "$expected_main_sha" || ! "$expected_main_sha" =~ ^[0-9a-f]{40}$ ]]; then
  echo "EXPECTED_MAIN_SHA must be an exact 40-character Git commit SHA." >&2
  exit 1
fi
if [[ "${GITHUB_SHA:-}" != "$expected_main_sha" ]]; then
  echo "Release candidate moved: expected $expected_main_sha, workflow is running $GITHUB_SHA." >&2
  exit 1
fi

if [[ -z "$expected_migration_head" || ! "$expected_migration_head" =~ ^[0-9]{12,14}$ ]]; then
  echo "EXPECTED_MIGRATION_HEAD must be the numeric prefix of one repository migration." >&2
  exit 1
fi

mapfile -t migration_matches < <(
  find supabase/migrations -maxdepth 1 -type f \
    -name "${expected_migration_head}_*.sql" -print | sort
)
if (( ${#migration_matches[@]} != 1 )); then
  echo "Expected exactly one repository migration for head $expected_migration_head; found ${#migration_matches[@]}." >&2
  exit 1
fi

if [[ "$require_applied_confirmation" == "true" && "$applied_confirmed" != "true" ]]; then
  echo "Deployment is blocked until the exact target migration head is confirmed applied." >&2
  exit 1
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "migration_file=${migration_matches[0]}" >> "$GITHUB_OUTPUT"
fi

printf 'Exact release candidate verified: commit=%s migration=%s\n' \
  "$expected_main_sha" "$expected_migration_head"
