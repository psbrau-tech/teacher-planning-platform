# Teacher Planning Platform Pilot Secrets and DNS

This is the controlled setup checklist for `planner.guidedscholar.ai` while authoritative DNS remains in Cloudflare and the isolated application stack is deployed in the existing AWS account in `us-east-2`.

## Security boundary

- Teacher and curriculum professional data only.
- No student names, IDs, grades, IEP/504 information, identifiable student work, health/discipline information, or other student-specific data.
- Never place keys, connection strings, or staff access lists in source files, screenshots, issues, pull-request comments, workflow summaries, or chat messages.
- GitHub Actions authenticates to AWS through OIDC. Long-lived AWS access keys are prohibited.
- The running ECS container uses a read-only root filesystem with a dedicated writable `/tmp` volume.
- A school or account being provisioned does not by itself authorize automatic email.

## AWS Secrets Manager

The controlled workflows use these exact secret IDs unless the corresponding protected GitHub environment variable overrides the name:

- `tpp/pilot/supabase-url`
- `tpp/pilot/supabase-anon-key`
- `tpp/pilot/supabase-service-role-key`
- `tpp/pilot/database-url`
- `tpp/pilot/openai-api-key`
- `tpp/pilot/google-oauth-client-id`
- `tpp/pilot/google-oauth-client-secret`

Each secret contains only its raw value.

### Credentials allowed in the interactive ECS web task

The current AI-enabled interactive runtime receives only:

- `TPP_SUPABASE_URL` from `tpp/pilot/supabase-url`;
- `TPP_SUPABASE_ANON_KEY` from `tpp/pilot/supabase-anon-key`; and
- `TPP_OPENAI_API_KEY` from `tpp/pilot/openai-api-key`.

The interactive web task must **not** receive:

- `TPP_SUPABASE_SERVICE_ROLE_KEY`;
- the PostgreSQL database URL;
- Google OAuth client ID or client secret.

Database migration and staff provisioning workflows retrieve the database connection only inside their protected operation. Google provider configuration occurs in Supabase and Google consoles. Deployment verification fails if a prohibited privileged credential appears in the interactive ECS task.

### Notification and scheduled-worker credential boundary

The approved SES sender is exactly `notifications@planner.guidedscholar.ai`. SES delivery uses AWS task-role permission for `ses:SendEmail` only after the sender is separately activated. `TPP_SES_FROM_EMAIL` and `TPP_SES_REGION` are non-secret runtime configuration.

The approved automatic Friday workflow uses **separate scheduled one-shot ECS tasks**, not the interactive web task. Only those isolated worker tasks may receive `TPP_SUPABASE_SERVICE_ROLE_KEY`, together with `TPP_SUPABASE_URL`, after the scheduled notification database/AWS activation gates are approved.

The scheduled workers must not receive the OpenAI key, Supabase anon key, PostgreSQL database URL, or Google OAuth secrets.

The exact worker commands remain:

- teacher: `python -m app.scheduled_digest_worker teacher`
- administrator: `python -m app.scheduled_digest_worker admin`

The two exact EventBridge Scheduler resources are **quarter-hour UTC dispatchers**, both using `cron(0/15 * ? * * *)`. They do not encode one school's timezone or one fixed send time. The database decides whether any enabled school is currently due using that school's stored IANA timezone and local notification settings. New schools default to notifications disabled.

The activation workflow stages both dispatcher schedules disabled, verifies them, and then enables them only after all manual gates are true. It does not run either task immediately and sends no immediate/test email.

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

Optional secret-ID and resource-name overrides are documented in workflow files. Defaults match the approved pilot resource names.

## Required protected secret for multi-school provisioning

`TPP_PILOT_ACCESS_JSON` contains the approved school configuration and professional access memberships. It is materialized only in the runner's temporary directory, used inside one database transaction, and deleted in an `always()` cleanup step.

Do not paste the real value into source control, an issue, a PR, a workflow input, a chat, or a release summary.

The new governed shape is:

```json
{
  "schools": [
    {
      "name": "Anniston High School",
      "timezone": "America/Chicago",
      "notifications": {
        "teacher_reminders_enabled": false,
        "teacher_reminder_local_time": "14:00",
        "admin_digest_enabled": false,
        "admin_digest_local_time": "15:30"
      }
    },
    {
      "name": "Anniston Middle School",
      "timezone": "America/Chicago",
      "notifications": {
        "teacher_reminders_enabled": false,
        "teacher_reminder_local_time": "14:00",
        "admin_digest_enabled": false,
        "admin_digest_local_time": "15:30"
      }
    }
  ],
  "access": [
    {
      "email": "platform.owner@anniston.k12.al.us",
      "display_name": "Platform Owner",
      "school": "Anniston High School",
      "roles": ["platform_admin", "teacher"],
      "is_home": true,
      "is_active": true
    },
    {
      "email": "middle.admin@anniston.k12.al.us",
      "display_name": "Middle School Administrator",
      "school": "Anniston Middle School",
      "roles": ["school_admin"],
      "is_home": true,
      "is_active": true
    }
  ]
}
```

The example addresses are fictitious. Real professional addresses remain only in the protected secret.

### Multi-school membership rules

