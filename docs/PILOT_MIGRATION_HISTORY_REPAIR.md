# TPP Pilot Migration-History Reconciliation

## Scope

This procedure corrects the Supabase migration tracking table after four early repository migrations were applied to the pilot database under later generated timestamps.

It does **not** execute, revert, or reapply schema SQL. It only replaces verified duplicate history identifiers with the canonical timestamps committed in `supabase/migrations`.

## Verified mappings

| Remote history version | Remote migration name | Canonical repository version |
|---|---|---|
| `20260805200342` | `v1_foundation` | `202608040001` |
| `20260805200357` | `reporting_and_templates` | `202608040002` |
| `20260805200405` | `weekly_plan_draft_revisions` | `202608050001` |
| `20260805200432` | `reporting_view_security` | `202608060001` |

The stored remote statements were reviewed against the canonical repository files before this repair workflow was added.

## Versions that must remain untouched

`20260805203624` already matches locally and remotely. It is not part of the repair.

The following repository migrations are genuinely pending because their database objects were confirmed absent during read-only inspection:

- `20260805210000_friday_validation_snapshots.sql`
- `20260805211000_pilot_tenant_uniqueness.sql`
- `20260805212000_sync_friday_instruction_records.sql`
- `20260806133000_reporting_multi_role_accuracy.sql`
- `20260806141500_fix_allowlist_sync_trigger.sql`

They must not be marked applied until their SQL is actually executed by the protected migration workflow.

## Controlled workflow

Use **Repair TPP Pilot Migration History** from GitHub Actions.

1. Run first with `apply_repair=false` and review the migration list and workflow summary.
2. Run again with `apply_repair=true` and confirmation `REPAIR_TPP_HISTORY`.
3. Confirm the post-repair dry run succeeds and lists only the genuinely pending migrations above.
4. Return to **Apply TPP Pilot Database Migrations** and run its dry-run gate before authorizing schema changes.

## Safety boundary

- GitHub OIDC only; no long-lived AWS credentials.
- Protected `tpp-pilot` environment.
- Dedicated TPP Supabase project.
- Teacher and curriculum data only; no student data.
- No direct editing of `supabase_migrations.schema_migrations` through the SQL editor.
