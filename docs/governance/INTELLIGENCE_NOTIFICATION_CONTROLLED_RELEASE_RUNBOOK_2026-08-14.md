# Reflection Intelligence, Assessment Analytics, PLC Artifacts, and Notifications — Controlled Release Runbook

**Date:** 2026-08-14  
**Status:** Release-preparation runbook; no live action is authorized by this document alone  
**Scope:** Teacher Planning Platform (TPP) controlled pilot, AWS `us-east-2`

## Purpose

This runbook defines the controlled path from merged source code to an accepted pilot release for the August 14 professional-learning and notification work.

It covers:

- Reflection Intelligence;
- daily formative-assessment analytics and weekly trends;
- PLC facilitation artifacts;
- manual school-admin weekly email digests;
- optional automatic school-admin weekly digest delivery; and
- Platform Owner product-adoption reporting for those features.

The order is intentional. Database and application functionality may be released while email remains fail-closed. SES and automatic delivery each have their own later activation gates.

## Non-negotiable release boundaries

At every step:

- TPP remains adult educator/administrator professional planning only.
- Student PII, student education records, student assessment results, identifiable student work, IEP/504, health/discipline data, and student-level analytics remain prohibited.
- The 12 required Weekly Reflection / PLC Discussion responses remain teacher-authored. AI may not suggest, generate, complete, or rewrite those required responses.
- Reflection Intelligence operates only after teacher-authored reflection submission.
- School Reflection Intelligence remains anonymous/aggregate and subject to its distinct-source support threshold.
- Formative-assessment analytics describe planned instructional signals only; they are not evidence that an assessment was administered and are not teacher-performance/compliance measures.
- The first-release admin email remains counts + authenticated TPP link only.
- The interactive web ECS task must not receive a Supabase service-role credential.
- No source merge, successful CI run, or CloudFormation template alone proves a live feature was activated.

## Phase 0 — Freeze the exact release candidate

Before any database or AWS action:

1. Confirm every intended PR is merged to `main`.
2. Record the exact `main` commit SHA.
3. Confirm the exact-head CI and required governed source verification are green.
4. Confirm there are no unresolved required-review threads or release-blocking governance findings.
5. Record the currently deployed immutable image digest and ECS task definition.
6. Record the current Supabase migration head actually applied in the pilot database.
7. Compare the applied migration head with repository migration order; do not infer database state from Git history alone.
8. Confirm the currently deployed pilot is healthy before changing it.

**Evidence to retain:** main SHA, workflow-run IDs, current image digest, current ECS task definition, current migration head, and pre-release health check.

## Phase 1 — Privacy, Help, and counsel packet reconciliation

Before enabling any new data flow:

1. Confirm the pre-release Privacy Policy, AI Use & Accuracy Notice, Security & Data Practices, Subprocessor List, Help content, and counsel brief match the exact release candidate.
2. Confirm the documents state that required weekly reflection is teacher-authored and that Reflection Intelligence is post-submission analysis.
3. Confirm formative-assessment analytics are described as planned signals rather than student results or teacher evaluation.
4. Confirm Amazon SES and scheduled delivery are described as conditional/fail-closed until separately activated.
5. Confirm the approved application From address is exactly `notifications@planner.guidedscholar.ai`.
6. Preserve the documents as pre-release drafts until publication/effective-date approval is separately given.

Counsel review may continue in parallel with source preparation. Public-policy effectiveness and live email activation remain separate decisions.

## Phase 2 — Apply only the required governed database migrations

Use the existing governed Supabase migration process. Apply migrations in repository order and only after confirming which are not already present in the pilot database.

The August 14/15 feature set includes the following relevant migrations:

1. `20260814190000_reflection_intelligence_foundation.sql`
   - Reflection Intelligence source/telemetry foundations.
2. `20260814190100_ai_usage_actor_policy.sql`
   - governed non-teacher AI actor accounting for authorized admin Reflection Intelligence.
