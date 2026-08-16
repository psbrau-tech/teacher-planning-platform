# Reflection Intelligence, Friday Status, and Notifications — Controlled Release Runbook

**Original date:** 2026-08-14  
**Reconciled:** 2026-08-16  
**Status:** Controlled release runbook; no live mutation is authorized by this document alone  
**Scope:** Teacher Planning Platform (TPP) pilot, AWS `us-east-2`

## Locked boundaries

At every phase:

- TPP remains adult educator/administrator professional planning only.
- Student PII, student education records, student assessment results, identifiable student work, IEP/504, health/discipline information, and student-level analytics remain prohibited.
- The 12 required Weekly Reflection / PLC Discussion responses remain teacher-authored. AI may not suggest, generate, complete, or rewrite those responses.
- Reflection Intelligence operates only after teacher-authored reflection submission.
- School Reflection Intelligence remains anonymous/aggregate and subject to the governed distinct-source threshold.
- Formative-assessment analytics are planned instructional signals, not teacher-performance/compliance measures or student outcomes.
- Friday submission status is operational workflow state, not teacher evaluation, ranking, quality, effort, or professionalism scoring.
- The interactive web ECS task must not receive a Supabase service-role credential.
- Email must never contain student information, reflection text, lesson-plan content, generated instructional insight, or teacher-quality scores.
- A successful merge, CI run, migration file, or CloudFormation template does not prove a live feature is activated.
- Adding a district, school, or professional account does not automatically enable scheduled email for that school.

## Current release sequence

The accepted Reflection Intelligence / PLC / formative-assessment, Friday-status, and multi-school readiness release is live through migration `20260815220500_harden_school_local_notification_windows.sql`. SES application sending and the Friday dispatchers remain separately governed and inactive.

The notification database sequence was intentionally applied during the controlled notification-preparation gate:

1. `20260815013000_scheduled_friday_notifications.sql`
   - automatic-delivery ledger and service-role-only candidate foundation;
   - teacher Friday courtesy-reminder candidates;
   - school-admin aggregate Friday digest candidates; and
   - at-most-once claims.
2. `20260815215500_multi_school_notification_controls.sql`
   - required school-local notification settings that default to disabled;
   - notification delivery uniqueness explicitly school-scoped;
   - global candidate RPCs replaced with explicit `school_id`-scoped claims;
   - service-role-only school-local dispatch-window selector; and
   - the existing one-email/one-explicit-school professional-account model preserved.
3. `20260815220500_harden_school_local_notification_windows.sql`
   - configured local notification times limited to quarter-hour boundaries;
   - school-local Friday dispatch calculation hardened; and
   - each school's IANA timezone used so daylight-saving changes are handled by the timezone database rather than hand-maintained UTC offsets.

The controlled migration workflow verified the live database up to date through `20260815220500`. Applying this schema did **not** enable email: school notification flags remain fail-closed, SES sending is not yet activated in the TPP stack, and the EventBridge Scheduler dispatchers remain inactive.

Repository source state and live database state are separate evidence. Future migrations still require an exact target-scoped preview and explicit mutating approval.

## District and school provisioning contract

The pilot provisioning path must treat district and school as explicit authorization boundaries rather than assuming Anniston High School.

The governed configuration identifies:

- district name;
- school name and its one configured district;
- required IANA timezone, for example `America/Chicago`;
- teacher-reminder enablement and local send time;
- administrator-digest enablement and local send time;
- professional account email and display name;
- one explicit configured district/school pair for each professional account; and
- the approved role or concurrent roles for that account.

New schools default to:

- teacher reminders **disabled**;
- administrator digests **disabled**;
- teacher reminder local time **2:00 PM**; and
- administrator digest local time **3:30 PM**.

The provisioning and read-only preflight scripts validate district names, district-to-school relationships, IANA timezone identifiers, quarter-hour local send times, and account district/school pairs before database mutation. A legacy Anniston High School access-list shape remains temporarily readable for backward compatibility, but that legacy path assigns Anniston High School to Anniston City Schools and provisions notification settings disabled. Automatic email therefore cannot become active merely because the old access secret still exists.

Each professional email has one explicit school assignment. A `school_admin` is authorized only for that assigned school. A `district_admin` is assigned one school in the governed district; the existing database authorization resolves `profiles.school_id -> schools.district_id` through `private.current_district_id()` and permits reporting only on schools with that same `district_id`. `platform_admin` remains intentionally platform-scoped.

TPP does not simulate district access by duplicating a district administrator across every school. Moving a professional account to a different school or district is an explicit governed provisioning change and must be reviewed as an authorization change.

For the current pilot, the intended district graph includes:

- **Anniston City Schools**
  - Anniston High School
  - Anniston Middle School

## Phase A — Friday status dashboard release

The Friday status dashboard is already released and remains independent from email activation.

The accepted behavior is:

