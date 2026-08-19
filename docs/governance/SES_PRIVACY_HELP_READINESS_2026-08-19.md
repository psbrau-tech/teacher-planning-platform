# TPP SES Privacy, Subprocessor, and Help Readiness Review

**Date:** 2026-08-19  
**Status:** Controlled pilot email-flow review complete; legal publication/effectiveness remains a separate gate  
**Scope:** Teacher Planning Platform (TPP), Amazon SES `us-east-2`

## Purpose

This record documents the factual review required before the controlled **Enable TPP SES Notifications** workflow may be run with `privacy_help_review_confirmed=true`.

This review does **not** make any customer-facing legal document effective, publish the legal packet, constitute legal advice, or replace qualified legal review. The customer-facing legal documents retain their existing Pre-Release Draft / Not Yet Effective status until separately approved and published.

## Exact governed email flow reviewed

The reviewed TPP professional operational email flow is:

- application From address: `notifications@planner.guidedscholar.ai`;
- monitored Reply-To address: `peter@brauconsulting.com`;
- Amazon SES Region: `us-east-2`;
- teacher courtesy reminder: one school-scoped reminder only when a required Friday item remains outstanding;
- teacher reminder content: professional class/course name plus whether the missing item is the current-week reflection/completed packet, the following-week lesson plan, or both;
- school-administrator digest: aggregate school operational submission counts plus an authenticated TPP link;
- administrator email excludes teacher names, class-level exception lists, reflection text, lesson-plan content, generated instructional insight, student information, and teacher-quality/performance scoring;
- email does not expand district/platform reporting or notification-recipient scope;
- student PII, student education records, identifiable student work, grades/assessment results, IEP/504, health/discipline information, and other student-specific information remain prohibited.

## SES provider and feedback-control evidence

Operator/provider evidence reported on 2026-08-19 establishes:

- `planner.guidedscholar.ai` SES identity verified;
- Easy DKIM successful and enabled;
- AWS production sending access approved in `us-east-2` and the account moved out of the SES sandbox;
- account-level SES suppression enabled for both `BOUNCE` and `COMPLAINT`;
- dedicated SNS topic `tpp-pilot-ses-feedback` configured in `us-east-2`;
- monitored SNS email subscription confirmed;
- SES Bounce and Complaint feedback both routed to that topic;
- SES Email Feedback Forwarding disabled after the SNS paths were established; and
- Amazon SES mailbox-simulator Bounce and Complaint events were both received through the monitored SNS path.

No notification payloads, recipient lists, or customer content are copied into this release evidence.

## Privacy Policy review

`docs/legal/PRIVACY_POLICY.md` was reviewed against the exact enabled-flow design.

The draft already covers the material customer-facing data categories for professional operational email:

- recipient professional account email address;
- minimized operational notification content;
- aggregate school-administrator status counts;
- bounded notification-delivery metadata;
- the prohibition on student data, reflection text, lesson-plan content, generated instructional insight, and teacher-performance content in administrator email; and
- the design choice that the TPP automatic-delivery ledger does not persist recipient email address, email body, reflection/lesson-plan content, or SES MessageId.

The provider-side SES suppression/SNS feedback controls do not change the TPP application data boundary. AWS may necessarily process the professional destination address and delivery/feedback event metadata to deliver mail, identify bounces/complaints, and maintain suppression. This is part of the AWS professional-email delivery purpose already identified in the Subprocessor List and does not mean the TPP application delivery ledger persists those provider records.

The Privacy Policy remains **Pre-Release Draft — Not Yet Effective**. This controlled review is sufficient only for the pilot infrastructure activation acknowledgement; public policy effectiveness remains separately governed.

## Subprocessor review

Amazon Web Services is already identified as the provider for application hosting and professional operational email delivery. The Subprocessor List must distinguish provider readiness from TPP application activation:

- SES identity/DKIM and production sending access are now provider-ready;
- bounce/complaint suppression and monitored SNS feedback controls are operational;
- TPP application SES sending remains inactive until the controlled SES activation workflow succeeds; and
- the Friday scheduler/isolated worker remains a separate later activation.

The legal Subprocessor List remains a Pre-Release Draft and still requires the broader final verification items identified in that document before publication.

## In-product Help review

`frontend/src/HelpPage.tsx` was reviewed against the exact email implementation.

Help accurately states that:

- email is a separately governed infrastructure feature;
- teacher reminders are limited to missing professional Friday submission items;
- school-administrator email contains aggregate counts and an authenticated TPP link;
- prohibited content is excluded from email;
- named operational follow-up remains inside authenticated TPP;
- the approved From address is `notifications@planner.guidedscholar.ai`;
- notifications are activated only through controlled release; and
- notification status is not a teacher-performance measure.

The approved Reply-To is governed in application configuration and routes normal recipient replies to `peter@brauconsulting.com`. The absence of a mailbox on the send-only From address does not change the Help-described notification content or authorization boundary.

## Activation-gate conclusion

For the narrow purpose of the **Enable TPP SES Notifications** workflow, the factual privacy/subprocessor + Help review for this email data flow is complete and may be represented as:

`privacy_help_review_confirmed=true`

This conclusion does **not** mean:

- the Privacy Policy, Subprocessor List, Terms, Security & Data Practices, or other legal document is final/effective;
- qualified legal review has been completed;
- public publication blockers are resolved;
- scheduled Friday notifications are enabled; or
- any school notification flag is enabled.

## Remaining separate gates

After this review record is accepted:

1. run the controlled **Enable TPP SES Notifications** workflow;
2. verify the immutable application image and exact runtime secret set are preserved;
3. perform a bounded authenticated application-delivery acceptance test;
4. provision/verify the isolated scheduled-worker service-role secret and school notification configuration;
5. separately activate the Friday dispatchers only after their own governed gate; and
6. keep legal publication/effectiveness under the existing owner/qualified-counsel process.