3. `20260814231500_notification_delivery_events.sql`
   - content-free manual notification delivery telemetry.
4. `20260815001500_daily_formative_assessment_analytics.sql`
   - governed school daily-assessment source RPC using immutable submitted lesson plans.
5. `20260815011000_scheduled_admin_digest_worker.sql`
   - service-role-only automatic-digest claim/completion boundary and scheduled-delivery ledger.

### Migration acceptance checks

After each migration group:

- verify the migration version is present in the database migration history;
- verify PostgREST schema reload completed where required;
- verify authenticated authorization remains fail-closed outside the intended role/school scope;
- verify no student-data table/source was added;
- verify no raw reflection or lesson-plan text was copied into analytics/event tables;
- verify the interactive application still does not require a Supabase service-role key.

The scheduled-worker migration may be deferred until automatic email delivery is actually being prepared. Manual email, Reflection Intelligence, assessment analytics, and PLC artifacts do not require the automatic scheduler to exist.

## Phase 3 — Deploy the application with email still disabled

This phase releases the professional-learning/application features while keeping SES fail-closed.

1. Build/publish an immutable image from the accepted `main` SHA through the governed deployment workflow.
2. Require the deployment workflow's exact expected-main-SHA and expected-migration-head checks.
3. Keep `SesFromEmail` and `SesIdentityArn` blank unless the separate SES activation phase has already been approved.
4. Deploy the accepted image.
5. Verify ECS stability and exact image provenance.
6. Verify the web task's runtime secret set still excludes `TPP_SUPABASE_SERVICE_ROLE_KEY`.

### Browser/API acceptance before email activation

Using synthetic or permitted adult professional pilot content only, validate:

- private teacher recap uses only that teacher's submitted reflections;
- school PLC brief requires an authorized reporting role and preserves anonymous aggregate sourcing;
- themes lacking the required distinct-source support are not surfaced as common themes;
- PLC facilitation handout renders/prints with the professional-learning boundary;
- formative-assessment analytics read only submitted lesson-plan planning fields;
- exit tickets/slips and other deterministic types are counted as expected;
- weekly trends show coverage context and are not normalized into teacher compliance rates;
- Platform Owner adoption counts are content-free/product-use signals;
- the disabled email action fails closed while SES is unconfigured.

**Do not continue to SES activation if the professional-learning release is not accepted independently.**

## Phase 4 — Verify the SES identity manually in AWS

This is a human AWS action.

Use Amazon SES in **`us-east-2`**, matching the pilot region and source-controlled runtime configuration.

Preferred governed options are:

- verify the exact email identity `notifications@planner.guidedscholar.ai`; or
- verify the domain identity `planner.guidedscholar.ai`, while the application still locks the actual From address to `notifications@planner.guidedscholar.ai`.

If SES requires DNS records for the chosen identity, add only the SES-provided records through the authoritative DNS provider and wait for verification. Do not invent DKIM/verification values.

Record the resulting exact SES identity ARN. The controlled activation workflow accepts only the approved email identity ARN or the `planner.guidedscholar.ai` domain identity ARN in `us-east-2` for the governed AWS account.

### SES account sending status

Before activation, confirm whether the SES account is still in the SES sandbox. In the sandbox, recipient restrictions apply. If professional pilot recipients cannot legally/technically be reached under the current SES account status, request production access before enabling the TPP sender.

Do not represent a requested SES production-access increase as approved until AWS reports it as approved.

## Phase 5 — Update the live governed deployment-role policies

The repository contains least-privilege policy documents for the GitHub OIDC deployment role and the dedicated CloudFormation execution role.

Before either SES or the scheduled worker is activated:

1. Review the exact accepted policy files in `infra/iam/`.
2. Compare them to the live AWS role policies; do not assume source and AWS are identical.
3. Use the existing governed role-configuration process to update the live policies to the accepted source-controlled version.
4. Verify the existing interactive deployment scopes were not broadened accidentally.
5. Record the resulting role-policy versions/evidence.