- Teacher Dashboard shows each active required class and whether this week's reflection/completed packet is submitted.
- Teacher Dashboard shows each active required class and whether the following week's lesson plan is submitted.
- A class with no expected instruction in a relevant week is shown as not required rather than falsely missing.
- Administrator reporting shows authorized teacher/class operational status only within governed reporting scope.
- School administrators remain school-scoped; district administrators may report only across schools sharing their governed district; platform administrators retain only their separately approved platform scope.
- No student data or reflection/lesson-plan body appears in the status API.
- Status uses immutable `weekly_plan_submissions`, so a newer draft cannot erase an already-submitted state.
- The normal administrator `Weekly admin email` action is not mounted in the product UI.
- SES remains fail-closed until the separate activation phases below.

## Phase B — SES identity and sending readiness

This phase requires human AWS/provider evidence.

The approved From address is exactly `notifications@planner.guidedscholar.ai` in `us-east-2`. The approved monitored Reply-To address is exactly `peter@brauconsulting.com`. Application delivery must reject a different From or Reply-To address.

As of the 2026-08-16 reconciliation:

- the SES domain identity `planner.guidedscholar.ai` is verified in `us-east-2`;
- Easy DKIM is successful and enabled;
- the three SES DKIM CNAME records are present in the authoritative Route 53 zone; and
- SES production-access approval has been requested but must remain treated as **pending** until AWS reports approval.

Before SES activation:

- confirm AWS has granted production sending access for the intended professional recipients;
- privacy/subprocessor and Help review must match the enabled email data flow;
- live deployment-role policies must match the accepted source-controlled policies;
- the approved From address and SES identity ARN must be recorded;
- the interactive web task must still exclude the Supabase service-role credential; and
- bounce/complaint/suppression handling must be operationally defined before routine automated sending.

The monitored reply path is now explicit: replies generated by a recipient's mail client are directed to `peter@brauconsulting.com`; TPP does not require inbound mail service on `planner.guidedscholar.ai` for this purpose.

The **Enable TPP SES Notifications** workflow updates the governed SES configuration without sending a test email. The activation workflow itself sends **no test email**.

## Phase C — Scheduled Friday delivery preparation

The notification migration chain through `20260815220500_harden_school_local_notification_windows.sql` is already applied and verified. Do not re-run it merely as part of SES activation.

Create/update the dedicated Secrets Manager secret for the existing Supabase service-role credential under the governed `tpp/pilot/supabase-service-role-key-*` path. Record only the ARN. Never place the value in source, chat, workflow inputs, browser configuration, or ordinary logs.

The scheduled worker receives only `TPP_SUPABASE_URL` and `TPP_SUPABASE_SERVICE_ROLE_KEY` as database secrets. It does not receive the OpenAI key, Supabase anon key, or OAuth secrets.

The delivery ledger persists bounded identifiers/status only. It does not retain recipient email, class/course reminder lists, email body, reflection text, lesson-plan content, student data, generated insight, or SES MessageId.

Run governed provisioning with the approved district/school configuration before enabling dispatchers. Confirm every configured school has the intended district, IANA timezone, and notification flags. A school whose flags remain disabled must not produce candidates.

## Approved school-local delivery behavior

For the current Anniston pilot, the approved local delivery times remain:

- **Teacher courtesy reminder:** Friday at **2:00 PM local time**.
- **School-administrator aggregate digest:** Friday at **3:30 PM local time**.

`America/Chicago` is the initial timezone for Anniston High School and Anniston Middle School, but it is stored independently on each school rather than treated as a platform-wide constant. Future schools must carry their own validated IANA timezone and explicit district assignment.

The 90-minute courtesy window is intentional. Teachers with every required submission complete receive no reminder. Teachers with an outstanding item receive one combined email for their assigned school that names the exact professional class/course and whether the missing item is the current-week reflection/completed packet, the following-week lesson plan, or both.

The administrator email contains aggregate counts and the authenticated TPP link only. Teacher/class exceptions remain behind authenticated reporting. The current email-recipient policy remains `school_admin`; `district_admin` and `platform_admin` do not silently become email recipients merely because they have broader reporting rights.

Instruction-requirement logic suppresses false missing states when an assignment has no expected meeting in the relevant week based on effective assignment dates, meeting pattern, explicit non-instructional calendar days, and schedule exceptions.

## Dispatcher architecture

AWS EventBridge Scheduler does not encode one fixed school timezone. Instead, the two existing tightly scoped schedules act as dispatchers:

- teacher dispatcher: `tpp-pilot-teacher-friday-reminder`;
- administrator dispatcher: `tpp-pilot-admin-weekly-digest`;
- dispatcher expression: `cron(0/15 * ? * * *)`;
- dispatcher timezone: `UTC`.

Every quarter hour, the isolated worker asks the database which enabled schools are currently inside their configured local Friday delivery window. The database converts the dispatcher timestamp using each school's IANA timezone. The worker then calls the candidate RPC with that exact `school_id` and that school's local Monday `week_start`.

This design provides:

