# Scheduled Admin Weekly Digest Decision

**Date:** 2026-08-14  
**Status:** Approved implementation direction; scheduler remains unactivated  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Purpose

School leadership approved a notification layer to reduce repetitive weekly operational follow-up. This slice prepares an automatic weekly school-admin digest using the same deliberately minimized content contract as the authenticated manual digest.

Automatic delivery is an operational convenience. It does not expand the instructional, privacy, personnel, or student-data boundary.

## First scheduled recipient scope

The first automatic release is limited to active governed TPP accounts holding the `school_admin` role for their own school.

The scheduled worker does not deliver to:

- teachers;
- district administrators;
- Platform Owners solely because of those roles;
- arbitrary addresses supplied by a client or workflow; or
- accounts outside the governed TPP professional email boundary.

Broader recipient rules, individual teacher reminders, custom reminders, and potentially-minimal-reflection reminders remain separate future decisions.

## Email content boundary

The scheduled worker reuses the existing `WeeklyAdminDigestMetrics` and `send_weekly_admin_digest` path. The email remains limited to school-scoped operational counts plus the authenticated TPP link.

The first scheduled digest must not contain:

- teacher names or teacher-level exception lists;
- teacher reflection text;
- AI-generated instructional insight;
- student PII or student education records;
- student assessment results;
- identifiable student work;
- teacher quality, performance, effort, productivity, rating, ranking, or personnel judgments; or
- secrets, internal identifiers, SES MessageIds, or provider response bodies.

## Isolated execution architecture

The automatic worker is intentionally separate from the interactive TPP web task.

The main web ECS task continues to use the governed authenticated-user Supabase path and must not receive `TPP_SUPABASE_SERVICE_ROLE_KEY`.

A separate EventBridge Scheduler target runs a short-lived Fargate task using the accepted immutable TPP application image with a different command:

`python -m app.scheduled_digest_worker`

Only that scheduled task receives the Supabase service-role credential. Its execution role can read only the Supabase URL secret and the separately created service-role secret. It does not receive the OpenAI API key, the Supabase anon key, or Google/OAuth credentials.

Its task role can call only `ses:SendEmail` against the approved SES identity.

## Database boundary and at-most-once claims

The scheduled worker may not query unrestricted planning content through generic service-role table access in application code. Instead, it invokes service-role-only database functions that return a content-minimized manifest containing:

- a transient delivery claim identifier;
- school and professional profile identifiers needed for governed delivery accounting;
- the recipient professional email address for the current send only; and
- the already-approved aggregate submission counts needed by the weekly digest.

The manifest excludes course names, teacher names, raw lesson-plan text, reflection content, generated insight, and all student information.

Before a candidate is returned, the database atomically inserts a unique claim for notification type + professional recipient profile + week. This gives the automatic path conservative at-most-once behavior across scheduler/task retries.

If a worker claims a delivery and then cannot complete it, that automatic claim is marked failed or remains claimed and is not automatically resent. An authorized administrator may still use the existing authenticated manual-send path. Avoiding an accidental duplicate automated email takes precedence over automatic retry convenience in the first release.

## Retained scheduled-delivery data

The scheduled-delivery ledger retains only:

- school ID;
- recipient professional profile ID;
- week start;
- notification key;
- claimed/sent/failed status; and
- claim/completion timestamps.

It does not persist the recipient email address, email body, SES MessageId, reflection text, generated insight, teacher names, student data, or provider response content.

Platform Owner adoption reporting may aggregate successful scheduled deliveries, distinct recipient administrators, and schools reached. These are product-adoption/operations signals, not staff-performance measures.

## Schedule activation remains a human gate

No weekly clock time is selected or activated by this code change.

The separate scheduled stack requires an explicit EventBridge Scheduler cron expression. The controlled activation workflow requires a human to approve the exact schedule expression and school-local timezone before enabling it.

The stack is staged with the schedule `DISABLED`, verifies the immutable image, isolated command, exact two-secret worker set, and approved schedule expression/timezone, and only then updates the schedule to `ENABLED`.

The activation workflow does not run the task immediately and does not send a test email.

## Required activation prerequisites

Before automatic delivery is enabled, all of the following must be complete:

1. the scheduled-digest database migration is applied and accepted;
2. the approved SES sender is verified and active in `us-east-2`;
3. the Supabase service-role key is stored in its own AWS Secrets Manager secret at the governed TPP path;
4. the GitHub deployment role and CloudFormation execution-role policies are updated to the exact scheduled-worker resources in this release;
5. privacy/subprocessor and Help text are reconciled for automatic professional email delivery;
6. the exact weekly schedule expression and `America/Chicago` (or other explicitly approved school-local IANA timezone) are approved; and
7. the controlled activation workflow is run against an accepted immutable application image.

Merging this slice does not satisfy those prerequisites and does not authorize deployment, migration application, scheduler creation, or email delivery.
