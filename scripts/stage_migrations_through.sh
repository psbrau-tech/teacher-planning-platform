#!/usr/bin/env bash
set -euo pipefail

target_head="${1:-}"
deferred_dir="${2:-${RUNNER_TEMP:-/tmp}/tpp-deferred-migrations}"

if [[ -z "$target_head" || ! "$target_head" =~ ^[0-9]{12,14}$ ]]; then
  echo "Usage: stage_migrations_through.sh <target-migration-head> [deferred-dir]" >&2
  exit 2
fi

mapfile -t target_matches < <(
  find supabase/migrations -maxdepth 1 -type f -name "${target_head}_*.sql" -print | sort
)
if (( ${#target_matches[@]} != 1 )); then
  echo "Expected exactly one target migration for $target_head; found ${#target_matches[@]}." >&2
  exit 1
fi

rm -rf "$deferred_dir"
mkdir -p "$deferred_dir"

deferred_count=0
while IFS= read -r migration; do
  file_name="$(basename "$migration")"
  version="${file_name%%_*}"
  if [[ "$version" > "$target_head" ]]; then
    mv "$migration" "$deferred_dir/$file_name"
    deferred_count=$((deferred_count + 1))
  fi
done < <(find supabase/migrations -maxdepth 1 -type f -name '*.sql' -print | sort)

if [[ ! -f "${target_matches[0]}" ]]; then
  echo "Target migration was unexpectedly deferred." >&2
  exit 1
fi

remaining_head="$(
  find supabase/migrations -maxdepth 1 -type f -name '*.sql' -printf '%f\n' \
    | sort | tail -n 1
)"
if [[ "${remaining_head%%_*}" != "$target_head" ]]; then
  echo "Staged migration head is ${remaining_head:-none}; expected $target_head." >&2
  exit 1
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "deferred_count=$deferred_count" >> "$GITHUB_OUTPUT"
  echo "staged_head=$target_head" >> "$GITHUB_OUTPUT"
fi

printf 'Staged migrations through %s; deferred %d later migration(s).\n' \
  "$target_head" "$deferred_count"
