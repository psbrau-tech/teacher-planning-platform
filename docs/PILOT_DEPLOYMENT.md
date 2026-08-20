# TPP Controlled Pilot Deployment

## Locked pilot decisions

- Hostname: `planner.guidedscholar.ai`
- AWS account: existing Brau Consulting / Guided Scholar AWS account
- AWS region: `us-east-2`
- Isolation: separate TPP pilot VPC, ALB, ECR repository, ECS cluster/service, task roles, and log group
- Supabase: dedicated Teacher Planning Platform project
- Authentication: Google SSO through Supabase Auth using approved `anniston.k12.al.us` professional accounts
- OpenAI: separate TPP project and key
- Data boundary: teacher and curriculum professional data only; no student data
- Platform Owner: one governed account must hold concurrent `platform_admin` and `teacher` roles
- Tenant model: explicit districts containing explicit schools, with one explicit district/school assignment per professional account
- Authorization model: `school_admin` is school-scoped; `district_admin` scope is derived from the assigned school's district; `platform_admin` remains intentionally platform-scoped
- Timezone model: every school stores a required IANA timezone; notification delivery uses school-local time and must not rely on a platform-wide UTC offset
- Notification default: newly provisioned schools have teacher reminders and administrator digests disabled until explicitly approved
- DNS: Cloudflare remains authoritative for the pilot; a later Route 53 migration moves the complete `guidedscholar.ai` zone, including `planner.guidedscholar.ai`, as one coordinated action

## Current accepted live baseline

The accepted interactive pilot baseline was established by live browser acceptance on
2026-08-20. Its exact application commit is
`b33bf905e98012b857c4434039fced08ff89137b`, and its applied database migration head is
`20260820020000_fix_ai_suggestion_decision_actor_ambiguity.sql`.

The accepted release includes class-duration display and start-time ordering, one pacing lesson
per class day, removal of pacing minute overrides, governed AI planning generation, explicit
teacher accept/edit/reject controls, and persistence of accepted AI planning text after reopening
the saved week. The live acceptance record is
`docs/governance/PILOT_BASELINE_2026-08-20.md`.

The source-controlled automatic-notification migrations are applied within this database baseline,
but migration state does not activate SES sending or either Friday dispatcher. Those operational
capabilities remain controlled by their separate activation workflows and governance gates.

Repository source state and live database state are separate evidence. A merge or successful CI run does not prove that a migration is live. A later intentionally deferred source migration is expected when the controlled release target stops earlier.

## Repository release controls

### Mutating workflows

- `.github/workflows/apply-pilot-database.yml` — target-scoped Supabase migration preview/application with exact `main` SHA, exact migration head, pinned CLI version, explicit apply confirmation, later-migration deferral, and post-apply target dry-run verification.
- `.github/workflows/provision-pilot-access.yml` — transaction-safe district, school, academic-year, school-timezone, notification-setting, and professional-access provisioning from a protected configuration secret.
- `.github/workflows/bootstrap-pilot.yml` — isolated AWS foundation, first exact-image deployment, health verification, and ACM request.
- `.github/workflows/enable-pilot-tls.yml` — issued-certificate attachment with listener, redirect, target-health, and image-preservation verification.
- `.github/workflows/deploy-pilot.yml` — subsequent exact-digest ECS deployments requiring exact accepted `main` SHA, confirmed migration head, Help review, rollback evidence, and immutable-image verification.
- `.github/workflows/enable-ses-notifications.yml` — separate manual activation of the approved SES sender after identity/sending/privacy gates; sends no test email.
- `.github/workflows/enable-scheduled-admin-digest.yml` — **Enable TPP Friday Notifications**; separate isolated activation of the two quarter-hour dispatcher schedules after database, SES, IAM, privacy/Help, school-local settings, and service-role-secret gates.

### Read-only workflows

- `.github/workflows/preflight-pilot.yml` — validates protected GitHub configuration, district/school graph, professional account assignments, academic-year dates, AWS OIDC, required secret metadata, CloudFormation, and migration inventory before mutation.
- `.github/workflows/verify-pilot-deployment.yml` — verifies stack stability, ECS counts, immutable image provenance, target health, log retention, secret mappings, certificate metadata, and optional public HTTPS without changing AWS.

### Application and infrastructure

