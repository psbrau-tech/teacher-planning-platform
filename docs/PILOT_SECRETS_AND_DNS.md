# Teacher Planning Platform Pilot Secrets and DNS

This is the controlled setup checklist for `planner.guidedscholar.ai` with authoritative DNS in Amazon Route 53 and the isolated application stack deployed in the existing AWS account in `us-east-2`.

## Security boundary

- Teacher and curriculum professional data only.
- No student names, IDs, grades, IEP/504 information, identifiable student work, health/discipline information, or other student-specific data.
- Never place keys, connection strings, or staff access lists in source files, screenshots, issues, pull-request comments, workflow summaries, or chat messages.
- GitHub Actions authenticates to AWS through OIDC. Long-lived AWS access keys are prohibited.
- The running ECS container uses a read-only root filesystem with a dedicated writable `/tmp` volume.
- A district, school, or account being provisioned does not by itself authorize automatic email.

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

The approved SES From address is exactly `notifications@planner.guidedscholar.ai`. The approved monitored Reply-To address is exactly `peter@brauconsulting.com`. The Reply-To address is non-secret governed runtime configuration; delivery code rejects a different Reply-To value.

SES delivery uses AWS task-role permission for `ses:SendEmail` only after the sender is separately activated. `TPP_SES_FROM_EMAIL` and `TPP_SES_REGION` are non-secret runtime configuration. The Reply-To default does not activate sending because `TPP_SES_FROM_EMAIL` remains blank until controlled SES activation.

The approved automatic Friday workflow uses **separate scheduled one-shot ECS tasks**, not the interactive web task. Only those isolated worker tasks may receive `TPP_SUPABASE_SERVICE_ROLE_KEY`, together with `TPP_SUPABASE_URL`, after the scheduled notification database/AWS activation gates are approved.

The **Supabase service-role** credential is therefore restricted to the isolated scheduled workers and protected operations; it is prohibited from the interactive web task.

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

## Required protected secret for district/school provisioning

`TPP_PILOT_ACCESS_JSON` contains the approved district graph, school configuration, notification settings, and professional account assignments. It is materialized only in the runner's temporary directory, used inside one database transaction, and deleted in an `always()` cleanup step.

Do not paste the real value into source control, an issue, a PR, a workflow input, a chat, or a release summary.

The governed shape is:

```json
{
  "districts": [
    {
      "name": "Anniston City Schools"
    }
  ],
  "schools": [
    {
      "name": "Anniston High School",
      "district": "Anniston City Schools",
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
      "district": "Anniston City Schools",
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
      "district": "Anniston City Schools",
      "school": "Anniston High School",
      "roles": ["platform_admin", "teacher"],
      "is_active": true
    },
    {
      "email": "middle.admin@anniston.k12.al.us",
      "display_name": "Middle School Administrator",
      "district": "Anniston City Schools",
      "school": "Anniston Middle School",
      "roles": ["school_admin"],
      "is_active": true
    },
    {
      "email": "district.admin@anniston.k12.al.us",
      "display_name": "District Administrator",
      "district": "Anniston City Schools",
      "school": "Anniston High School",
      "roles": ["district_admin"],
      "is_active": true
    }
  ]
}
```

The example addresses are fictitious. Real professional addresses remain only in the protected secret.

### District and school authorization rules

- Every configured district has an explicit name.
- Every configured school names exactly one configured district.
- Every configured school requires a valid IANA timezone such as `America/Chicago`.
- Notification local times must be on a 15-minute boundary.
- New schools default teacher/admin notification flags to `false` if notification settings are omitted.
- Every professional email appears once and names one configured district/school pair.
- `school_admin` is scoped to the assigned school.
- `district_admin` scope is derived from the assigned school's `district_id`; the existing district-reporting authorization then permits reporting only on schools whose `district_id` matches that district.
- `platform_admin` remains intentionally platform-scoped through the established authorization model.
- Do not duplicate an email across schools to simulate broader access.
- Moving an existing professional account to another school or district is an explicit authorization change and must be reviewed before provisioning.
- The record for `TPP_PLATFORM_OWNER_EMAIL` must include both `platform_admin` and `teacher`.