For SES, the CloudFormation execution role must be able to manage the exact TPP task-role inline policy required by the main stack.

For the later scheduled worker, the role policies additionally permit only the exact scheduled task roles, exact Scheduler resource, scheduled log group, scheduled CloudFormation stack, and service-role secret metadata path defined by the accepted release.

## Phase 6 — Activate the approved SES sender without sending an email

Run the source-controlled **Enable TPP SES Notifications** workflow only after:

- the SES identity is verified in `us-east-2`;
- the SES account can send to the intended professional recipients;
- privacy/subprocessor and Help review for the enabled email data flow is complete; and
- live governed AWS role policies match the accepted release.

Supply the exact verified SES identity ARN and confirm all workflow gates.

The activation workflow is designed to:

- preserve the accepted immutable application image;
- update only the main stack's SES parameters;
- set `TPP_SES_FROM_EMAIL` to `notifications@planner.guidedscholar.ai`;
- set `TPP_SES_REGION` to the AWS Region;
- attach `ses:SendEmail` to the application task role scoped to the approved SES identity; and
- verify the resulting task configuration.

The activation workflow itself sends **no test email**.

### Immediate post-activation checks

- verify main stack status is stable;
- verify `SesNotificationsStatus` reports configured;
- verify the runtime From address is exact;
- verify the application image is unchanged;
- verify the interactive web task still has its original governed database-secret set and no Supabase service-role credential;
- verify no SES open/click tracking or configuration-set tracking was introduced.

## Phase 7 — Perform one bounded authenticated manual email acceptance test

After SES infrastructure activation is accepted, use an authorized school administrator's authenticated TPP account.

1. Select an approved Monday-starting week.
2. Trigger **Email digest to my TPP account**.
3. Confirm the recipient is the authenticated administrator's own governed professional address; there is no arbitrary-recipient field.
4. Confirm the From address is `notifications@planner.guidedscholar.ai`.
5. Confirm the message contains only approved operational counts, PLC-brief availability wording, and the authenticated TPP link.
6. Confirm the message contains no teacher names, teacher-level exception list, reflection text, generated instructional insight, student information/results/work, or teacher-quality/performance content.
7. Confirm notification telemetry records only the approved content-free event and does not persist the body, recipient address, or SES MessageId.
8. Confirm application/CloudWatch logs do not reveal message content, recipient addresses unnecessarily, credentials, or provider response bodies.

If this acceptance test fails, stop scheduled-email preparation and disable/fix the email path before proceeding.

## Phase 8 — Prepare the isolated scheduled-worker secret

This phase is required only if automatic weekly admin delivery is approved for activation.

1. Confirm `20260815011000_scheduled_admin_digest_worker.sql` is applied and accepted.
2. Obtain the existing Supabase service-role credential through the governed Supabase/admin process; do not expose it in chat, source, workflow inputs, logs, or screenshots.
3. Create/update a dedicated AWS Secrets Manager secret under the governed path matching:
   - `tpp/pilot/supabase-service-role-key-*`
4. Record the secret ARN, not the secret value, for the scheduled-worker activation workflow.
5. Verify the secret value is not present in the main ECS task definition, GitHub variables, ordinary logs, source, or browser configuration.

The scheduled worker uses this elevated credential only to invoke purpose-built service-role database functions that return the minimized professional recipient/count manifest.

## Phase 9 — Make the remaining human schedule decision

Automatic delivery has **no approved clock time yet**.

Before enabling it, the product owner/school leadership must choose:

- the exact weekly day/time;
- the exact EventBridge Scheduler cron expression representing that time; and
- the school-local IANA timezone.

The source-controlled default timezone is `America/Chicago`, which matches the current Alabama pilot, but the exact schedule expression must be supplied and explicitly approved at activation.

