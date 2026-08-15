# Friday Submission Status and Notification Decision

**Date:** 2026-08-15  
**Status:** Approved product design; dashboard implementation may ship before email activation  
**Data boundary:** Adult educator/administrator professional operational data only; no student data

## Decision

TPP will treat Friday submission support as one coordinated professional workflow rather than a manual email feature.

### Teacher dashboard

The teacher Dashboard will show class-by-class status for:

- the current Monday-starting week's required reflection/completed packet; and
- the following Monday-starting week's required lesson plan.

Status is based on immutable submitted records, not draft presence. The submitted completed packet is the authoritative signal that the teacher-authored weekly reflection was submitted because the completed-packet submission path already requires the reflection.

A class is marked `Not required` when its active assignment, meeting pattern, academic calendar, and schedule exceptions indicate no expected instructional meeting in the relevant week.

### Teacher courtesy reminder

When automatic email delivery is activated, TPP will run the teacher reminder at **2:00 PM Friday in the school-local `America/Chicago` timezone** for the Anniston pilot.

A teacher receives no email when every required item is already submitted. A teacher with outstanding work receives one combined courtesy reminder, not one email per class. The message names each exact professional course/class with an outstanding submission and indicates whether it is missing:

- the current week's reflection/completed packet;
- the following week's lesson plan; or
- both.

The message is supportive and operational. It must not frame the reminder as teacher evaluation, quality, effort, productivity, or a compliance score. It contains no reflection text, lesson-plan content, student information, generated instructional insight, or teacher-quality score.

### Administrator dashboard

Authorized administration reporting will show teacher- and class-level operational status for the same two submission windows. This detail stays behind TPP authentication and existing school/district/platform reporting authorization.

The report may identify teacher and professional course because that information is needed for operational follow-up. It must not add student data, teacher ranking, normalized performance rates, or instructional-quality inferences.

### Automatic administrator digest

When automatic delivery is activated, TPP will run the school-administrator digest at **3:30 PM Friday in the school-local `America/Chicago` timezone**. The 90-minute interval provides teachers a courtesy reminder window before the administrator snapshot.

The email contains aggregate operational counts only:

- current-week teachers fully complete / expected;
- current-week completed packets submitted / expected;
- following-week teachers fully planned / expected;
- following-week lesson plans submitted / expected; and
- PLC brief availability.

Teacher names and class-level exceptions remain in authenticated TPP and are not placed in the administrator email.

### Manual email control

The normal administrator-facing `Weekly admin email` action is removed from the product UI once the scheduled design is adopted. Email delivery is infrastructure behavior, not an administrator task.

A manual delivery/recovery path may be retained only as controlled operational support. It must not become a routine duplicate-send control available in the normal administrator workflow.

## Delivery and persistence boundary

The scheduled worker remains isolated from the interactive web task and may use the Supabase service-role credential only in that isolated runtime. The interactive task must never receive that credential.

The delivery ledger stores only professional profile identifiers, week, notification key, status, and timestamps necessary for at-most-once delivery. It does **not** persist recipient email, teacher/course reminder lists, message bodies, reflection text, lesson-plan content, student data, generated insight, or SES message identifiers.

Teacher course names and missing-item flags may exist transiently in the service-role candidate manifest and email body because they are necessary to make the reminder actionable. They are not added to the delivery ledger.

## Release sequencing

The Friday dashboard/status source is intentionally separated from automatic email delivery:

1. `20260815011000_friday_submission_status.sql` may be reviewed, applied, and deployed with the authenticated dashboards while SES remains fail-closed.
2. `20260815013000_scheduled_friday_notifications.sql` remains deferred until the approved SES sender, service-role secret, least-privilege IAM, Help/privacy review, and exact 2:00 PM / 3:30 PM schedules are ready for explicit activation.
3. The activation workflow stages both schedules disabled, verifies immutable image/commands/secrets/times, and only then enables both. It does not send an immediate test email.

## Governance interpretation

This feature is administrative/professional operational reporting within TPP's existing educator-data boundary. It is not student analytics and does not change the prohibition on student PII or student education records.

Submission status is a workflow state. It must not be presented or reused as a proxy for teacher effectiveness, instructional quality, professionalism, or personnel evaluation.