- daylight-saving-safe school-local delivery;
- no new EventBridge/IAM role set for every added school;
- school-by-school notification enablement;
- explicit school-scoped candidate claims;
- school-scoped at-most-once delivery keys; and
- fail-closed behavior for newly provisioned schools.

The quarter-hour dispatcher does not mean an email is sent every 15 minutes. Outside a configured school-local delivery window, the selector returns no school and the worker sends nothing.

## Phase D — activate isolated dispatchers

Run **Enable TPP Friday Notifications** only after every workflow confirmation is true:

- scheduled-delivery and multi-school notification-control migrations applied;
- approved SES notifications active;
- enabled schools have approved district, IANA timezone, and local notification settings;
- privacy/subprocessor and Help review complete;
- live governed deployment-role policies updated; and
- dedicated Supabase service-role secret exists at the governed path.

The workflow must:

1. verify the main pilot stack and SES state;
2. resolve the current immutable application image;
3. verify the interactive web task still lacks the service-role credential;
4. deploy the isolated worker stack with both quarter-hour dispatchers `DISABLED`;
5. verify the teacher task command is exactly `python -m app.scheduled_digest_worker teacher`;
6. verify the admin task command is exactly `python -m app.scheduled_digest_worker admin`;
7. verify both isolated tasks receive only the two approved Supabase secrets;
8. verify both exact schedule names, `cron(0/15 * ? * * *)`, and dispatcher timezone `UTC` while disabled; and
9. change both dispatchers to `ENABLED` only after those checks pass.

The activation workflow does not call `ecs run-task`, does not invoke the worker immediately, and sends no immediate/test email.

## First scheduled execution acceptance

At the first approved Friday windows for an enabled school:

- verify the teacher worker dispatches at the school's configured 2:00 PM local window;
- verify only teachers with outstanding required submissions are claimed for that school;
- verify a multi-class teacher receives one email for that school, with the exact missing class(es) and item(s);
- verify a fully complete teacher receives no reminder;
- verify the administrator worker dispatches at the school's configured 3:30 PM local window and sends the aggregate current-closeout/following-plan summary only to eligible active `school_admin` recipients assigned to that school;
- verify a district administrator can report only across schools whose `district_id` matches the district derived from that administrator's assigned school;
- verify a `district_admin` or `platform_admin` does not silently become a school-admin email recipient without an explicitly approved notification-recipient policy change;
- verify a newly provisioned school with notification flags disabled receives no automatic email;
- verify at-most-once claims prevent duplicate automatic sends on retries;
- verify worker logs do not print recipient addresses, teacher names, course names, message bodies, school identifiers, credentials, or SES MessageIds;
- verify no teacher names or class-level exception list appears in the administrator email; and
- verify no student data appears anywhere in the workflow.

Manual delivery/recovery, if retained, is controlled operational support and not a normal administrator-facing UI action.

## Evidence to retain

Keep bounded release evidence:

- exact accepted `main` SHA;
- exact immutable image digest and ECS task definition;
- CI/source-verification run IDs;
- live migration head;
- governed district names, school names/timezones, and notification enabled/disabled state without copying staff rosters into release evidence;
- SES identity ARN and sending-status evidence if activated;
- exact scheduled task definitions and both Scheduler states if activated;
- service-role secret ARN only, never its value;
- live IAM-policy evidence;
- Help/privacy/subprocessor review evidence; and
- acceptance/rollback results.

Do not retain customer content, reflection text, lesson-plan text, student data, credentials, recipient email addresses, or message bodies when bounded identifiers/status are sufficient. The approved From and Reply-To control addresses may be retained as configuration evidence because they are infrastructure controls rather than customer recipient data.

## Stop conditions requiring human intervention

Stop for human action/approval at:

- applying live database migrations;
- changing the governed district/school access and notification secret for real professional accounts;
- creating a new district or school with real professional users;
- moving an existing professional account to another school or district;
- enabling notifications for a school for the first time;
- deploying an application image when the controlled release gate requires manual workflow dispatch;
- SES identity/DNS verification;
- SES production-access approval if required;
- live AWS IAM policy updates when no governed automated path is already authorized;
- creation/update of the service-role secret;
- running the SES activation workflow;
- running the Friday notification activation workflow;
- first live/pilot email delivery acceptance if a manual recipient-side check is required;
- publishing/making legal policies effective; or
- any data-boundary, reporting-audience, retention, or personnel/evaluation expansion.

## Rollback

If the Friday status application is defective, use the exact-image/database release evidence and governed rollback process.

If email configuration is unsafe, stop/disable SES sending configuration before further acceptance.

If automatic delivery is unsafe, disable both EventBridge Scheduler dispatchers first so no new tasks launch, then remediate the worker/database path. UI hiding is never a scheduler kill switch.

If one school's notification configuration is unsafe while the dispatcher infrastructure itself remains sound, disable that school's teacher/admin notification flags through governed provisioning; do not disable unrelated schools unless necessary.
