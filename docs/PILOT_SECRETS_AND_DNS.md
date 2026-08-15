# Teacher Planning Platform Pilot Secrets and DNS

This is the controlled setup checklist for `planner.guidedscholar.ai` while authoritative DNS remains in Cloudflare and the isolated application stack is deployed in the existing AWS account in `us-east-2`.

## Security boundary

- Teacher and curriculum data only.
- No student names, IDs, grades, IEP information, accommodations tied to named students, or other student-specific data.
- Never place keys, connection strings, or staff access lists in source files, screenshots, issues, pull-request comments, workflow summaries, or chat messages.
- GitHub Actions authenticates to AWS through OIDC. Long-lived AWS access keys are prohibited.
- The running ECS container uses a read-only root filesystem with a dedicated writable `/tmp` volume.

## AWS Secrets Manager

The controlled workflows use these exact secret IDs unless the corresponding GitHub environment variable overrides the name:

- `tpp/pilot/supabase-url`
- `tpp/pilot/supabase-anon-key`
- `tpp/pilot/supabase-service-role-key`
- `tpp/pilot/database-url`
- `tpp/pilot/openai-api-key`
- `tpp/pilot/google-oauth-client-id`
- `tpp/pilot/google-oauth-client-secret`

Each secret contains only its raw value.

### Credentials allowed in the interactive ECS web task

The current AI-enabled interactive runtime receives only the three governed secret mappings required by application code:

- `TPP_SUPABASE_URL` from `tpp/pilot/supabase-url`;
- `TPP_SUPABASE_ANON_KEY` from `tpp/pilot/supabase-anon-key`; and
- `TPP_OPENAI_API_KEY` from `tpp/pilot/openai-api-key`.

The Supabase values support JWT verification and user-token REST requests governed by row-level security. The OpenAI key supports the reviewed AI planning and post-submission Reflection Intelligence paths. It does not change the no-student-data boundary, and required Weekly Reflection / PLC Discussion responses remain teacher-authored.

The interactive web task must **not** receive:

- the Supabase service-role key;
- the PostgreSQL database URL;
- the Google OAuth client ID or client secret.

Those privileged credentials remain outside the interactive application task. Database migration and staff provisioning workflows retrieve the database connection only for their protected operation. Google provider configuration occurs in Supabase and Google consoles. The deployment verification workflow fails if a prohibited privileged credential appears in the ECS task as plaintext or a secret mapping.

### Notification and scheduled-worker credential boundary

Manual admin email delivery uses the interactive task's AWS task role for `ses:SendEmail` only after the SES sender is separately activated. `TPP_SES_FROM_EMAIL` and `TPP_SES_REGION` are non-secret runtime configuration; they are not AWS access keys.

The optional automatic weekly digest uses a **separate scheduled ECS task**, not the interactive web task. Only that isolated worker may receive `TPP_SUPABASE_SERVICE_ROLE_KEY`, together with `TPP_SUPABASE_URL`, after the scheduled-worker database/AWS activation gates are approved. The scheduled worker must not receive the OpenAI key, Supabase anon key, or Google OAuth secrets.

## GitHub environment: `tpp-pilot`

### Required variables

- `TPP_AWS_REGION` = `us-east-2`
- `TPP_AWS_ROLE_ARN`
- `TPP_ECR_REPOSITORY`
- `TPP_ECS_CLUSTER`
- `TPP_ECS_SERVICE`
- `TPP_TASK_DEFINITION_FAMILY`
- `TPP_SUPABASE_URL`
- `TPP_SUPABASE_ANON_KEY`
- `TPP_PLATFORM_OWNER_EMAIL`

After TLS acceptance, also set:

- `TPP_CERTIFICATE_ARN` = the issued certificate ARN attached by the accepted TLS workflow

Optional secret-ID and resource-name overrides are documented in the workflow files. Defaults match the approved pilot resource names.

### Required environment secret for provisioning

`TPP_PILOT_ACCESS_JSON` contains the approved teacher and administrator list. It is materialized only in the runner's temporary directory, used inside one database transaction, and deleted in an `always()` cleanup step.

