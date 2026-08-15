# SES Notification Infrastructure Decision

**Date:** 2026-08-14  
**Status:** Infrastructure prepared; activation remains a manual controlled release action  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Approved sender

The approved TPP notification From address is:

`notifications@planner.guidedscholar.ai`

The application code, infrastructure activation workflow, and release checks must reject or refuse activation for a different From address.

## Default state

SES delivery remains disabled by default.

The CloudFormation parameters `SesFromEmail` and `SesIdentityArn` both default to an empty string. The ECS task role receives no SES send policy unless both parameters are nonblank. The runtime `TPP_SES_FROM_EMAIL` therefore remains blank until a controlled activation updates the stack.

This means merging or deploying application code alone does not activate email delivery.

## Least-privilege task permission

When activation is approved, CloudFormation may attach a task-role policy that grants only:

`ses:SendEmail`

to the single verified SES identity ARN supplied during activation. The policy is attached to the ECS application task role; no static AWS access key is introduced.

The identity ARN is restricted by the activation workflow to either:

- `arn:aws:ses:us-east-2:697091778129:identity/notifications@planner.guidedscholar.ai`; or
- `arn:aws:ses:us-east-2:697091778129:identity/planner.guidedscholar.ai`.

The application still enforces the exact approved From address even when a verified domain identity is used.

## Controlled activation workflow

`.github/workflows/enable-ses-notifications.yml` is the only new activation path introduced by this slice.

It requires explicit confirmation that:

1. the SES identity is verified in `us-east-2`;
2. the SES account is permitted to send to the intended professional recipients; and
3. privacy/subprocessor and Help review for the enabled email data flow are complete.

The workflow then updates only the SES CloudFormation parameters. Existing stack parameter values, immutable application image, runtime secret set, school data boundary, and ECS service configuration must remain otherwise unchanged.

The workflow does **not** send a test email. A separate governed application-level delivery test should occur only after the infrastructure activation is accepted.

## Existing deployment workflows

Normal CloudFormation updates do not need to restate the SES parameters once activated. The AWS CLI `cloudformation deploy` update behavior retains an existing stack parameter value when that parameter is not supplied in `--parameter-overrides`.

This is important because the existing deploy, bootstrap, and TLS workflows must not silently replace an activated SES identity with a template default during later stack updates.

A new stack remains fail-closed because both SES parameters have blank template defaults.

## Data boundary

The SES infrastructure does not expand TPP's data boundary. Email remains limited to adult professional operational communication. Student PII, student education records, identifiable student work, student assessment results, reflection text, generated instructional insight, and teacher-quality/performance content remain prohibited from the first-release admin digest.

## Still required before activation

The following are deliberate human/release gates and are not satisfied by this code change:

- verify the approved email or domain identity in AWS SES `us-east-2`;
- complete any DNS records required by SES verification;
- confirm SES sending access for intended recipients;
- reconcile the enabled SES data flow with the final privacy policy/subprocessor disclosures and Help text;
- run the controlled SES activation workflow against an accepted release candidate; and
- perform a bounded authenticated admin delivery test after activation.

No SES activation or production/pilot email delivery is authorized merely by merging this infrastructure slice.
