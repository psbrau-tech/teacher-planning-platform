# TPP Controlled Pilot Deployment

## Locked pilot decisions

- Hostname: `planner.guidedscholar.ai`
- AWS account: existing Brau Consulting / Guided Scholar AWS account
- AWS region: `us-east-2`
- Isolation: separate TPP pilot VPC, ALB, ECR repository, ECS cluster/service, task roles, and log group
- Supabase: dedicated Teacher Planning Platform project
- Authentication: Google SSO through Supabase Auth using approved `anniston.k12.al.us` accounts
- OpenAI: separate TPP project and key
- Data boundary: teacher and curriculum data only; no student data
- Platform Owner: one governed account must hold concurrent `platform_admin` and `teacher` roles
- DNS: Cloudflare remains authoritative for the pilot; a later Route 53 migration moves the complete `guidedscholar.ai` zone, including `planner.guidedscholar.ai`, as one coordinated action

## Repository release controls

### Mutating workflows

- `.github/workflows/apply-pilot-database.yml` — target-scoped Supabase migration preview/application with exact `main` SHA, exact migration head, pinned CLI version, explicit apply confirmation, later-migration deferral, and post-apply target dry-run verification
- `.github/workflows/provision-pilot-access.yml` — transaction-safe school, academic-year, and staff-access provisioning
- `.github/workflows/bootstrap-pilot.yml` — isolated AWS foundation, first exact-image deployment, health verification, and ACM request; safe to retry only for the same accepted commit
- `.github/workflows/enable-pilot-tls.yml` — issued-certificate attachment with listener, redirect, target-health, and image-preservation verification
- `.github/workflows/deploy-pilot.yml` — subsequent exact-digest ECS deployments requiring the exact accepted `main` SHA, the confirmed applied migration head, Help review, prior-task-definition rollback evidence, and no-op verification when the exact image is already active
- `.github/workflows/enable-ses-notifications.yml` — separate manual activation of the approved SES sender after identity/sending/privacy gates; does not send a test email
- `.github/workflows/enable-scheduled-admin-digest.yml` — **Enable TPP Friday Notifications**; separate isolated activation of the approved Friday 2:00 PM teacher courtesy reminder and 3:30 PM administrator digest after database, SES, IAM, privacy/Help, service-role-secret, and exact-schedule gates; not part of a normal application deployment

### Read-only workflows

- `.github/workflows/preflight-pilot.yml` — validates protected GitHub configuration, staff-access JSON, academic-year dates, AWS OIDC, required secret metadata, CloudFormation, and migration inventory before mutation
- `.github/workflows/verify-pilot-deployment.yml` — verifies stack stability, ECS counts, immutable image provenance, target health, log retention, secret mappings, certificate metadata, and optional public HTTPS without changing AWS

### Application and infrastructure

- `Dockerfile` — combined React/FastAPI production image with non-root runtime and application health check
- `infra/pilot-stack.yml` — isolated TPP pilot CloudFormation stack, including fail-closed SES parameters
- `infra/scheduled-admin-digest-stack.yml` — separate optional Friday notification-worker stack containing isolated teacher-reminder and administrator-digest tasks/schedules; it is not created by normal application deployment
- `backend/scripts/preflight_pilot.py` — local and workflow validation of staff access and academic-year inputs without connecting to Supabase
- `scripts/build_or_reuse_pilot_image.sh` — shared immutable-ECR helper that reuses a commit-tagged digest after a partial workflow failure rather than attempting to overwrite an immutable tag
- `scripts/verify_exact_release_candidate.sh` — requires a release workflow to run from `main`, at the exact accepted SHA, against an exact repository migration version
- `scripts/stage_migrations_through.sh` — makes only migrations through the approved target visible to the Supabase CLI in the ephemeral Actions checkout, leaving later source migrations intentionally deferred

### Operational documentation