- `Dockerfile` — combined React/FastAPI production image with non-root runtime and application health check.
- `infra/pilot-stack.yml` — isolated TPP pilot CloudFormation stack, including fail-closed SES parameters.
- `infra/scheduled-admin-digest-stack.yml` — separate optional professional-notification worker stack containing isolated teacher-reminder and administrator-digest tasks plus two exact EventBridge Scheduler resources. These are dispatcher schedules, not fixed school-time schedules.
- `backend/scripts/provision_pilot.py` — governed district/school configuration parser/provisioner with IANA timezone validation, explicit district-to-school assignment, one explicit district/school pair per professional account, school notification settings, and backward-compatible fail-closed handling of the legacy AHS access-list shape.
- `backend/scripts/preflight_pilot.py` — read-only validation of the same district/school graph, account assignment, role, timezone, and notification-setting structure before mutation.
- `scripts/verify_exact_release_candidate.sh` — requires a release workflow to run from `main`, at the exact accepted SHA, against an exact repository migration version.
- `scripts/stage_migrations_through.sh` — makes only migrations through the approved target visible to the Supabase CLI in the ephemeral Actions checkout, leaving later source migrations intentionally deferred.

## Controlled application release sequence

For an already-running pilot application release:

1. Review CI, the pull-request diff, applicable Help/legal/governance documents, and any required acceptance artifacts.
2. Approve and merge every intended release pull request.
3. Record the exact resulting `main` SHA and choose the exact migration target required for that release.
4. Run **Apply TPP Pilot Database Migrations** from `main` with that `expected_main_sha`, that `target_migration_head`, `dry_run_only=true`, and `apply_target_confirmed=false`.
5. Review the exact target-scoped pending list. Later repository migrations may remain deliberately deferred when the release runbook permits it.
6. If approved, rerun with the same SHA/head, `dry_run_only=false`, and `apply_target_confirmed=true`. The final dry run must show nothing pending **through the approved target**.
7. Run **Preflight TPP Pilot Release** if protected configuration changed or a fresh preflight is required for the release record. The preflight must validate each school against a configured district and each professional account against a configured district/school pair.
8. Run **Deploy TPP Pilot** from `main` with the exact accepted SHA, exact migration head confirmed applied, `migration_head_applied_confirmed=true`, and the required Help review confirmation.
9. Verify ECS stability, target health, exact immutable image provenance, and the interactive runtime secret boundary.
10. Run **Verify TPP Pilot Deployment** for the exact accepted commit and perform release-specific browser/API acceptance.
11. Retain the exact image digest, task-definition revision, workflow runs, migration evidence, and acceptance evidence.

Do not select a later migration merely because it exists in source. The approved target is a release decision.

## District and school provisioning boundary

TPP no longer treats Anniston High School as an implicit singleton tenant. The protected `TPP_PILOT_ACCESS_JSON` configuration defines the governed district/school graph and staff accounts.

Each configured district requires:

- an explicit district name.

Each configured school requires:

- an explicit school name;
- exactly one configured district;
- a valid IANA timezone such as `America/Chicago`;
- teacher-reminder enablement state and local send time; and
- administrator-digest enablement state and local send time.

Each professional account requires:

- professional school email;
- display name;
- one explicit configured district;
- one explicit school in that district;
- one or more approved roles; and
- active/inactive state.

The current session model intentionally remains one-school-per-account. A `school_admin` is authorized only for the account's assigned school. A `district_admin` is assigned one school within the governed district; the established database authorization resolves that school's `district_id` through `private.current_district_id()` and permits reporting only on schools whose `district_id` matches. `platform_admin` remains intentionally platform-scoped.

This makes the district boundary explicit without inventing a second active-school selector or duplicating a district administrator across every school in the district.

For the current pilot, the graph is intended to include:

- **Anniston City Schools**
  - Anniston High School
  - Anniston Middle School

Moving an existing account to another school or district is an explicit governed provisioning change because school/district context is authorization state. Duplicate email rows are rejected by the protected configuration parser.

New school records default automatic notification flags to disabled. Merely adding Anniston Middle School, its teachers, or its administrators must not cause email to start.

## Interactive runtime credential boundary

The current AI-enabled interactive application task uses exactly these secret mappings:

- `TPP_SUPABASE_URL`;
- `TPP_SUPABASE_ANON_KEY`; and
- `TPP_OPENAI_API_KEY`.

