# Teacher Planning Platform — Repository Development Instructions

These instructions apply to all development, review, debugging, release, infrastructure, database, AI, authentication, logging, analytics, export, and UI work in this repository.

## Mandatory governance read

Before changing behavior that can affect user data, AI processing, authentication/authorization, logging, retention, exports, standards provenance, third-party integrations, or public claims, read and comply with:

- `docs/governance/LEGAL_COMPLIANCE_REQUIREMENTS.md`
- `docs/governance/LEGAL_COMPLIANCE_RELEASE_CHECKLIST.md`
- relevant canonical documents in `docs/legal/`

## Non-negotiable data boundary

TPP is an adult educator/administrator productivity service. Teacher/admin account data and professional curriculum, standards, schedule, lesson-planning, validation, reporting, export, and related operational data are permitted.

**Student personally identifiable information and student education records are not permitted.** Do not add student accounts, rosters, grades, identifiable student work, IEP/504 data, health/discipline data, or student-level analytics without an explicit, separately approved governance/legal architecture change.

## Conflict rule

If a task, issue, PR description, chat instruction, old document, or implementation request conflicts with the mandatory governance documents, do not silently weaken the governance rule. Surface the conflict and require explicit approval before changing the legal/compliance boundary.

## AI rule

AI output is teacher-reviewable draft assistance. Authoritative standards text is deterministic governed source content, not generative AI output. AI may not silently overwrite teacher-approved planning content, fabricate authoritative standards, or receive prohibited student data.

## Change review trigger

Treat the following as legal/compliance-impacting changes: new data categories; new user types; minors/student access; integrations/subprocessors; auth changes; AI provider/model/data-sharing changes; analytics/session replay; retention/deletion/backups; admin reporting scope; public privacy/security/accessibility/accuracy claims; payment processing; support tooling receiving customer content; or new customer jurisdictions.

Any such change must update or explicitly confirm the affected governance/legal documentation before release.