- Every configured school requires a valid IANA timezone such as `America/Chicago`.
- Notification local times must be on a 15-minute boundary.
- New schools default teacher/admin notification flags to `false` if notification settings are omitted.
- Every active professional account has exactly one `is_home: true` school membership.
- The same professional email may have additional school memberships with `is_home: false` when explicitly authorized.
- School roles are materialized to `profile_roles` for the exact school membership.
- The home school populates the existing `profiles.school_id` context; it does not grant authorization to other schools.
- The record set for `TPP_PLATFORM_OWNER_EMAIL` must collectively include both `platform_admin` and `teacher`.

The provisioning script temporarily remains backward-compatible with the legacy AHS-only array shape. That compatibility path assigns Anniston High School / `America/Chicago` and keeps automatic notification settings **disabled**, so an old secret cannot accidentally turn email on.

## Controlled workflow order

1. Merge the reviewed release PR and record the exact resulting `main` SHA.
2. Select the exact migration target required by the release. The professional-learning/application baseline includes `20260815001500`; the current accepted Friday-status live head is `20260815011000_friday_submission_status.sql`.
3. Automatic notification migrations remain deliberately **deferred** until email preparation is intentionally opened:
   - `20260815013000_scheduled_friday_notifications.sql`
   - `20260815215500_multi_school_notification_controls.sql`
   - `20260815220500_harden_school_local_notification_windows.sql`
4. Run **Apply TPP Pilot Database Migrations** from `main` with exact `expected_main_sha`, exact `target_migration_head`, `dry_run_only=true`, and `apply_target_confirmed=false`; review the target-scoped pending list.
5. Approve a mutating migration run only after the preview is accepted. Use the same exact SHA/head, `dry_run_only=false`, and `apply_target_confirmed=true`. The final dry run must show nothing pending **through that target**.
6. Run **Preflight TPP Pilot Release** with the approved academic-year dates when required.
7. After the multi-school notification schema exists, update the protected `TPP_PILOT_ACCESS_JSON` only with the approved school settings/memberships and run **Provision TPP Pilot Access**. This is a human-controlled gate for real staff access and first-time school notification enablement.
8. Run **Deploy TPP Pilot** for application changes using the exact accepted SHA and confirmed applied migration head.
9. Run **Verify TPP Pilot Deployment** and complete release-specific acceptance.
10. Prepare SES identity/sending activation separately; normal application deployment does not turn email on.
11. Verify or create the dedicated service-role secret under the governed `tpp/pilot/supabase-service-role-key-*` path. Record only its ARN, never its value.
12. Reconcile live IAM with accepted source.
13. Run **Enable TPP SES Notifications** only after sender identity, production sending status, privacy/Help, and runtime-boundary confirmations are true.
14. Run **Enable TPP Friday Notifications** only after the full notification migration chain is applied, SES is active, school-local settings are approved, the service-role secret is ready, and IAM/privacy/Help gates are true.
15. Accept the first live Friday execution on the recipient side and confirm no duplicates, no cross-school delivery, and no prohibited content.

No workflow in this sequence changes Cloudflare or Route 53 directly.

## SES identity and DNS

The approved identity is either:

- exact address identity `notifications@planner.guidedscholar.ai`, or
- approved domain identity `planner.guidedscholar.ai`.

Verification must occur in SES `us-east-2`. Add only the DNS records actually returned by AWS. Do not invent DKIM, verification, MAIL FROM, SPF, or DMARC values.

Confirm SES sending status supports the intended professional recipients. If the account is still restricted by the SES sandbox or another provider limitation, do not represent email as production-ready.

Before routine automated sending, define operational handling for:

- bounces;
- complaints;
- suppression-list events; and
- Reply-To behavior / a monitored mailbox if users reply to notifications.

These are operational controls; they do not change the no-student-data content boundary.

## Google and Supabase configuration

- Enable Google in the dedicated Supabase project.
- Configure the Google OAuth client with the callback URL displayed by Supabase for that project.
- Set the Supabase Site URL to `https://planner.guidedscholar.ai` after TLS is attached.
- Add `https://planner.guidedscholar.ai` to allowed redirect URLs.
- Add the application origin to the Google OAuth web-client configuration where required.
- Keep the professional school-domain restriction and database allowlist in force.

Authentication is not authorization. A valid Google school account receives no application data unless its lowercase email has an active governed school membership in `private.pilot_access_allowlist`; the database then creates/synchronizes the profile and approved school-scoped roles.

## Cloudflare and ACM

The bootstrap workflow returns the ACM certificate ARN, validation CNAME, and ALB DNS name. Keep the ACM validation CNAME in place. Add the application CNAME only after the certificate is issued and the HTTPS listener is attached. Use DNS-only mode during direct AWS acceptance.

SES DNS records are separate from ACM/TLS records. Preserve each verified identity/validation record for as long as the associated AWS identity/certificate requires it.

## Route 53 migration rule

Do not migrate `planner.guidedscholar.ai` by itself. If Cloudflare is later removed from the production path, move the complete `guidedscholar.ai` hosted zone in one coordinated action. Validate every application, email, OAuth, certificate-validation, SES, and verification record before changing registrar nameservers.
