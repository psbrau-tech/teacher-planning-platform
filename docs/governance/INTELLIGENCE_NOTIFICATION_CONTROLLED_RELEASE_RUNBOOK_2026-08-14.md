# Reflection Intelligence, Friday Status, and Notifications — Controlled Release Runbook

**Original date:** 2026-08-14  
**Reconciled:** 2026-08-15  
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
- Adding a school or professional account does not automatically enable scheduled email for that school.

## Current release sequence

The accepted Reflection Intelligence / PLC / formative-assessment and Friday-status application release is live through migration `20260815011000_friday_submission_status.sql`. Email remains separately governed and inactive.

The source-controlled notification sequence is intentionally staged:

1. `20260815013000_scheduled_friday_notifications.sql`
   - deferred automatic-delivery ledger and service-role-only candidate foundation;
   - teacher Friday courtesy-reminder candidates;
   - school-admin aggregate Friday digest candidates;
   - at-most-once claims;
   - remains deferred until SES and scheduler activation are being prepared.
2. `20260815215500_multi_school_notification_controls.sql`
   - adds required school-local notification settings that default to disabled;
   - makes notification delivery uniqueness explicitly school-scoped;
   - replaces global candidate RPCs with explicit `school_id`-scoped claims;
   - adds the service-role-only school-local dispatch-window selector; and
   - preserves the existing one-email/one-explicit-school professional-account model.
3. `20260815220500_harden_school_local_notification_windows.sql`
   - limits configured local notification times to quarter-hour boundaries;
   - hardens the school-local Friday dispatch calculation; and
   - uses the IANA timezone stored on each school so daylight-saving changes are handled by the timezone database rather than hand-maintained UTC offsets.

Repository source state and live database state are separate evidence. Use the target-scoped database workflow to stage only migrations through the specifically approved target. The three notification migrations above must remain unapplied until the notification preparation gate is intentionally opened.

## Multi-school provisioning contract

The pilot provisioning path must treat school as an explicit tenant boundary rather than assuming Anniston High School.

The governed configuration identifies:

- school name;
- required IANA timezone, for example `America/Chicago`;
- teacher-reminder enablement and local send time;
- administrator-digest enablement and local send time;
- professional account email and display name;
- one explicit school assignment for each professional account; and
- the approved role or concurrent roles for that account.

New schools default to:

- teacher reminders **disabled**;
- administrator digests **disabled**;
- teacher reminder local time **2:00 PM**; and
- administrator digest local time **3:30 PM**.

The provisioning script validates IANA timezone identifiers and quarter-hour local send times before database mutation. A legacy Anniston High School access-list shape remains temporarily readable for backward compatibility, but that legacy path provisions notification settings disabled. Automatic email therefore cannot become active merely because the old access secret still exists.

Each professional email has one explicit school assignment. A `school_admin` is authorized only for that assigned school. Existing `district_admin` and `platform_admin` roles provide intentionally broader district/platform scope through the established authorization model; TPP does not simulate broader access by assigning one school administrator to multiple schools in a single session.

Moving a professional account to a different school is an explicit governed provisioning change. It is not an additional membership and must be reviewed as an authorization change.

## Phase A — Friday status dashboard release

The Friday status dashboard is already released through migration `20260815011000` and remains independent from email activation.

The accepted behavior is:

- Teacher Dashboard shows each active required class and whether this week's reflection/completed packet is submitted.
- Teacher Dashboard shows each active required class and whether the following week's lesson plan is submitted.
- A class with no expected instruction in a relevant week is shown as not required rather than falsely missing.
- Administrator reporting shows authorized teacher/class operational status only within governed reporting scope.
- No student data or reflection/lesson-plan body appears in the status API.
- Status uses immutable `weekly_plan_submissions`, so a newer draft cannot erase an already-submitted state.
- The normal administrator `Weekly admin email` action is not mounted in the product UI.
- SES remains fail-closed until the separate activation phases below.

## Phase B — SES identity and sending readiness

This requires human AWS/provider evidence.

The approved From address is exactly `notifications@planner.guidedscholar.ai` in `us-east-2`. Verify the exact email identity or approved `planner.guidedscholar.ai` domain identity in Amazon SES, including required DNS records. Do not invent verification or DKIM values.

Confirm SES account sending status supports the intended professional recipients. If production access is required, do not treat a request as approved until AWS reports approval.

Before SES activation:

- privacy/subprocessor and Help review must match the enabled email data flow;
- live deployment-role policies must match the accepted source-controlled policies;
- the approved From address and identity ARN must be recorded;
- the interactive web task must still exclude the Supabase service-role credential; and
- bounce/complaint/suppression handling and the monitored Reply-To behavior must be operationally defined before routine automated sending.

The **Enable TPP SES Notifications** workflow updates the governed SES configuration without sending a test email. The activation workflow itself sends **no test email**.

## Phase C — Scheduled Friday delivery preparation

Apply the notification migration chain through `20260815220500_harden_school_local_notification_windows.sql` only after automatic delivery is being prepared for activation. This intentionally includes the deferred `20260815013000` foundation first.

Create/update the dedicated Secrets Manager secret for the existing Supabase service-role credential under the governed `tpp/pilot/supabase-service-role-key-*` path. Record only the ARN. Never place the value in source, chat, workflow inputs, browser configuration, or ordinary logs.

The scheduled worker receives only `TPP_SUPABASE_URL` and `TPP_SUPABASE_SERVICE_ROLE_KEY` as database secrets. It does not receive the OpenAI key, Supabase anon key, or OAuth secrets.

The delivery ledger persists bounded identifiers/status only. It does not retain recipient email, class/course reminder lists, email body, reflection text, lesson-plan content, student data, generated insight, or SES MessageId.

After the notification-control migrations are applied, run governed provisioning with the approved multi-school configuration before enabling dispatchers. Confirm every configured school has the intended IANA timezone and notification flags. A school whose flags remain disabled must not produce candidates.

## Approved school-local delivery behavior

For the current Anniston pilot, the approved local delivery times remain:

- **Teacher courtesy reminder:** Friday at **2:00 PM local time**.
- **School-administrator aggregate digest:** Friday at **3:30 PM local time**.

`America/Chicago` is the initial timezone for Anniston High School and Anniston Middle School, but it is stored independently on each school rather than treated as a platform-wide constant. Future schools must carry their own validated IANA timezone.

The 90-minute courtesy window is intentional. Teachers with every required submission complete receive no reminder. Teachers with an outstanding item receive one combined email for their assigned school that names the exact professional class/course and whether the missing item is the current-week reflection/completed packet, the following-week lesson plan, or both.

The administrator email contains aggregate counts and the authenticated TPP link only. Teacher/class exceptions remain behind authenticated reporting.

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
- enabled schools have approved IANA timezone and local notification settings;
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
- governed school names/timezones and notification enabled/disabled state without copying staff rosters into release evidence;
- SES identity ARN and sending-status evidence if activated;
- exact scheduled task definitions and both Scheduler states if activated;
- service-role secret ARN only, never its value;
- live IAM-policy evidence;
- Help/privacy/subprocessor review evidence; and
- acceptance/rollback results.

Do not retain customer content, reflection text, lesson-plan text, student data, credentials, recipient email addresses, or message bodies when bounded identifiers/status are sufficient.

## Stop conditions requiring human intervention

Stop for human action/approval at:

- applying live database migrations;
- changing the governed multi-school access/notification secret for real professional accounts;
- moving an existing professional account to another school;
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
