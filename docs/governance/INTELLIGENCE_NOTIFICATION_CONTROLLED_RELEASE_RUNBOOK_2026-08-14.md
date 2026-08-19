# Reflection Intelligence, Friday Status, and Notifications — Controlled Release Runbook

**Original date:** 2026-08-14  
**Reconciled:** 2026-08-19  
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

## Current accepted release state

The accepted Reflection Intelligence / PLC / formative-assessment, Friday-status, multi-school, and governed Reply-To application release is live through migration `20260815220500_harden_school_local_notification_windows.sql`.

Release #46 is deployed and verified from exact `main` SHA `162bf35f80e9836ed31f3b884da167a2bed6ec9d`. The accepted immutable image and ECS task definition are release evidence; SES application sending and the Friday dispatchers remain separate activation gates.

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

The controlled migration workflow verified the live database up to date through `20260815220500`. Applying this schema did **not** enable email: school notification flags remain fail-closed, SES application sending is not yet activated in the TPP stack, and the EventBridge Scheduler dispatchers remain inactive.

Repository source state and live database state are separate evidence. Future migrations still require an exact target-scoped preview and explicit mutating approval.

## District and school provisioning contract

The pilot provisioning path must treat district and school as explicit authorization boundaries rather than assuming Anniston High School.

The governed configuration identifies district, school, one district per school, a required IANA timezone, school-local notification settings, and one explicit configured district/school pair for each professional account.

New schools default to:

- teacher reminders **disabled**;
- administrator digests **disabled**;
- teacher reminder local time **2:00 PM**; and
- administrator digest local time **3:30 PM**.

The provisioning and read-only preflight scripts validate district names, district-to-school relationships, IANA timezone identifiers, quarter-hour local send times, and account district/school pairs before database mutation.

Each professional email has one explicit school assignment. A `school_admin` is authorized only for that assigned school. A `district_admin` is assigned one school in the governed district; the database resolves `profiles.school_id -> schools.district_id` through `private.current_district_id()` and permits reporting only on schools with that same `district_id`. `platform_admin` remains intentionally platform-scoped.

TPP does not simulate district access by duplicating a district administrator across every school. Moving a professional account to a different school or district is an explicit governed authorization change.

For the current pilot, the intended district graph includes:

- **Anniston City Schools**
  - Anniston High School
  - Anniston Middle School

## Phase A — Friday status dashboard release

The Friday status dashboard is released and remains independent from email activation.

Accepted behavior includes:

- teacher views of required current-week completed-packet/reflection submission and following-week plan submission;
- not-required states when no instruction is expected;
- administrator operational status constrained to governed reporting scope;
- no student data or reflection/lesson-plan body in the status API;
- immutable submission-state evidence; and
- no normal administrator-facing manual weekly email action.

SES remains fail-closed until Phase B is intentionally completed.

## Phase B — SES identity, production access, and feedback readiness

The approved From address is exactly `notifications@planner.guidedscholar.ai` in `us-east-2`. The approved monitored Reply-To address is exactly `peter@brauconsulting.com`. Application delivery must reject a different From or Reply-To address.

As of the 2026-08-19 reconciliation:

- the SES domain identity `planner.guidedscholar.ai` is verified in `us-east-2`;
- Easy DKIM is successful and enabled;
- the three SES DKIM CNAME records are present in the authoritative Route 53 zone;
- AWS approved production sending access and moved the SES account out of the sandbox in `us-east-2`;
- AWS reported a 50,000-message daily quota and a maximum send rate of 14 messages per second; and
- TPP SES application sending is still inactive.

Production access does not itself authorize TPP application sending.

Before **Enable TPP SES Notifications** may be run:

