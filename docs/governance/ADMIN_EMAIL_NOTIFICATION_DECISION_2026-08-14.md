# Admin Email Notification Decision — Weekly School Operations Digest

**Date:** 2026-08-14  
**Status:** Approved product direction; implementation may merge fail-closed before SES activation  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Approval context

Anniston High School leadership approved moving forward with the Reflection Intelligence analytics, email-notification layer, and PLC/faculty artifacts reviewed in the August 14 concept discussion.

This decision narrows the first email implementation to a deliberately minimized school-operations digest rather than putting teacher names or reflection content into email.

## First-release notification

An authorized school reporting administrator may explicitly request a weekly TPP admin digest for a selected Monday week.

The recipient is always the requesting administrator's own authenticated TPP professional email address. The client does not supply an arbitrary recipient address.

The email may include only:

- configured course-assignment count;
- lesson-plan submitted/missing counts;
- completed Friday packet submitted/missing counts;
- whether enough distinct completed-packet teacher sources exist to generate an aggregate school PLC brief; and
- a link back to authenticated TPP for details.

The email must not include:

- student data;
- teacher reflection text;
- AI-generated instructional insight text;
- teacher names or teacher-level exception lists;
- teacher quality scores, ratings, rankings, or performance judgments;
- secrets, tokens, internal identifiers, or provider response bodies.

Named teacher follow-up remains available only inside the authenticated operational reporting surface where it is already role-authorized.

## Delivery architecture

The application uses AWS SES through the ECS task role. No static AWS access key is introduced into application configuration.

SES delivery remains fail-closed unless all of the following are configured and verified:

1. an approved sender identity is verified in the production/pilot SES Region;
2. the runtime environment supplies the approved From address;
3. the ECS task role has least-privilege `ses:SendEmail` permission scoped to the approved SES identity where technically supported;
4. the SES account is allowed to send to the intended professional recipients;
5. current AWS terms/DPA/service settings and the TPP subprocessor/privacy disclosures are reconciled for the email data flow; and
6. the controlled deployment workflow is updated and reviewed before activation.

A blank sender configuration is the intended disabled state.

## Telemetry

TPP may record the content-free event `admin_weekly_digest_sent` with school, authenticated requesting professional, event key, and timestamp.

TPP does not persist the email body, recipient address, SES MessageId, teacher names, reflection text, or generated insight in notification telemetry.

## Automatic/scheduled email is deferred

This release does not create automatic Friday/Sunday scheduling, bulk recipient resolution, or cross-admin delivery.

A future scheduled notification service must use a separately governed execution path rather than expanding the main web application's database privilege. In particular, the main web application must not receive a Supabase service-role credential merely to support a scheduler.

Potential future notification types from the approved concept — individual missing-plan reminders, missing-packet reminders, potentially-minimal-reflection reminders, and custom reminders — require separate rule, recipient, frequency, suppression, and privacy review before activation.

## No engagement tracking

The first release does not use SES configuration sets, tracking pixels, click/open tracking, behavioral analytics, or advertising technology. Any such addition requires separate privacy/governance review.

## Release requirements

Before SES is enabled in the controlled pilot:

- verify sender identity and SES account sending status;
- verify the exact IAM policy and runtime From address;
- verify only the requesting admin can trigger delivery to their own governed account;
- verify the message contains counts plus the authenticated TPP link only;
- verify no student or reflection content enters the SES request;
- verify content-free notification telemetry only;
- reconcile `docs/legal/PRIVACY_POLICY.md` and `docs/legal/SUBPROCESSORS.md` to the enabled AWS SES data flow;
- review Help text against the exact release candidate; and
- retain exact commit/image/infrastructure evidence for deployment.