Example structure with fictitious addresses only:

```json
[
  {
    "email": "platform.owner@anniston.k12.al.us",
    "display_name": "Platform Owner",
    "roles": ["platform_admin", "teacher"],
    "is_active": true
  },
  {
    "email": "pilot.teacher@anniston.k12.al.us",
    "display_name": "Pilot Teacher",
    "roles": ["teacher"],
    "is_active": true
  },
  {
    "email": "school.admin@anniston.k12.al.us",
    "display_name": "School Administrator",
    "roles": ["school_admin"],
    "is_active": true
  }
]
```

The record matching `TPP_PLATFORM_OWNER_EMAIL` must contain both `platform_admin` and `teacher`. Provisioning fails rather than reducing that account to one role.

## Controlled workflow order

1. Merge the reviewed release pull request and record the exact resulting `main` SHA.
2. Select the exact migration target required by that release. For the August 14 professional-learning/application release, `20260815001500` intentionally leaves `20260815011000_scheduled_admin_digest_worker.sql` deferred.
3. Run **Apply TPP Pilot Database Migrations** from `main` with the exact `expected_main_sha`, exact `target_migration_head`, `dry_run_only=true`, and `apply_target_confirmed=false`; review the target-scoped pending list.
4. Approve a second migration run only when the preview is accepted. Use the same exact SHA/head, `dry_run_only=false`, and `apply_target_confirmed=true`. Its final dry run must report no migration pending **through that target**. Later intentionally deferred migrations may remain in the repository.
5. Run **Preflight TPP Pilot Release** with the approved academic-year dates.
6. Run **Provision TPP Pilot Access** with the same dates and protected access-list secret.
7. Run **Bootstrap TPP Pilot** only for an initial stack. It creates or resumes the isolated AWS foundation, builds or reuses an exact commit-plus-build-configuration image, deploys the first ECS service, verifies target health, and requests or reuses the ACM certificate.
8. Run **Verify TPP Pilot Deployment** with public-hostname verification disabled.
9. Add the ACM validation CNAME returned in the workflow summary to Cloudflare.
10. After ACM reports `ISSUED`, run **Enable TPP Pilot TLS** with that certificate ARN.
11. Set `TPP_CERTIFICATE_ARN` to the accepted issued certificate ARN.
12. Add the Cloudflare application record: CNAME `planner` to the exact ALB DNS name, initially **DNS only**.
13. Complete Supabase and Google redirect configuration.
14. Run deployment verification with public HTTPS enabled, then perform live Google SSO acceptance.
15. For subsequent application releases, run **Deploy TPP Pilot** from `main` with the exact `expected_main_sha`, exact `expected_migration_head`, `migration_head_applied_confirmed=true`, and the required Help review confirmation.

No workflow in this sequence changes Cloudflare or Route 53 directly.

## Google and Supabase configuration

- Enable Google in the dedicated Supabase project.
- Configure the Google OAuth client with the callback URL displayed by Supabase for that project.
- Set the Supabase Site URL to `https://planner.guidedscholar.ai` after TLS is attached.
- Add `https://planner.guidedscholar.ai` to the allowed redirect URLs.
- Add the application origin to the Google OAuth web-client configuration where required.
- Keep the school domain restriction and database allowlist in force.

Authentication is not authorization. A valid Google school account receives no application data unless its lowercase email is active in `private.pilot_access_allowlist`; the database then creates the governed profile and all approved concurrent roles.

## Cloudflare and ACM

The bootstrap workflow returns:

- the ACM certificate ARN;
- the ACM DNS-validation CNAME name and value;
- the ALB DNS name.

Keep the ACM validation CNAME in place. Add the application CNAME only after the certificate is issued and the HTTPS listener is attached. Use DNS-only mode during direct AWS acceptance.

## Route 53 migration rule

Do not migrate `planner.guidedscholar.ai` by itself. When Cloudflare is removed from the production path, move the complete `guidedscholar.ai` hosted zone, including the `planner.guidedscholar.ai` record, in one coordinated action. Validate every application, email, OAuth, certificate-validation, and verification record before changing registrar nameservers.
