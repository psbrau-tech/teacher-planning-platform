# SES Notification Infrastructure Decision

**Original date:** 2026-08-14  
**Reconciled:** 2026-08-19  
**Status:** SES production access approved; application activation remains a manual controlled release action  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Approved delivery addresses

The approved TPP notification From address is:

`notifications@planner.guidedscholar.ai`

The approved monitored Reply-To address is:

`peter@brauconsulting.com`

The application delivery path must reject a different From or Reply-To address. The Reply-To address is non-secret governed configuration and does not authorize or activate SES sending.

## Default state

SES delivery remains disabled by default.

The CloudFormation parameters `SesFromEmail` and `SesIdentityArn` both default to an empty string. The ECS task role receives no SES send policy unless both parameters are nonblank. The runtime `TPP_SES_FROM_EMAIL` therefore remains blank until a controlled activation updates the stack.

The application carries the approved Reply-To as a non-secret default, but cannot send while the From address remains blank. This means merging or deploying application code alone does not activate email delivery.

## Least-privilege task permission

When activation is approved, CloudFormation may attach a task-role policy that grants only:

`ses:SendEmail`

to the single verified SES identity ARN supplied during activation. The policy is attached to the ECS application task role; no static AWS access key is introduced.

The identity ARN is restricted by the activation workflow to either:

- `arn:aws:ses:us-east-2:697091778129:identity/notifications@planner.guidedscholar.ai`; or
- `arn:aws:ses:us-east-2:697091778129:identity/planner.guidedscholar.ai`.

The application still enforces the exact approved From and Reply-To addresses even when a verified domain identity is used.

## Controlled activation workflow

`.github/workflows/enable-ses-notifications.yml` remains the controlled activation path.

It requires explicit confirmation that:

1. the SES identity is verified in `us-east-2`;
2. the SES account is out of the sandbox and permitted to send to the intended professional recipients;
3. account-level suppression for both `BOUNCE` and `COMPLAINT` is enabled and monitored bounce/complaint notifications are operational; and
4. privacy/subprocessor and Help review for the enabled email data flow are complete.

The workflow then updates only the SES CloudFormation parameters. Existing stack parameter values, immutable application image, runtime secret set, school data boundary, and ECS service configuration must remain otherwise unchanged.

The workflow does not send a test email. A separate governed application-level delivery test should occur only after the infrastructure activation is accepted.

## Existing deployment workflows

Normal CloudFormation updates do not need to restate the SES parameters once activated. The AWS CLI `cloudformation deploy` update behavior retains an existing stack parameter value when that parameter is not supplied in `--parameter-overrides`.

This is important because the existing deploy, bootstrap, and TLS workflows must not silently replace an activated SES identity with a template default during later stack updates.

A new stack remains fail-closed because both SES parameters have blank template defaults.

## Current provider readiness

As of the 2026-08-19 reconciliation:

- the SES domain identity `planner.guidedscholar.ai` is verified in `us-east-2`;
- DKIM is successful and enabled;
- the three SES DKIM CNAME records are present in the authoritative Route 53 hosted zone;
- AWS approved production sending access in `us-east-2` and moved the account out of the SES sandbox;
- AWS reported a sending quota of 50,000 messages per 24 hours and a maximum send rate of 14 messages per second; and
- TPP application SES sending remains disabled until the feedback-control and activation gates are complete.

The monitored reply path is explicitly `peter@brauconsulting.com`; no inbound mailbox on `planner.guidedscholar.ai` is required for recipient replies.

## Bounce, complaint, and suppression controls

TPP must not rely on the send-only From address as its feedback mailbox.

Before application SES activation:

- enable the SES account-level suppression list for both `BOUNCE` and `COMPLAINT`;
- create a dedicated `us-east-2` SNS topic for TPP SES feedback;
- subscribe `peter@brauconsulting.com` and confirm the subscription;
- configure the verified `planner.guidedscholar.ai` identity to publish both Bounce and Complaint feedback to that topic; and
- after both SNS feedback types are operational, disable duplicate email feedback forwarding for the identity because the send-only From address has no inbound mailbox.

The exact provider procedure and operational response are documented in `docs/governance/SES_FEEDBACK_CONTROLS_RUNBOOK_2026-08-19.md`.

The current GitHub deployment role is intentionally not expanded to mutate SES account settings, SNS subscriptions, or CloudWatch configuration merely to automate this provider setup. The activation workflow instead requires explicit confirmation that the feedback controls are operational. This preserves the existing least-privilege deployment boundary.

## Data boundary

The SES infrastructure does not expand TPP's data boundary. Email remains limited to adult professional operational communication. Student PII, student education records, identifiable student work, student assessment results, reflection text, generated instructional insight, and teacher-quality/performance content remain prohibited from notification email.

Bounce/complaint events are operational delivery signals only. They must not be used as teacher-quality, performance, or employment-evaluation data.

## Still required before activation

The following are deliberate human/release gates and are not satisfied merely by this source change:

- configure and verify the required SES suppression and SNS feedback controls;
- reconcile the enabled SES data flow with the privacy policy/subprocessor disclosures and Help text;
- run the controlled SES activation workflow against an accepted release candidate; and
- perform a bounded authenticated delivery test after activation, preferring the SES mailbox simulator where applicable.

No SES activation or production/pilot email delivery is authorized merely by merging this governance slice.