The provisioning script temporarily remains backward-compatible with the legacy AHS-only array shape. That compatibility path assigns Anniston High School to Anniston City Schools, uses `America/Chicago`, and keeps automatic notification settings **disabled**, so an old secret cannot accidentally turn email on.

## Controlled workflow order

1. Merge the reviewed release PR and record the exact resulting `main` SHA.
2. Select the exact migration target required by the release and keep repository source state separate from live database evidence.
3. The notification preparation chain is now applied through the verified live head `20260815220500_harden_school_local_notification_windows.sql`:
   - `20260815013000_scheduled_friday_notifications.sql`
   - `20260815215500_multi_school_notification_controls.sql`
   - `20260815220500_harden_school_local_notification_windows.sql`
4. For future database changes, run **Apply TPP Pilot Database Migrations** from `main` with exact `expected_main_sha`, exact `target_migration_head`, `dry_run_only=true`, and `apply_target_confirmed=false`; review the target-scoped pending list.
5. Approve a mutating migration run only after the preview is accepted. Use the same exact SHA/head, `dry_run_only=false`, and `apply_target_confirmed=true`. The final dry run must show nothing pending **through that target**.
6. Run **Preflight TPP Pilot Release** with the approved academic-year dates when required. The read-only preflight validates the district-to-school graph, each account's district/school assignment, role set, timezone, and notification settings before mutation.
7. With the multi-school notification schema now live, update the protected `TPP_PILOT_ACCESS_JSON` only with approved district/school settings and professional accounts, then run **Provision TPP Pilot Access**. This is a human-controlled gate for real staff access, district/school reassignment, and first-time school notification enablement.
8. Run **Deploy TPP Pilot** for application changes using the exact accepted SHA and confirmed applied migration head.
9. Run **Verify TPP Pilot Deployment** and complete release-specific acceptance.
10. Prepare SES identity/sending activation separately; normal application deployment does not turn email on.
11. Verify or create the dedicated service-role secret under the governed `tpp/pilot/supabase-service-role-key-*` path. Record only its ARN, never its value.
12. Reconcile live IAM with accepted source.
13. Run **Enable TPP SES Notifications** only after sender identity, production sending status, privacy/Help, and runtime-boundary confirmations are true.
14. Run **Enable TPP Friday Notifications** only after the notification schema is confirmed live, SES is active, school-local settings are approved, the service-role secret is ready, and IAM/privacy/Help gates are true.
15. Accept the first live Friday execution on the recipient side and confirm no duplicates, no cross-school delivery, and no prohibited content.

No workflow in this sequence changes public DNS directly.

## SES identity and DNS

The approved SES identity is either:

- exact address identity `notifications@planner.guidedscholar.ai`, or
- approved domain identity `planner.guidedscholar.ai`.

Verification occurs in SES `us-east-2`. As of the 2026-08-16 reconciliation, the `planner.guidedscholar.ai` domain identity is verified, DKIM is successful and enabled, and all three SES DKIM CNAME records are present in the authoritative Route 53 hosted zone.

The SES production-access request has been submitted. Until AWS reports approval, do not represent SES as ready to send to ordinary intended professional recipients and do not run the SES activation workflow with `production_access_confirmed=true`.

The governed application delivery addresses are:

- From: `notifications@planner.guidedscholar.ai`
- Reply-To: `peter@brauconsulting.com`

TPP does not require an inbound mailbox or MX record for `notifications@planner.guidedscholar.ai` because replies are explicitly directed to the monitored Reply-To mailbox.

Before routine automated sending, define and verify operational handling for:

- bounces;
- complaints; and
- suppression-list events.

These are operational controls; they do not change the no-student-data content boundary.

## Google and Supabase configuration

- Enable Google in the dedicated Supabase project.
- Configure the Google OAuth client with the callback URL displayed by Supabase for that project.
- Set the Supabase Site URL to `https://planner.guidedscholar.ai` after TLS is attached.
- Add `https://planner.guidedscholar.ai` to allowed redirect URLs.
- Add the application origin to the Google OAuth web-client configuration where required.
- Keep the professional school-domain restriction and database allowlist in force.
