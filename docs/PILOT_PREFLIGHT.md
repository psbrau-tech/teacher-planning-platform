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
12. The repository contains the expected Supabase migration set.

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

Treat this as a release defect. Do not proceed to bootstrap until the template validates in CI and in the preflight workflow.

## Controlled sequence

1. Merge the accepted release code.
2. Apply reviewed Supabase migrations.
3. Run the read-only preflight.
4. Provision the governed staff access list.
5. Run the preflight again before bootstrap if any AWS or GitHub environment value changed.
6. Bootstrap the isolated AWS pilot stack and first exact image.
7. Complete ACM, TLS, DNS, OAuth, and browser acceptance gates.

## Data boundary

The preflight accepts staff roles only: `teacher`, `school_admin`, and `platform_admin`. It has no student role, student roster, student account, or student-data input.