- `docs/PILOT_PREFLIGHT.md` — preflight use, target-scoped migration rules, retry boundaries, and failure-specific remediation
- `docs/PILOT_BROWSER_ACCEPTANCE.md` — owner, administrator, volunteer-teacher, negative-authorization, export, and Friday-validation evidence package
- `docs/VOLUNTEER_TEACHER_PILOT_GUIDE.md` — controlled teacher exercise and feedback guide
- `docs/PILOT_ROLLBACK.md` — detailed layered recovery runbook
- `docs/RELEASE_ROLLBACK_CHECKLIST.md` — concise release and rollback checklist
- `docs/governance/INTELLIGENCE_NOTIFICATION_CONTROLLED_RELEASE_RUNBOOK_2026-08-14.md` — phased release/activation boundary for Reflection Intelligence, assessment analytics, PLC artifacts, Friday status, and notifications
- `docs/governance/FRIDAY_STATUS_NOTIFICATION_DECISION_2026-08-15.md` — approved teacher/admin Friday status and notification product contract
- `docs/ROUTE53_MIGRATION_PREP.md` — coordinated migration preparation while Cloudflare remains authoritative
- `docs/DNS_RECORD_INVENTORY_TEMPLATE.md` — human-readable DNS inventory worksheet
- `docs/ROUTE53_RECORD_INVENTORY.csv` — row-level Cloudflare-to-Route 53 comparison template

All mutating workflows use the protected `tpp-pilot` GitHub environment. The read-only workflows use the same environment so they validate the actual protected values. A code push or pull request does not mutate the application, database, AWS resources, DNS, certificate, or identity-provider configuration.

## Controlled release sequence

For an already-running pilot application release:

1. Review CI, the pull-request diff, applicable Help/legal/governance documents, and any required acceptance artifacts.
2. Approve and merge every intended release pull request.
3. Record the exact resulting `main` SHA and choose the exact migration target required for that release.
4. Run **Apply TPP Pilot Database Migrations** from `main` with that `expected_main_sha`, that `target_migration_head`, `dry_run_only=true`, and `apply_target_confirmed=false`.
5. Review the exact target-scoped pending list. Later repository migrations may remain deliberately deferred when the release runbook permits it.
6. If approved, rerun the migration workflow with the same SHA/head, `dry_run_only=false`, and `apply_target_confirmed=true`. The final dry run must show nothing pending **through the approved target**.
7. Run **Preflight TPP Pilot Release** if protected configuration changed or a fresh preflight is required for the release record.
8. Run **Deploy TPP Pilot** from `main` with the exact accepted SHA, the exact migration head confirmed applied, `migration_head_applied_confirmed=true`, and the required Help review confirmation.
9. Verify ECS stability, target health, exact immutable image provenance, and the interactive runtime secret boundary.
10. Run **Verify TPP Pilot Deployment** for the exact accepted commit and perform the release-specific browser/API acceptance.
11. Retain the exact image digest, task-definition revision, workflow runs, migration evidence, and acceptance evidence.

The accepted professional-learning/application release is live through `20260815001500`. The next Friday-status dashboard/application release uses `20260815011000_friday_submission_status.sql` as its intended migration target. That target adds authenticated professional submission-status sources but does not enable email delivery. `20260815013000_scheduled_friday_notifications.sql` is intentionally later and must remain deferred during the dashboard release. The automatic SES/service-role/Scheduler path is a separate activation sequence.

For a brand-new pilot stack, the original bootstrap/TLS/DNS/OAuth sequence still applies: provision governed access, run preflight, bootstrap the stack, verify the non-public deployment, complete ACM validation, enable TLS, set the accepted certificate ARN, add the application DNS record, complete Supabase/Google redirect configuration, and then run public verification/browser acceptance.

Do not bypass failed validation by weakening checks, broadening access, moving protected values into repository files, or selecting a later migration merely to make a workflow pass.

## Deterministic migration boundary

The migration workflow uses an exact Supabase CLI version rather than `latest`. Every run is bound to the exact accepted `main` SHA and one explicit target migration head. In the ephemeral runner checkout, repository migrations later than that target are moved out of the Supabase CLI migration directory before preview/application. This allows a governed later feature migration to remain source-controlled but intentionally deferred.