The interactive task must not contain `TPP_SUPABASE_SERVICE_ROLE_KEY`, the PostgreSQL database URL, or Google OAuth client credentials. SES delivery, when separately activated, uses least-privilege AWS task-role permission plus non-secret SES sender/region configuration.

The optional Friday notification worker is isolated in separate one-shot ECS tasks and is the only runtime permitted to receive the Supabase service-role key after its additional activation gates are satisfied. Those workers receive only `TPP_SUPABASE_URL` and `TPP_SUPABASE_SERVICE_ROLE_KEY` as database secrets; they do not receive the OpenAI key, Supabase anon key, database URL, or OAuth secrets.

## School-local Friday notification behavior

The approved default **local** delivery times are:

- teacher courtesy reminder: Friday at **2:00 PM local time**;
- school-administrator aggregate digest: Friday at **3:30 PM local time**.

Anniston High School and Anniston Middle School initially use `America/Chicago`, but that value is stored independently on each school. The architecture must continue to work when a future school uses another IANA timezone or belongs to another configured district.

The scheduler layer itself uses two exact quarter-hour dispatchers:

- `tpp-pilot-teacher-friday-reminder`
- `tpp-pilot-admin-weekly-digest`
- expression: `cron(0/15 * ? * * *)`
- dispatcher timezone: `UTC`

Every quarter hour, an isolated worker asks the database for enabled schools whose **local Friday clock** is inside that school's configured 15-minute send window. The database converts the current dispatcher timestamp through each school's IANA timezone, so daylight-saving-time changes follow the timezone database rather than a manually maintained offset.

The quarter-hour cadence is not a quarter-hour email cadence. If no enabled school is due, the worker sends nothing.

For every due school, the worker makes an explicit `school_id`-scoped claim. The delivery ledger's at-most-once key includes school ID, recipient profile ID, notification type, and week as defense in depth against cross-school claims.

Teachers with every required submission complete receive no reminder. Teachers with outstanding work receive one combined email for their assigned school, naming the exact professional class/course and whether each is missing the current-week reflection/completed packet, following-week lesson plan, or both.

The administrator email contains aggregate school-scoped operational counts and an authenticated TPP link only. It must not contain teacher names, teacher/class exception lists, reflection text, lesson-plan content, generated instructional insight, student information, or teacher-quality/performance content.

## Notification database activation boundary

The notification chain must be applied as a single reviewed forward sequence when email preparation is intentionally opened:

1. `20260815013000_scheduled_friday_notifications.sql` — bounded delivery ledger and initial isolated-worker claim foundation.
2. `20260815215500_multi_school_notification_controls.sql` — school notification settings, school-scoped at-most-once key, school-local window selector, and explicit school-scoped candidate claims.
3. `20260815220500_harden_school_local_notification_windows.sql` — quarter-hour local-time constraints and hardened IANA-timezone dispatch-window calculation.

Until that controlled target is approved and applied, the live migration head remains earlier and automatic delivery remains inactive.

After the migration chain is applied, run governed provisioning with the reviewed district/school configuration before enabling dispatchers. Confirm each school's district, timezone, and notification enabled/disabled state. A school with notification flags disabled must return no automatic-delivery candidates.

## SES activation boundary

The approved sender is exactly `notifications@planner.guidedscholar.ai` in `us-east-2`.

Before running **Enable TPP SES Notifications**:

- verify the exact address or `planner.guidedscholar.ai` domain identity in Amazon SES;
- complete required DNS records without inventing DKIM/verification values;
- confirm SES account sending status supports intended professional recipients;
- complete privacy/subprocessor and Help review for the enabled data flow;
- confirm deployment-role policies match accepted source; and
- verify the interactive web task still excludes the service-role credential.

The SES activation workflow configures the approved sender and least-privilege task permission. It sends no test email.

Before routine automated delivery, also define and verify bounce/complaint/suppression monitoring and the intended Reply-To/monitored mailbox behavior.

## Friday dispatcher activation boundary

Run **Enable TPP Friday Notifications** only after all of the following are true:

- the notification migration chain through `20260815220500` is applied;
- approved SES sender infrastructure is active;
- the dedicated `tpp/pilot/supabase-service-role-key-*` secret exists and only its ARN is supplied to the workflow;
- live deployment-role policies match source;
- Help/privacy/subprocessor review is current;
- every school intended to receive notifications has an approved district, IANA timezone, and local settings; and
- any newly added school not intended for email remains disabled.