Also decide whether automatic delivery should run during weeks with no instruction, holidays, or extended closures. If suppression behavior is desired beyond current database eligibility, implement/test that behavior before activation rather than assuming it.

## Phase 10 — Activate the isolated scheduled worker

Run **Enable TPP Scheduled Admin Digest** only after every workflow confirmation is true:

- database migration applied;
- SES notifications active;
- exact schedule approved;
- privacy/subprocessor and Help review complete;
- live deployment-role policies updated;
- dedicated Supabase service-role secret exists at the governed path.

The activation workflow is designed to:

1. verify the main pilot stack is healthy and SES is configured;
2. resolve the current immutable application image from the accepted pilot service;
3. verify the interactive web task still lacks the service-role credential;
4. deploy the separate scheduled-worker stack with `ScheduleState=DISABLED`;
5. verify the scheduled task command is exactly `python -m app.scheduled_digest_worker`;
6. verify the scheduled worker receives only `TPP_SUPABASE_URL` and `TPP_SUPABASE_SERVICE_ROLE_KEY` as secrets;
7. verify it does not receive the OpenAI key, Supabase anon key, or OAuth secrets;
8. verify the exact approved schedule expression and timezone while disabled; and
9. update the schedule to `ENABLED` only after those checks pass.

The workflow does not run the worker immediately and does not send an immediate/test email.

## Phase 11 — Observe first scheduled execution

At the first approved scheduled window:

- verify exactly one task is launched;
- verify task exit status and bounded logs;
- verify no recipient address, message body, school identifier, secret, or SES MessageId is printed by the worker;
- verify each eligible active `school_admin` professional recipient is claimed at most once for the week;
- verify failed/uncertain automatic claims are not automatically duplicated;
- verify any failed automatic delivery can still be handled through the authenticated manual-send path;
- verify Platform Owner reporting distinguishes scheduled from manually triggered delivery;
- verify no teacher, district-admin, or Platform Owner account receives an automatic message solely because of those non-school-admin roles.

## Phase 12 — Release closeout evidence

Retain a compact release record containing:

- accepted `main` SHA;
- exact immutable image digest;
- CI/governed-source workflow IDs;
- applied database migration head;
- ECS main task definition;
- SES identity ARN and verification/sending status evidence;
- main-stack SES configuration evidence;
- manual email acceptance result;
- if enabled: scheduled-worker stack/task definition;
- if enabled: approved cron expression/timezone and Scheduler state;
- if enabled: service-role secret ARN only, never the secret value;
- live IAM policy evidence;
- Help/privacy/subprocessor review evidence; and
- any rollback/remediation performed during acceptance.

Do not record customer content, reflection text, lesson-plan text, student data, credentials, recipient email addresses, or email bodies in the release evidence when bounded identifiers/status are sufficient.

## Stop conditions requiring human intervention

Stop and request human action/decision when any of the following is reached:

- SES identity/DNS verification;
- SES production-access approval if required;
- creation/update of the dedicated AWS Secrets Manager service-role secret;
- applying live AWS IAM policy changes if no governed automated path is already authorized;
- choosing the automatic delivery day/time/cron expression;
- applying database migrations or deploying an application image when the controlled release requires explicit deployment authorization;
- running either email activation workflow;
- sending the first live/pilot email acceptance message;
- publishing/making legal policies effective; or
- any change that would expand the data boundary, reporting audience, retained professional content, or personnel/evaluation use.

## Rollback principles

If a professional-learning feature fails but email is unaffected, roll back the application/database release through the existing governed release process using exact-image/migration evidence.

If manual email delivery is unsafe or incorrectly configured, stop sending immediately and remove/disable the SES runtime configuration before further acceptance.

If automatic delivery is unsafe or incorrectly configured, disable the EventBridge schedule first so no new tasks launch, then remediate the scheduled-worker stack/database path. Do not rely on application UI hiding to stop an AWS Scheduler target.

Rollback must preserve audit evidence needed to understand the release without retaining prohibited customer/student content.
