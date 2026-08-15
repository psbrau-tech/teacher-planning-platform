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

## Current release sequence

The previously accepted Reflection Intelligence / PLC / formative-assessment application release is live through migration `20260815001500`. Email remains separately governed.

The next source-controlled sequence is intentionally split:

1. `20260815011000_friday_submission_status.sql`
   - teacher class-by-class Friday status;
   - authorized administration teacher/class status;
   - immutable submitted records only;
   - current-week completed packet + following-week lesson plan;
   - instruction requirement is assignment/schedule/calendar/exception aware;
   - does **not** create the scheduled delivery ledger and does not require the service-role worker.
2. `20260815013000_scheduled_friday_notifications.sql`
   - deferred automatic-delivery ledger and service-role-only candidate RPCs;
   - teacher Friday courtesy-reminder candidates;
   - school-admin aggregate Friday digest candidates;
   - at-most-once claims;
   - remains deferred until SES and scheduler activation are approved.

Repository source state and live database state are separate evidence. Use the target-scoped database workflow to stage only migrations through the specifically approved target. A later intentionally deferred source migration must not be applied merely because it exists in the repository.

## Phase A — Friday status dashboard release

Before database mutation:

1. Merge intended source PRs to `main`.
2. Record the exact `main` commit SHA.
3. Confirm exact-head CI and governed-source verification are green.
4. Record the currently deployed immutable image digest, ECS task definition, and live Supabase migration head.
5. Confirm the existing pilot is healthy.
6. Confirm Help/governance describes Friday status as professional operational reporting.

Apply only the approved dashboard migration head using the governed workflow. For the first Friday-status release, the intended target is `20260815011000`; `20260815013000_scheduled_friday_notifications.sql` must remain deferred.

After migration application, verify local/remote history matches through the approved target and the final dry run has no pending migration through that staged target.

Deploy the exact accepted application image only after the database target is confirmed applied. Verify immutable image provenance, ECS health, TLS/public health, and that the interactive task still contains only the approved runtime secret set and no Supabase service-role key.

### Friday status browser acceptance

Using permitted adult professional pilot content:

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
- the interactive web task must still exclude the Supabase service-role credential.

The **Enable TPP SES Notifications** workflow updates the governed SES configuration without sending a test email. The activation workflow itself sends **no test email**.

## Phase C — Scheduled Friday delivery preparation

Apply `20260815013000_scheduled_friday_notifications.sql` only after automatic delivery is being prepared for activation.

Create/update the dedicated Secrets Manager secret for the existing Supabase service-role credential under the governed `tpp/pilot/supabase-service-role-key-*` path. Record only the ARN. Never place the value in source, chat, workflow inputs, browser configuration, or ordinary logs.

The scheduled worker receives only `TPP_SUPABASE_URL` and `TPP_SUPABASE_SERVICE_ROLE_KEY` as database secrets. It does not receive the OpenAI key, Supabase anon key, or OAuth secrets.

The delivery ledger persists bounded identifiers/status only. It does not retain recipient email, class/course reminder lists, email body, reflection text, lesson-plan content, student data, generated insight, or SES MessageId.

## Approved schedule

The automatic delivery schedule is now approved for the Anniston pilot in `America/Chicago`:

- **Teacher courtesy reminder:** Friday at **2:00 PM local time** — `cron(0 14 ? * FRI *)`.
- **School-administrator aggregate digest:** Friday at **3:30 PM local time** — `cron(30 15 ? * FRI *)`.

The 90-minute courtesy window is intentional. Teachers with every required submission complete receive no reminder. Teachers with an outstanding item receive one combined email that names the exact professional class/course and whether the missing item is the current-week reflection/completed packet, the following-week lesson plan, or both.

The administrator email contains aggregate counts and the authenticated TPP link only. Teacher/class exceptions remain behind authenticated reporting.

Instruction-requirement logic suppresses false missing states when an assignment has no expected meeting in the relevant week based on effective assignment dates, meeting pattern, explicit non-instructional calendar days, and schedule exceptions.

## Phase D — Activate both isolated schedules

Run **Enable TPP Friday Notifications** only after every workflow confirmation is true:

- scheduled Friday notification migration applied;
- approved SES notifications active;
- exact 2:00 PM / 3:30 PM schedule approved;
- privacy/subprocessor and Help review complete;
- live governed deployment-role policies updated;
- dedicated Supabase service-role secret exists at the governed path.

The workflow must:

1. verify the main pilot stack and SES state;
2. resolve the current immutable application image;
3. verify the interactive web task still lacks the service-role credential;
4. deploy the isolated Friday worker stack with both schedules `DISABLED`;
5. verify the teacher task command is exactly `python -m app.scheduled_digest_worker teacher`;
6. verify the admin task command is exactly `python -m app.scheduled_digest_worker admin`;
7. verify both isolated tasks receive only the two approved Supabase secrets;
8. verify teacher schedule `cron(0 14 ? * FRI *)`, admin schedule `cron(30 15 ? * FRI *)`, and `America/Chicago` while disabled; and
9. change both schedules to `ENABLED` only after those checks pass.

The activation workflow does not call `ecs run-task`, does not invoke the worker immediately, and sends no immediate/test email.

## First scheduled execution acceptance

At the first approved Friday windows:

- verify the 2:00 PM teacher task runs once and only teachers with outstanding required submissions are claimed;
- verify a multi-class teacher receives one email, with the exact missing class(es) and item(s);
- verify a fully complete teacher receives no reminder;
- verify the 3:30 PM administrator task runs once and sends the aggregate current-closeout/following-plan summary to eligible active `school_admin` recipients;
- verify at-most-once claims prevent duplicate automatic sends on retries;
- verify worker logs do not print recipient addresses, teacher names, course names, message bodies, school identifiers, credentials, or SES MessageIds;
- verify no teacher names or class-level exception list appears in the administrator email;
- verify no student data appears anywhere in the workflow.

Manual delivery/recovery, if retained, is controlled operational support and not a normal administrator-facing UI action.

## Evidence to retain

Keep bounded release evidence:

- exact accepted `main` SHA;
- exact immutable image digest and ECS task definition;
- CI/source-verification run IDs;
- live migration head;
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

If automatic delivery is unsafe, disable both EventBridge Scheduler schedules first so no new tasks launch, then remediate the worker/database path. UI hiding is never a scheduler kill switch.
