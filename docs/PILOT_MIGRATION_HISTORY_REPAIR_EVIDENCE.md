# TPP Pilot Migration-History Repair Evidence

**Database project:** dedicated TPP Supabase project  
**Inspection mode:** read-only  
**Date:** August 6, 2026

## Remote history inspection

The remote migration table contained four versions that were absent from the repository migration directory:

- `20260805200342` — `v1_foundation`
- `20260805200357` — `reporting_and_templates`
- `20260805200405` — `weekly_plan_draft_revisions`
- `20260805200432` — `reporting_view_security`

The stored SQL statements for those records were compared with the committed canonical migration files. They correspond to:

- `202608040001_v1_foundation.sql`
- `202608040002_reporting_and_templates.sql`
- `202608050001_weekly_plan_draft_revisions.sql`
- `202608060001_reporting_view_security.sql`

`20260805203624_governed_multi_role_access_and_rls.sql` already matched locally and remotely and is excluded from repair.

## Remote schema inspection

The following objects were confirmed absent:

- `public.friday_validation_snapshots`
- `districts_name_unique`
- `schools_district_name_unique`
- `academic_years_school_name_unique`
- `private.sync_friday_instruction_records()`
- `sync_friday_instruction_records_trigger`

Therefore the following local migrations are genuinely pending and must not be marked applied by the history repair:

- `20260805210000_friday_validation_snapshots.sql`
- `20260805211000_pilot_tenant_uniqueness.sql`
- `20260805212000_sync_friday_instruction_records.sql`

The two post-merge forward migrations are also pending:

- `20260806133000_reporting_multi_role_accuracy.sql`
- `20260806141500_fix_allowlist_sync_trigger.sql`

## Repair conclusion

The controlled correction is to remove only the four duplicate remote aliases from migration history and insert only the four canonical repository timestamps as applied. No schema SQL is executed by the repair operation. A subsequent `db push --dry-run` must list the five genuinely pending migrations before any schema application is authorized.
