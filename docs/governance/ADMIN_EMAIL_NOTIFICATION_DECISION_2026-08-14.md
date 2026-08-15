# Admin Email Notification Decision — Historical Foundation / Current Friday Use

**Original date:** 2026-08-14  
**Reconciled:** 2026-08-15  
**Status:** Original manual-admin notification decision retained as recovery foundation; normal UI and automatic cadence are governed by the August 15 Friday decision  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Superseding product decision

This file originally approved the first fail-closed, administrator-requested weekly digest. The normal product workflow has since been simplified. Current teacher/admin Friday status, recipient logic, and automatic schedule are governed by:

`docs/governance/FRIDAY_STATUS_NOTIFICATION_DECISION_2026-08-15.md`.

The normal administrator UI no longer mounts the manual `Weekly admin email` action. The existing authenticated manual endpoint/code may remain only as controlled operational recovery while the automatic path is introduced; it is not the primary administrator workflow.

## Approved sender identity

The approved TPP notification From address remains exactly:

`notifications@planner.guidedscholar.ai`

Application code must reject a different configured From address. The runtime sender remains blank until the approved identity is verified in AWS SES and the controlled ECS IAM/deployment configuration is completed. Recording this address does not activate email delivery.

## Original/manual recovery contract

The retained manual recovery path, if invoked through controlled support, sends only to the authenticated requesting administrator's own governed TPP professional email account. A client does not supply an arbitrary recipient address.

Its historical minimized content is limited to school operational counts and an authenticated TPP link. It must not contain student data, teacher reflection text, AI-generated instructional insight, teacher names or teacher-level exception lists, teacher-quality/performance judgments, secrets, tokens, internal identifiers, or provider response bodies.

This recovery contract does not define the normal Friday administrator experience and must not be used to bypass automatic-delivery at-most-once controls.

## Current automatic Friday contract

The approved Anniston Pilot sequence is:

- Friday 2:00 PM `America/Chicago`: one teacher courtesy reminder only when a required current-week reflection/completed packet or following-week lesson plan remains unsubmitted. The email names the exact professional class/course for each missing item so the teacher does not have to inspect every class.
- Friday 3:30 PM `America/Chicago`: an aggregate school-administrator digest with current-week closeout and following-week lesson-plan counts plus an authenticated TPP link. Teacher/class exceptions remain inside authenticated reporting.

The teacher courtesy email may include teacher display name and professional course name as transient delivery data necessary to make the reminder actionable. It must not include reflection text, lesson-plan content, student information, generated instructional insight, teacher rankings, or quality/performance/effort/productivity judgments.

The administrator email remains aggregate and must not include teacher names or class-level exception lists.

## Delivery architecture

SES delivery uses AWS task-role permission rather than static AWS credentials. Automatic Friday delivery uses isolated short-lived ECS tasks, not the interactive web task. The interactive web task must never receive the Supabase service-role key for scheduler convenience.

The scheduled worker's database access is limited to purpose-built service-role-only candidate functions. The delivery ledger stores only bounded professional identifiers, notification key, week, status, and timestamps needed for at-most-once delivery. It does not retain recipient email, course/class reminder lists, email body, reflection text, lesson-plan content, student data, generated insight, or SES MessageId.

## Activation boundary

SES and automatic delivery remain fail-closed unless the controlled release prerequisites are complete. These include:

1. verified/accepted `notifications@planner.guidedscholar.ai` or an approved parent-domain SES identity covering that exact address in `us-east-2`;
2. intended-recipient sending status permitted by the SES account;
3. least-privilege SES IAM using the approved identity;
4. privacy/subprocessor and Help reconciliation;
5. the Friday scheduled-delivery migration explicitly applied;
6. the isolated Supabase service-role secret stored through the approved AWS secret path;
7. live deployment-role policies reconciled to accepted source;
8. exact teacher/admin schedule expressions and `America/Chicago` verified; and
9. execution of the controlled Friday-notification activation workflow.

The activation workflow stages both schedules disabled, verifies them, and only then enables them. It does not invoke the workers immediately and sends no immediate/test email.

## Telemetry and tracking

The historical manual path may record the content-free event `admin_weekly_digest_sent`. Automatic scheduled-admin delivery may be counted through its bounded delivery ledger for Platform Owner adoption reporting. Teacher courtesy reminders are operational reminders and should not be repurposed as staff-performance analytics.

TPP does not persist email bodies or SES MessageIds in notification telemetry. The design does not add SES engagement tracking, tracking pixels, click/open tracking, advertising technology, or behavioral email analytics. Any such expansion requires separate privacy/governance review.

## Current source of truth

For release/activation decisions, use the August 15 Friday decision and the reconciled controlled release runbook. Git history preserves the original August 14 manual-admin design for provenance.