The activation workflow:

1. validates the main pilot stack, SES state, immutable image, and interactive credential boundary;
2. stages the two exact dispatcher schedules as `DISABLED`;
3. verifies worker commands exactly:
   - `python -m app.scheduled_digest_worker teacher`
   - `python -m app.scheduled_digest_worker admin`;
4. verifies isolated tasks contain only the two approved Supabase secrets;
5. verifies the two exact schedule names, `cron(0/15 * ? * * *)`, and `UTC` dispatcher timezone while disabled;
6. changes both dispatchers to `ENABLED` only after those checks pass; and
7. sends no immediate/test email and does not invoke `ecs run-task`.

## First live Friday acceptance

At the first approved Friday window for each enabled school, verify:

- the teacher worker processes the school at its configured 2:00 PM local window;
- only teachers with outstanding required submissions are claimed for that school;
- a multi-class teacher receives one school-specific email with exact missing class(es)/item(s);
- a fully complete teacher receives no reminder;
- the admin worker processes the school at its configured 3:30 PM local window;
- eligible active `school_admin` recipients receive only their assigned school's aggregate digest;
- `district_admin` reporting spans only schools attached to the same district as the district administrator's assigned school;
- district/platform roles do not become school-admin email recipients unless the notification-recipient policy is explicitly expanded and reviewed;
- a newly provisioned school with notification flags disabled receives no automatic email;
- retries do not create duplicate sends because of at-most-once claims;
- worker logs do not print recipient email, names, course names, school identifiers, message bodies, credentials, or SES MessageIds; and
- no student data appears anywhere in the delivery path.

## Operational acceptance before a material pilot expansion

- The read-only deployment verification passes for the exact accepted commit.
- Public HTTPS `/health` returns HTTP 200 without a certificate warning when public verification is in scope.
- ECS desired and running counts match, pending count is zero, and rollout is complete.
- The active task definition uses an immutable ECR digest associated with the accepted commit.
- All load-balancer targets are healthy.
- Application logs exist in the dedicated 30-day CloudWatch log group.
- No secret-bearing value appears in plaintext task-definition environment values.
- The exact permitted interactive runtime secrets are mapped through ECS secret references; prohibited privileged credentials are absent.
- Supabase migration history contains the exact migration target required by the release; any later intentionally deferred source migration is recorded as deferred rather than treated as missing accidentally.
- The approved district/school access configuration is active and unapproved accounts receive no application data.
- Platform Owner retains both `platform_admin` and `teacher` in one session.
- School Administrator reporting remains school-scoped and within the non-evaluative professional reporting boundary.
- District Administrator reporting remains intentionally district-scoped through the governed school-to-district relationship.
- Platform Administrator cost/adoption reporting remains restricted to the governed Platform Administrator role.
- No student table, roster, student account, or student-specific field is used.

## Rollback

Use `docs/PILOT_ROLLBACK.md` to identify the failing layer before mutation. Application rollback, database forward correction, staff-access correction, OAuth restoration, TLS correction, SES correction, scheduler correction, and DNS rollback are separate controlled actions.

If automatic Friday notifications are unsafe, disable both EventBridge Scheduler dispatchers first so no new worker tasks launch, then remediate the worker/database/SES path.

If the dispatcher infrastructure is sound but one school's configuration is unsafe, disable that school's teacher/admin notification flags through governed provisioning. Do not disable unrelated schools unless the incident requires it.

## Human-controlled gates

The following require human action or explicit approval:

- selection/approval of the exact migration target for a mutating database run;
- protected-environment approval for database, provisioning, infrastructure, TLS, deployment, preflight, and verification workflows;
- real district/school graph, staff access-list contents, and academic-year dates;
- creation of a new district or school with real professional users;
- moving an existing professional account to another school or district;
- enabling automatic notifications for a school for the first time;
- ACM/SES validation DNS records when required;
- Supabase and Google console changes;
- SES identity/sending activation and first live/pilot email acceptance;
- creation/update of the dedicated scheduled-worker service-role secret;
- live AWS IAM policy changes when no already-approved governed workflow performs them;
- execution of the Friday notification activation workflow;
- live browser/recipient acceptance with approved school accounts;
- any production rollback; and
- the later coordinated Route 53 nameserver migration.

Do not bypass failed validation by weakening tests, broadening access, moving protected values into repository files, or selecting a later migration merely to make a workflow pass.