An apply run previews the target-scoped migration set, applies only reviewed pending files through the target in timestamp order, lists migration history, and performs a final target-scoped dry run. Applied migration files are immutable history; any correction must be a new forward migration.

Repository source state and live database state are separate evidence. The release record must retain the actual pilot migration history/head; a Git merge or successful CI run does not prove a migration is applied.

## Interactive runtime credential boundary

The current AI-enabled interactive application task uses exactly these secret mappings:

- `TPP_SUPABASE_URL`;
- `TPP_SUPABASE_ANON_KEY`; and
- `TPP_OPENAI_API_KEY`.

The interactive task must not contain `TPP_SUPABASE_SERVICE_ROLE_KEY`, the PostgreSQL database URL, or Google OAuth client credentials. SES delivery, when separately activated, uses least-privilege AWS task-role permission plus non-secret SES sender/region configuration. The optional Friday notification worker is isolated in separate one-shot ECS tasks and is the only runtime permitted to receive the Supabase service-role key after its additional activation gates are satisfied.

## Friday notification activation boundary

The Anniston Pilot schedule is approved in `America/Chicago`:

- teacher courtesy reminder: Friday at 2:00 PM, `cron(0 14 ? * FRI *)`;
- school-administrator aggregate digest: Friday at 3:30 PM, `cron(30 15 ? * FRI *)`.

Teachers receive no automatic reminder when all required submissions are complete. A teacher with outstanding work receives one combined reminder naming the exact professional class(es) and whether each is missing the current-week reflection/completed packet, the following-week lesson plan, or both. The administrator email contains aggregate counts and a link only; teacher/class exceptions remain authenticated in TPP.

The normal administrator UI does not expose a routine `Weekly admin email` action. Any retained manual path is controlled operational recovery, not the primary workflow.

Before automatic delivery can be enabled, the scheduled-delivery migration `20260815013000_scheduled_friday_notifications.sql` must be explicitly applied, the approved SES sender must be active, the dedicated Supabase service-role secret must exist at the governed path, live deployment-role policies must match the accepted source, and Help/privacy/subprocessor review must be complete.

The activation workflow stages both schedules as `DISABLED`, verifies the immutable image, exact worker commands, exact two Supabase secrets, schedule expressions, timezone, and interactive service-role exclusion, and only then changes both schedules to `ENABLED`. It does not run either task immediately and sends no immediate/test email.

## Retry and recovery behavior

- **Preflight TPP Pilot Release** is read-only and can be rerun at any time.
- **Apply TPP Pilot Database Migrations** defaults to dry-run and refuses mutation unless the exact SHA/head are supplied and target application is explicitly confirmed.
- **Provision TPP Pilot Access** validates the complete access list before connecting and applies its changes in one database transaction.
- **Bootstrap TPP Pilot** can resume a new or partially completed stack for the same accepted commit. It will not remove an existing service and will refuse to replace an existing service with a different commit.
- After bootstrap, application changes must use **Deploy TPP Pilot**.
- Bootstrap and deploy reuse the immutable ECR digest already tagged with the same commit after a partial failure.
- Deploy avoids registering or activating a new task-definition revision when the same exact image is already active; it verifies the existing deployment instead.
- **Enable TPP Pilot TLS** preserves and verifies the active exact image and confirms the HTTPS listener, approved certificate, HTTP redirect, and target health.
- SES sender activation and Friday-worker activation remain separate from an application deployment and have their own fail-closed checks.
- Application rollback, database correction, staff-access correction, OAuth restoration, TLS correction, DNS rollback, and future Route 53 delegation rollback remain separate controlled actions.

## Operational acceptance before volunteer access or a material pilot release

