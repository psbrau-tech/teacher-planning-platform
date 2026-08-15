# Scheduled Admin Weekly Digest Decision — Superseded

**Original date:** 2026-08-14  
**Superseded:** 2026-08-15  
**Status:** Historical decision record; not the current implementation contract  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Supersession

This document recorded the original admin-only automatic weekly-digest direction. It is superseded by:

`docs/governance/FRIDAY_STATUS_NOTIFICATION_DECISION_2026-08-15.md`

and the reconciled controlled release runbook:

`docs/governance/INTELLIGENCE_NOTIFICATION_CONTROLLED_RELEASE_RUNBOOK_2026-08-14.md`.

Do not use this file as the current source for recipient scope, schedule, worker command, migration filename, or activation sequence.

## What remains valid from the original decision

The following governance principles remain in force:

- automatic email is an operational convenience and does not expand TPP's adult educator/administrator data boundary;
- the interactive web ECS task must never receive `TPP_SUPABASE_SERVICE_ROLE_KEY`;
- scheduled delivery runs in isolated short-lived ECS/Fargate tasks;
- the isolated worker receives only the minimum Supabase service-role database credentials required for its service-role-only candidate functions and does not receive the OpenAI key, Supabase anon key, PostgreSQL database URL, or Google/OAuth credentials;
- SES permission is limited to the approved professional sender identity;
- automatic delivery uses at-most-once claims before send attempts;
- the retained delivery ledger does not persist recipient email, email body, reflection text, lesson-plan content, generated instructional insight, student data, or SES MessageId;
- worker logs must not print recipient addresses, teacher names, course names, message bodies, school identifiers, credentials, or provider IDs; and
- scheduler/SES activation remains a separately controlled operational boundary rather than an effect of normal application deployment.

## Current approved replacement

The current design is a coordinated Friday workflow in `America/Chicago` for the Anniston Pilot:

- **2:00 PM Friday:** a teacher courtesy reminder is sent only when a required current-week reflection/completed packet or following-week lesson plan is still missing. One email combines all outstanding items and names the exact professional class/course for each missing submission.
- **3:30 PM Friday:** eligible school administrators receive an automatic aggregate status digest. Teacher/class exceptions remain behind authenticated TPP reporting.
- **Teacher Dashboard:** class-by-class current-closeout and following-week-plan status.
- **Administration reporting:** authorized teacher/class operational status for follow-up.
- **Normal administrator UI:** no routine manual `Weekly admin email` control. Any retained manual path is controlled recovery only.

The teacher email may contain the professional course name because that specificity is necessary to make the reminder actionable. It must not contain reflection text, lesson-plan content, generated insight, student data, or teacher-performance/evaluation language.

The administrator email remains aggregate counts plus an authenticated link; it does not contain teacher names or class-level exception lists.

## Current migration and activation boundary

The implementation is split deliberately:

- `20260815011000_friday_submission_status.sql` — authenticated dashboard/report status sources and instruction-requirement logic. This may be released while email remains fail-closed.
- `20260815013000_scheduled_friday_notifications.sql` — scheduled delivery ledger and service-role-only teacher/admin candidate functions. This remains deferred until automatic email activation is explicitly prepared.

The Friday activation workflow stages both exact schedules disabled, verifies the immutable image, exact worker commands, exact secret set, schedule expressions, timezone, and the interactive service-role exclusion, then enables both schedules only after all manual activation confirmations are satisfied. It does not invoke a worker immediately or send a test email.

Git history retains the original August 14 admin-only decision for historical provenance.
