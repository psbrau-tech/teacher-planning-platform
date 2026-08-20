# TPP Post-Pilot Legal / Compliance Reconciliation — 2026-08-20

**Provider:** Brau Consulting LLC  
**Status:** Internal reconciliation record  
**Accepted application SHA:** `b33bf905e98012b857c4434039fced08ff89137b`  
**Applied migration head:** `20260820020000`

## Scope

This record reconciles the legal/compliance packet against the live-accepted Pilot baseline recorded
in `../governance/PILOT_BASELINE_2026-08-20.md`. It supplements rather than replaces the broader
2026-08-13 reconciliation.

The reviewed release changes are limited to:

- displaying scheduled class duration and ordering class cards by start time;
- treating each curriculum pacing row as one class day and retiring the optional minute override;
- restoring governed AI usage-event logging; and
- restoring explicit teacher accept/edit/reject decision recording so accepted or edited AI
  planning text can enter and persist in the saved weekly plan.

## Governance conclusion

No legal/compliance boundary expansion was identified. This release does not add:

- a new data category;
- student accounts, student PII, or student education records;
- a new user type or broader administrator reporting scope;
- a new AI provider, model-training opt-in, or AI data-sharing purpose;
- a new subprocessor or integration;
- a new analytics, logging, retention, deletion, or export category; or
- a new public privacy, security, accessibility, or accuracy claim.

The existing customer-facing drafts therefore do not require substantive policy or contract changes
for this release. They remain pre-release drafts subject to the unresolved publication decisions and
qualified legal review already recorded in the packet.

## AI human-control reconciliation

The accepted implementation matches the packet's human-control requirement:

1. AI planning output is returned as a draft.
2. The teacher explicitly accepts, edits, or rejects each suggestion, or uses the governed bulk
   action that records the corresponding field decisions.
3. The decision record is tied to a successful AI usage event and the authenticated teacher's
   teaching assignment.
4. Accepted or edited text enters the working plan only after the decision operation succeeds.
5. The teacher separately saves the weekly plan.
6. Live acceptance confirmed that the accepted text remains present after reopening the saved week.

The repair preserves the teacher-role check, authenticated actor identity, assignment ownership,
allowed decision values, allowed planning fields, and audit event. It does not weaken row-level
security or allow AI to overwrite teacher-approved content silently.

## Pacing and instructional-time reconciliation

The pacing correction changes product interpretation, not the data boundary. Each pacing row now
represents one instructional class day. The existing professional course schedule supplies the
available minutes for that date. Historical minute values remain readable for compatibility but no
longer split, combine, suppress, or extend lessons.

The optional minute field was removed from the editor, blank template, import review, and export.
No new retained field or content category was introduced.

## Notification-state clarification

The accepted migration head includes the source-controlled professional-notification schema. Schema
application does not establish that SES application sending or the isolated Friday dispatchers are
active. Email/scheduler activation remains subject to the separate controlled workflows, provider
controls, privacy/Help checks, professional-recipient limits, and school-local configuration already
documented in the governance packet.

## Documents reviewed

The following canonical documents were reviewed for impact:

- `TERMS_OF_USE.md`
- `PRIVACY_POLICY.md`
- `ACCEPTABLE_USE_POLICY.md`
- `AI_USE_AND_ACCURACY_NOTICE.md`
- `INSTITUTIONAL_SERVICES_AGREEMENT.md`
- `SECURITY_AND_DATA_PRACTICES.md`
- `SUBPROCESSORS.md`
- `ACCESSIBILITY_STATEMENT.md`
- `DATA_RETENTION_AND_DELETION_POLICY.md`
- `INCIDENT_RESPONSE_POLICY.md`
- `../governance/LEGAL_COMPLIANCE_REQUIREMENTS.md`
- `../governance/LEGAL_COMPLIANCE_RELEASE_CHECKLIST.md`

No substantive customer-facing amendment was required because the accepted behavior remains within
their existing descriptions and controls. The packet index, counsel implementation summary, lawyer
review order, deployment baseline, and this reconciliation record were updated for factual accuracy.

## Remaining publication blockers

This reconciliation does not resolve or alter the existing publication blockers, including final
contact/address decisions, effective dates, commercial terms, end-to-end retention/deletion
commitments, provider account/DPA verification, incident contacts, WCAG 2.1 Level AA evidence, and
qualified counsel review of liability, indemnity, disputes, and public-school contracting terms.

## Decision

**PASS —** the 2026-08-20 live-accepted Pilot baseline is materially consistent with the existing
TPP legal/privacy/security architecture. No release-specific legal/compliance defect remains open.
