# TPP Pilot Release Preflight

## Purpose

Run **Preflight TPP Pilot Release** before staff provisioning, the initial AWS bootstrap, TLS attachment, or a subsequent application deployment whenever protected environment configuration has changed.

The workflow is read-only. It does not retrieve secret values, write to Supabase, deploy CloudFormation, push an image, change ECS, request a certificate, or modify DNS.

## What the preflight checks

1. The protected GitHub environment `tpp-pilot` supplies all required values:
   - `TPP_AWS_ROLE_ARN`
   - `TPP_PLATFORM_OWNER_EMAIL`
   - `TPP_SUPABASE_URL`
   - `TPP_SUPABASE_ANON_KEY`
   - secret `TPP_PILOT_ACCESS_JSON`
2. Region governance remains locked to `us-east-2`.
3. The Platform Owner email uses `anniston.k12.al.us`.
4. The access-list secret is valid JSON and contains only supported fields.
5. Every access record:
   - uses an Anniston school email;
   - has a nonblank display name;
   - has at least one approved role;
   - has a boolean active state when supplied;
   - does not duplicate another email.
6. The Platform Owner is active and retains both `platform_admin` and `teacher`.
7. At least one active `teacher` and one active `school_admin` are present for acceptance testing.
8. Academic-year dates are valid and ordered correctly.
9. GitHub OIDC can assume the configured AWS role.
10. All required AWS Secrets Manager entries exist by metadata lookup:
    - Supabase URL
    - Supabase anon key
    - Supabase service-role key
    - database URL
    - OpenAI API key
    - Google OAuth client ID
    - Google OAuth client secret
11. The CloudFormation template passes AWS validation.
12. The repository contains the complete timestamped Supabase migration inventory.

Preflight validates source/configuration readiness; it does **not** prove that a particular migration is applied to the live pilot database. Live migration history is separate release evidence from **Apply TPP Pilot Database Migrations**.

## Running the workflow

Open:

**GitHub → Actions → Preflight TPP Pilot Release → Run workflow**

Use the same academic-year label and governed dates intended for **Provision TPP Pilot Access**.

Recommended reason:

`Validate protected pilot configuration before provisioning and bootstrap`

Approve the `tpp-pilot` environment when prompted.

## Interpreting failures

### Missing environment values

The workflow reports every missing required value in one failure instead of stopping at the first missing item. Add the values under:

**Repository → Settings → Environments → tpp-pilot**

Use environment **variables** for non-secret configuration and environment **secrets** for the protected staff-access JSON.

### Access-list validation failure

Correct the JSON in `TPP_PILOT_ACCESS_JSON`. Do not paste real staff addresses into issues, pull requests, workflow summaries, repository files, screenshots, or chat messages.

### AWS OIDC failure

Verify that `TPP_AWS_ROLE_ARN` identifies the approved GitHub Actions role and that its trust policy permits this repository and the `tpp-pilot` environment.

### Secrets Manager metadata failure

Create the missing secret or correct the corresponding optional secret-ID override. The preflight checks only that the secret exists; it does not read or display the secret value.

### CloudFormation failure

Treat this as a release defect. Do not proceed to bootstrap or deployment until the template validates in CI and in the preflight workflow.

### Migration inventory change

Any merged branch that adds a migration requires a new protected migration review. Do not infer the live database head from the repository's latest filename.

**Apply TPP Pilot Database Migrations** is target-scoped and uses a pinned Supabase CLI version rather than the moving `latest` channel. Each run requires:

- the exact accepted `main` SHA;
- one exact `target_migration_head` that exists in the repository;
- dry-run preview by default; and
- a separate `apply_target_confirmed=true` acknowledgement before mutation.

The workflow temporarily removes migrations later than the approved target from the runner's Supabase migration directory. Its preview, apply, migration list, and final dry-run therefore concern only migrations through that target. A later source migration may remain intentionally deferred when the release runbook permits it.

For the August 14 professional-learning/application release, `20260815001500` is the planned target boundary and `20260815011000_scheduled_admin_digest_worker.sql` remains deferred until automatic delivery is separately prepared.

## Controlled sequence

1. Merge every intended release change and record the exact resulting `main` SHA.
2. Select the exact migration target for the release; do not default automatically to the repository's newest migration when a later feature is intentionally deferred.
3. Run **Apply TPP Pilot Database Migrations** from `main` with the exact SHA/head, `dry_run_only=true`, and `apply_target_confirmed=false`; review the target-scoped pending list.
4. Run an approved apply with the **same** SHA/head, `dry_run_only=false`, and `apply_target_confirmed=true` only after the preview is accepted.
5. Retain the migration-list/final-dry-run evidence showing no migration remains pending through the selected target.
6. Run the read-only preflight.
7. Provision the governed staff access list if provisioning changes are part of the release.
8. Run the preflight again before infrastructure mutation if any AWS or GitHub environment value changed.
9. For an existing pilot, use **Deploy TPP Pilot** with the exact accepted `main` SHA, the exact applied migration head, `migration_head_applied_confirmed=true`, and the exact-candidate Help review confirmation.
10. Complete deployment verification and release-specific browser/API acceptance.

For a brand-new stack, bootstrap/TLS/DNS/OAuth steps still follow the controlled pilot deployment guide after migration, preflight, and provisioning gates pass.

## Retry boundaries

- Preflight can be rerun safely because it is read-only.
- The migration workflow defaults to dry-run; a mutating retry must use the same reviewed exact SHA/head unless a new release candidate is deliberately accepted.
- Provisioning is transaction-safe and can update the same approved records.
- Bootstrap can resume the same accepted commit after a partial failure, but it will not replace an existing service with a different commit.
- **Deploy TPP Pilot** is the only workflow for application upgrades after bootstrap.
- Repeated deployment of the same commit reuses its immutable ECR digest and does not force an unnecessary task-definition revision.
- TLS attachment preserves and verifies the active exact image.
- SES sender activation and scheduled-worker activation are separate controlled workflows; neither is implied by a normal application deployment.

## Data boundary

The preflight accepts staff roles only: `teacher`, `school_admin`, and `platform_admin`. It has no student role, student roster, student account, or student-data input.