- SES account-level suppression must be enabled for both `BOUNCE` and `COMPLAINT`;
- a dedicated `us-east-2` SNS topic must receive both Bounce and Complaint feedback for the verified `planner.guidedscholar.ai` identity;
- the operational subscription to `peter@brauconsulting.com` must be confirmed and monitored;
- after both SNS feedback paths are working, duplicate SES email feedback forwarding should be disabled because the From identity is send-only;
- privacy/subprocessor and Help review must match the enabled email data flow;
- live deployment-role policies must match the accepted source-controlled policies;
- the approved From address and SES identity ARN must be recorded; and
- the interactive web task must still exclude the Supabase service-role credential.

The exact provider procedure is `docs/governance/SES_FEEDBACK_CONTROLS_RUNBOOK_2026-08-19.md`.

The monitored reply path is explicit: ordinary recipient replies are directed to `peter@brauconsulting.com`; TPP does not require inbound mail service on `planner.guidedscholar.ai` for this purpose.

The **Enable TPP SES Notifications** workflow requires an explicit feedback-controls confirmation, updates the governed SES configuration, preserves the accepted application image, and sends no test email. The activation workflow itself sends **no test email**.

## Phase C — Scheduled Friday delivery preparation

The notification migration chain through `20260815220500_harden_school_local_notification_windows.sql` is already applied and verified. Do not re-run it merely as part of SES activation.

Create/update the dedicated Secrets Manager secret for the existing Supabase service-role credential under the governed `tpp/pilot/supabase-service-role-key-*` path. Record only the ARN. Never place the value in source, chat, workflow inputs, browser configuration, or ordinary logs.

The scheduled worker receives only `TPP_SUPABASE_URL` and `TPP_SUPABASE_SERVICE_ROLE_KEY` as database secrets. It does not receive the OpenAI key, Supabase anon key, or OAuth secrets.

The delivery ledger persists bounded identifiers/status only. It does not retain recipient email, class/course reminder lists, email body, reflection text, lesson-plan content, student data, generated insight, or SES MessageId.

Run governed provisioning with the approved district/school configuration before enabling dispatchers. Confirm every configured school has the intended district, IANA timezone, and notification flags. A school whose flags remain disabled must not produce candidates.

## Approved school-local Friday delivery behavior

For the current Anniston pilot:

- teacher courtesy reminder: Friday at **2:00 PM local time**;
- school-administrator aggregate digest: Friday at **3:30 PM local time**.

`America/Chicago` is stored independently on each Anniston school rather than treated as a platform-wide constant. Future schools must carry their own validated IANA timezone and explicit district assignment.

The 90-minute courtesy window is intentional. Teachers with all required submissions complete receive no reminder. A teacher with outstanding items receives one school-specific combined message that can name the exact professional class/course and whether the missing item is the current-week reflection/completed packet, the following-week lesson plan, or both.

The administrator email contains aggregate counts and the authenticated TPP link only. Teacher/class exceptions remain behind authenticated reporting. The current email-recipient policy remains `school_admin`; broader roles do not silently become email recipients.

## Dispatcher architecture

The two tightly scoped EventBridge Scheduler resources are quarter-hour dispatchers, not fixed school-time senders:

- teacher dispatcher: `tpp-pilot-teacher-friday-reminder`;
- administrator dispatcher: `tpp-pilot-admin-weekly-digest`;
- dispatcher expression: `cron(0/15 * ? * * *)`;
- dispatcher timezone: `UTC`.

Every quarter hour, the isolated worker asks the database which enabled schools are inside each school's local Friday delivery window. The database converts the dispatcher timestamp using the school's IANA timezone and the worker makes an explicit claim with that exact `school_id`.

This design preserves school-local daylight-saving behavior, school-by-school enablement, explicit school scope, and school-scoped at-most-once delivery keys. The quarter-hour dispatcher does not mean an email is sent every 15 minutes; outside a due school-local window the worker sends nothing.

## Phase D — activate isolated dispatchers

Run **Enable TPP Friday Notifications** only after all gates are true:

