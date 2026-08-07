# TPP Pilot Migration-History Repair Runbook

## Before running

- Confirm the protected `tpp-pilot` GitHub environment still contains the accepted AWS OIDC role and database secret configuration.
- Confirm no other TPP database workflow is running.
- Review `PILOT_MIGRATION_HISTORY_REPAIR_EVIDENCE.md`.

## Review-only run

Run **Repair TPP Pilot Migration History** from GitHub Actions with:

- `reason`: `Review verified duplicate migration timestamps`
- `apply_repair`: `false`
- `confirmation`: leave blank

Expected result:

- current migration list is displayed;
- no database mutation occurs;
- the workflow summary lists the four verified timestamp mappings.

## Apply run

After the review-only run is accepted, run the same workflow with:

- `reason`: `Reconcile verified duplicate migration timestamps`
- `apply_repair`: `true`
- `confirmation`: `REPAIR_TPP_HISTORY`

Expected result:

- four remote alias records are marked reverted;
- four canonical repository versions are marked applied;
- no schema SQL is executed;
- the post-repair dry run includes all reviewed pending migrations, including versions that sort before the latest remote migration;
- the pending set is exactly:
  - `20260805210000`
  - `20260805211000`
  - `20260805212000`
  - `20260806133000`
  - `20260806141500`

The workflows use Supabase CLI `--include-all` because the first three genuinely pending migrations sort before the already-applied `202608060001` migration. Without that flag, Supabase stops with an out-of-order migration warning even though the repaired migration history is correct.

If the history repair completed but its final dry run failed only with the `--include-all` warning, verify the live migration table before rerunning the repair. Do not repeat a successful history mutation merely to obtain a green workflow result.

## After repair

Return to **Apply TPP Pilot Database Migrations** and run:

- `reason`: `Preview reconciled TPP pilot migrations`
- `dry_run_only`: `true`

Do not apply schema migrations until that dry run confirms only the five expected versions above are pending.
