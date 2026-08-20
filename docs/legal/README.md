# Teacher Planning Platform — Legal & Compliance Packet

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Not Yet Effective  
**Original governance baseline:** 2026-08-08  
**Latest post-pilot reconciliation:** 2026-08-20

This directory is the canonical repository location for the Teacher Planning Platform (TPP) legal, privacy, security, accessibility, and governance packet. The packet has been reconciled against the deployed controlled pilot and remains pre-release pending Brau Consulting review, qualified legal review, final publication decisions, and release-gate verification.

TPP is an adult educator/administrator productivity service. Its locked data boundary permits educator/administrator account information and professional curriculum, standards, scheduling, lesson-planning, validation, reflection, reporting, export, product-usage, and related operational data. TPP is not designed to collect, store, or process student personally identifiable information or student education records.

## External / customer-facing drafts

1. `TERMS_OF_USE.md`
2. `PRIVACY_POLICY.md`
3. `ACCEPTABLE_USE_POLICY.md`
4. `AI_USE_AND_ACCURACY_NOTICE.md`
5. `INSTITUTIONAL_SERVICES_AGREEMENT.md`
6. `SECURITY_AND_DATA_PRACTICES.md`
7. `SUBPROCESSORS.md`
8. `ACCESSIBILITY_STATEMENT.md`

## Internal governance, reconciliation, and research documents

9. `DATA_RETENTION_AND_DELETION_POLICY.md`
10. `INCIDENT_RESPONSE_POLICY.md`
11. `LEGAL_RESEARCH_NOTES.md`
12. `DECISIONS_REQUIRED_BEFORE_PUBLICATION.md`
13. `POST_PILOT_RECONCILIATION_2026-08-13.md`
14. `POST_PILOT_RECONCILIATION_2026-08-20.md`
15. `COUNSEL_REVIEW_BRIEF_2026-08-13.md`
16. `../governance/PILOT_BASELINE_2026-08-20.md`
17. `../governance/LEGAL_COMPLIANCE_REQUIREMENTS.md`
18. `../governance/LEGAL_COMPLIANCE_RELEASE_CHECKLIST.md`
19. `../governance/PRODUCT_ANALYTICS_DECISION_2026-08-13.md`

Repository-level `../../AGENTS.md` makes the legal/compliance governance documents mandatory context for future development work.

## Deployed pilot facts incorporated in the reconciliation

As of the 2026-08-20 reconciliation, the repository and controlled-pilot implementation establish the following material facts:

- application hosting on AWS in `us-east-2` using ECS/Fargate behind an Application Load Balancer;
- HTTPS/TLS support on the controlled pilot endpoint;
- immutable Amazon ECR images with image scanning;
- AWS Secrets Manager/protected configuration for runtime secrets, including the OpenAI API credential;
- Amazon CloudWatch application logging with a verified 30-day application-log retention setting;
- Supabase-backed database/authentication and role/authorization records;
- teacher-invoked OpenAI generative-AI planning assistance with educator review/decision controls and bounded usage metadata;
- live-accepted teacher accept/edit/reject and weekly-plan persistence for AI planning suggestions;
- daily pacing in which one pacing lesson represents one class day and the saved schedule supplies that date's instructional minutes;
- governed authoritative standards ingestion, provenance, snapshots, reconciliation, course mapping, and administration;
- teacher, school-administrator, district-administrator, and Platform Owner role/reporting functionality within the no-student-data boundary;
- weekly planning, validation/reflection, weekly/completed-packet submission, and PDF/other planning export workflows;
- approved first-party active-interaction telemetry for bounded product-effectiveness measurement, with duration reporting restricted to the Platform Owner and excluded from ordinary school/district administrator reporting.

These implementation facts do not make the customer-facing documents legally effective and do not replace final vendor/configuration verification where the packet expressly calls for it.

## Control rules

- Git history is the authoritative version history for these files.
- No document becomes effective or public merely because it is merged.
- The packet must continue to be reconciled against deployed application behavior, database schema, AI request paths, authentication/authorization, logging and telemetry, exports, infrastructure, account lifecycle, accessibility evidence, and vendor configuration before publication and after material changes.
- Material legal conclusions, statutory requirements, limitation-of-liability language, indemnities, dispute provisions, accessibility obligations, and customer-contract terms require qualified legal review before final publication.
- Any code, infrastructure, database, logging, analytics, AI, authentication, accessibility, reporting, or UI change that conflicts with `docs/governance/LEGAL_COMPLIANCE_REQUIREMENTS.md` is a governance change and requires explicit approval plus corresponding document review.

## Remaining publication blockers

The post-pilot reconciliation resolves several architecture/feature uncertainties but intentionally does not invent unresolved legal or business terms. Before publication, Brau Consulting LLC must approve or confirm:

- public legal/privacy/security/support/accessibility contact information;
- public business mailing address;
- effective dates;
- commercial/payment/renewal terms where applicable;
- final institutional contracting approach;
- numerical retention/deletion and post-termination schedules beyond verified application-log retention;
- final Supabase project region, backup/restore retention, and relevant contractual posture;
- production OpenAI data-control/account configuration and current contract/DPA posture;
- any additional production vendors that routinely process personal/customer content;
- designated incident contacts;
- accessibility evidence against the applicable WCAG 2.1 Level AA baseline;
- final dispute-resolution, venue, warranty, liability, and indemnity language after qualified legal review.

See `DECISIONS_REQUIRED_BEFORE_PUBLICATION.md` for the controlled decision register,
`POST_PILOT_RECONCILIATION_2026-08-20.md` for the latest implementation reconciliation, and
`COUNSEL_REVIEW_BRIEF_2026-08-13.md` for the recommended counsel handoff.
