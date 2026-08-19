# TPP SES Feedback Controls Runbook

**Date:** 2026-08-19  
**Status:** Required provider configuration before TPP SES activation  
**Scope:** Teacher Planning Platform controlled pilot, Amazon SES `us-east-2`

## Purpose

Amazon SES production access is approved for the TPP AWS account in `us-east-2`. TPP application sending remains disabled until bounce and complaint handling is operational.

This runbook defines the minimum feedback controls required before the **Enable TPP SES Notifications** workflow may be run with `feedback_controls_confirmed=true`.

These controls do not expand the TPP data boundary and do not activate the Friday notification schedulers.

## Locked delivery identity

- Verified SES domain identity: `planner.guidedscholar.ai`
- Application From address: `notifications@planner.guidedscholar.ai`
- Monitored application Reply-To: `peter@brauconsulting.com`
- AWS Region: `us-east-2`

TPP intentionally does not require an inbound mailbox for `notifications@planner.guidedscholar.ai`. Because SES bounce/complaint feedback must still be monitored, feedback is routed through Amazon SNS rather than relying on email feedback forwarding to the send-only From address.

## Required control 1 — account-level suppression

In the Amazon SES console in **US East (Ohio) / `us-east-2`**:

1. Open **Configuration → Suppression list**.
2. Edit the account-level suppression settings.
3. Enable the account-level suppression list.
4. Select both reasons:
   - `BOUNCE`
   - `COMPLAINT`
5. Save the setting.

Required acceptance evidence: the account-level suppression configuration shows both `BOUNCE` and `COMPLAINT` enabled.

A hard bounce or complaint must therefore cause the affected destination to be added to the SES account-level suppression list rather than being repeatedly retried by later TPP sends.

## Required control 2 — monitored SNS feedback topic

In Amazon SNS in **`us-east-2`**:

1. Create one standard topic dedicated to TPP SES feedback, using the name:
   - `tpp-pilot-ses-feedback`
2. Create an **Email** subscription to:
   - `peter@brauconsulting.com`
3. Open the AWS subscription-confirmation email in that mailbox and choose **Confirm subscription**.
4. Return to SNS and verify the subscription status is confirmed rather than `PendingConfirmation`.

Do not use a student, teacher, school, or customer address as the operational subscription endpoint.

Required acceptance evidence: the dedicated topic exists in `us-east-2` and the `peter@brauconsulting.com` subscription is confirmed.

## Required control 3 — bind SES bounce and complaint notifications to SNS

In Amazon SES in **`us-east-2`**:

1. Open **Configuration → Identities**.
2. Select the verified identity `planner.guidedscholar.ai`.
3. Open the **Notifications** tab and edit **Feedback notifications**.
4. For **Bounce feedback**, choose the `tpp-pilot-ses-feedback` SNS topic.
5. For **Complaint feedback**, choose the same `tpp-pilot-ses-feedback` SNS topic.
6. Delivery notifications are not required for this first controlled release.
7. Do **not** include original email headers in the SNS notifications unless a later reviewed operational need explicitly requires them.
8. Save the changes and verify both bounce and complaint feedback show the dedicated SNS topic.

The domain-level setting applies to mail sent from addresses in the verified domain unless an individual email identity has its own notification configuration.

Required acceptance evidence: both Bounce and Complaint feedback for `planner.guidedscholar.ai` point to the dedicated SNS topic.

## Required control 4 — email feedback forwarding

After both Bounce and Complaint SNS topics are configured and the SNS subscription is confirmed, disable SES **Email Feedback Forwarding** for `planner.guidedscholar.ai`.

Reason: `notifications@planner.guidedscholar.ai` is a send-only application identity and does not have an inbound mailbox. SNS is the governed monitored feedback channel. Leaving email feedback forwarding enabled would create a duplicate or unmonitored feedback path.

Do not disable email feedback forwarding unless SNS is configured for **both** Bounce and Complaint feedback.

## Optional defense in depth — CloudWatch reputation alarms

Amazon SES publishes account reputation metrics to CloudWatch. Before material expansion beyond the controlled pilot, create alarms to the same monitored SNS topic using AWS's published warning thresholds:

- bounce-rate alarm at `>= 0.05` (5%);
- complaint-rate alarm at `>= 0.001` (0.1%);
- treat missing data as ignore/maintain current state.

These alarms are defense in depth; the required first-release controls are the account-level suppression list plus direct SNS bounce/complaint notifications.

## Operational response

When a TPP SES bounce or complaint notification arrives:

1. Do not forward the provider notification outside the operational owner path.
2. Do not copy notification payloads into ordinary support tickets or chat if a bounded identifier/status is sufficient.
3. Confirm the destination is suppressed when the event qualifies for account-level suppression.
4. Treat complaints as a stop-sending signal for that recipient until the recipient's professional account and notification authorization are reviewed.
5. Treat repeated hard-bounce patterns or any unexpected complaint as an operational incident and pause the affected school notification flag or the global SES activation if necessary.
6. Never use bounce/complaint information as teacher-performance or employment-evaluation data.

## Activation gate

Only after all four required controls above are complete may the **Enable TPP SES Notifications** workflow be run with:

`feedback_controls_confirmed=true`

That workflow still:

- sends no test email;
- does not enable the Friday schedulers;
- preserves the accepted immutable application image;
- grants only the existing identity-scoped `ses:SendEmail` application permission; and
- keeps the TPP no-student-data boundary unchanged.

## First bounded test after SES activation

After SES infrastructure activation is verified, use the Amazon SES mailbox simulator for the first bounded bounce/complaint-path validation where appropriate. Simulator testing is preferred over intentionally sending to invalid or complaint-prone real addresses.

Routine school notifications remain disabled until their separate school-configuration and Friday-scheduler activation gates are intentionally opened.

## Authoritative AWS references

- Amazon SES account-level suppression list documentation
- Amazon SES feedback notifications through Amazon SNS
- Amazon SES identity notification configuration
- Amazon SES email feedback forwarding documentation
- Amazon SES CloudWatch reputation alarm documentation

Provider console labels can change. If the current AWS console differs from this runbook, use the current AWS documentation and preserve the controls described here rather than guessing from stale UI labels.