- The read-only deployment verification passes for the exact accepted commit.
- Public HTTPS `/health` returns HTTP 200 without a certificate warning when public verification is in scope.
- ECS desired and running counts match, pending count is zero, and rollout is complete.
- The active task definition uses an immutable ECR digest associated with the accepted commit.
- All load-balancer targets are healthy.
- Application logs exist in the dedicated 30-day CloudWatch log group.
- No secret-bearing value appears in plaintext task-definition environment values.
- The exact permitted interactive runtime secrets are mapped through ECS secret references; prohibited privileged credentials are absent.
- Supabase migration history contains the exact migration target required by the release; any later intentionally deferred source migration is recorded as deferred rather than treated as missing accidentally.
- The approved access list is active and unapproved accounts receive no application data.
- Platform Owner retains both `platform_admin` and `teacher` in one session.
- School Administrator reporting is aggregate and school-scoped where the product contract calls for aggregates; authorized Friday operational follow-up may identify teachers/classes but remains within governed reporting scope and is not evaluation.
- Platform Administrator cost/adoption reporting is restricted to the governed Platform Administrator role.
- No student table, roster, student account, or student-specific field is used.

## Volunteer-teacher acceptance

The volunteer teacher must independently be able to:

1. authenticate with an approved Google school account;
2. see only the approved role set;
3. import or select a sequenced curriculum;
4. configure independent teaching assignments and meeting patterns;
5. generate a week using instructional minutes and calendar exceptions;
6. complete nonblank Literacy Standards and ACT Preparation fields;
7. save and reopen a weekly draft;
8. export each approved Anniston document and the combined packet;
9. validate lessons as completed, modified, missed, or skipped;
10. carry missed instruction forward without changing unrelated curricula;
11. recognize the teacher-and-curriculum-only boundary throughout the workflow.

For the Friday-status release, also verify that the Dashboard reports each required class independently, distinguishes current completed-packet/reflection submission from following-week lesson-plan submission, and does not treat a saved draft as submitted.

## Rollback

Use `docs/PILOT_ROLLBACK.md` to identify the failing layer before mutation. Application rollback, database correction, staff-access correction, OAuth restoration, TLS correction, application-record rollback, and future Route 53 delegation rollback are separate controlled actions.

A failed ECS deployment uses the configured deployment circuit breaker. A manual application rollback uses the recorded prior task definition and exact image. Application rollback does not reverse database migrations.

If automatic Friday notifications are unsafe, disable both EventBridge Scheduler schedules first so no new worker tasks launch, then remediate the worker/database/SES path.

## Human-controlled gates

The following require human action or explicit approval:

- pull-request merge when standing release authorization does not already cover it;
- selection/approval of the exact migration target for a mutating database run;
- protected-environment approval for database, provisioning, infrastructure, TLS, deployment, preflight, and verification workflows;
- staff access-list contents and academic-year dates;
- ACM/SES validation DNS record creation when required;
- setting accepted protected environment values such as a certificate ARN;
- Supabase and Google console changes;
- SES identity/sending activation and the first live/pilot email acceptance message;
- creation/update of the dedicated scheduled-worker service-role secret;
- live AWS IAM policy changes when no already-approved governed workflow performs them;
- execution of the Friday notification activation workflow;
- live browser acceptance with approved school accounts;
- any production rollback;
- the later coordinated Route 53 nameserver migration.

## Route 53 preparation boundary

The hosted zone and record inventory may be prepared while Cloudflare remains authoritative. Do not change registrar nameservers until:

- Guided Scholar and TPP are both stable and accepted;
- every Cloudflare record is inventoried and deliberately represented or retired;
- email, OAuth, Supabase, ACM, verification, and application records are validated;
- Cloudflare proxy-only behavior has an approved replacement;
- DNSSEC handling and rollback nameservers are documented;
- an explicit coordinated migration is authorized.

Do not migrate `planner.guidedscholar.ai` independently from the parent `guidedscholar.ai` zone.

## Rollout boundary

The first exercise is a controlled volunteer-teacher pilot. Full-school rollout is a separate decision contingent on pilot acceptance, defect closeout, administrator validation, monitoring review, and explicit authorization.