- notification-control migrations applied;
- approved SES application sending active and verified;
- required SES suppression and monitored feedback controls operational;
- enabled schools have approved district, IANA timezone, and local notification settings;
- privacy/subprocessor and Help review complete;
- live governed deployment-role policies current; and
- dedicated Supabase service-role secret exists at the governed path.

The workflow must stage both dispatchers `DISABLED`, verify the isolated task commands and secret boundary, verify the exact schedule names/expression/timezone, and only then change both dispatchers to `ENABLED`. It does not invoke the worker immediately and sends no immediate/test email.

## First scheduled execution acceptance

At the first approved Friday windows for an enabled school, verify:

- the teacher worker runs in the school's configured 2:00 PM local window;
- only teachers with outstanding required submissions are claimed for that school;
- a multi-class teacher receives one school-specific reminder;
- a fully complete teacher receives no reminder;
- the administrator worker runs in the school's configured 3:30 PM local window;
- eligible active `school_admin` recipients receive only their assigned school's aggregate digest;
- district/platform roles do not silently become school-admin email recipients;
- a school with notification flags disabled receives no automatic email;
- at-most-once claims prevent duplicate sends;
- worker logs do not print recipient addresses, teacher names, course names, message bodies, school identifiers, credentials, or SES MessageIds;
- no teacher names or class-level exception list appears in administrator email; and
- no student data appears anywhere in the delivery path.

Manual delivery/recovery, if retained, is controlled operational support and not a normal administrator-facing UI action.

## Feedback-event operational response

A bounce or complaint notification is an operational delivery signal, not professional evaluation data.

When feedback arrives through the monitored SNS path:

- verify suppression status when the event qualifies;
- do not repeatedly send to a hard-bounced or complained-about destination;
- review complaint events as a stop-sending signal for the affected recipient;
- pause the affected school's notification flag or global SES path if an unexpected pattern indicates risk; and
- do not use feedback events for teacher ranking, quality scoring, or employment evaluation.

## Evidence to retain

Keep bounded release evidence:

- exact accepted `main` SHA;
- exact immutable image digest and ECS task definition;
- CI/source-verification run IDs;
- live migration head;
- governed district names, school names/timezones, and notification enabled/disabled state without copying staff rosters;
- SES identity/sending-status and feedback-control evidence if activated;
- exact scheduled task definitions and Scheduler states if activated;
- service-role secret ARN only, never its value;
- live IAM-policy evidence;
- Help/privacy/subprocessor review evidence; and
- acceptance/rollback results.

Do not retain customer content, reflection text, lesson-plan text, student data, credentials, ordinary recipient email addresses, or message bodies when bounded identifiers/status are sufficient. The approved From, Reply-To, and operational feedback subscription address may be retained as infrastructure-control evidence.

## Stop conditions requiring human intervention

Stop for human action/approval at:

- applying live database migrations;
- changing governed district/school access or notification configuration for real professional accounts;
- creating a new district or school with real professional users;
- moving an existing professional account to another school or district;
- enabling notifications for a school for the first time;
- deploying an application image when the controlled release gate requires manual workflow dispatch;
- SES identity/DNS verification;
- configuring or materially changing SES suppression, SNS feedback, or feedback-forwarding controls;
- live AWS IAM policy updates when no governed automated path is already authorized;
- creation/update of the service-role secret;
- running the SES activation workflow;
- running the Friday notification activation workflow;
- first live/pilot email delivery acceptance when a recipient-side check is required;
- publishing/making legal policies effective; or
- any data-boundary, reporting-audience, retention, or personnel/evaluation expansion.

## Rollback

If the application release is defective, use the exact-image/database release evidence and governed rollback process.

If SES application configuration is unsafe, disable the SES sending configuration before further acceptance.

If automatic delivery is unsafe, disable both EventBridge Scheduler dispatchers first so no new tasks launch, then remediate the worker/database/SES path. UI hiding is never a scheduler kill switch.

If one school's notification configuration is unsafe while shared infrastructure remains sound, disable that school's teacher/admin notification flags through governed provisioning rather than disabling unrelated schools.
