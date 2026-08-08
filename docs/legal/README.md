# Teacher Planning Platform — Legal & Compliance Packet

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Not Yet Effective  
**Baseline date:** 2026-08-08

This directory is the canonical repository location for the Teacher Planning Platform (TPP) pre-release legal, privacy, security, and governance packet. These documents are drafted for an adult educator/administrator service and the locked TPP data boundary: teacher, administrator, curriculum, standards, scheduling, lesson-planning, validation, export, and related professional data only. TPP is not designed to collect, store, or process student personally identifiable information or student education records.

## External / customer-facing drafts

1. `TERMS_OF_USE.md`
2. `PRIVACY_POLICY.md`
3. `ACCEPTABLE_USE_POLICY.md`
4. `AI_USE_AND_ACCURACY_NOTICE.md`
5. `INSTITUTIONAL_SERVICES_AGREEMENT.md`
6. `SECURITY_AND_DATA_PRACTICES.md`
7. `SUBPROCESSORS.md`
8. `ACCESSIBILITY_STATEMENT.md`

## Internal governance documents

9. `DATA_RETENTION_AND_DELETION_POLICY.md`
10. `INCIDENT_RESPONSE_POLICY.md`
11. `../governance/LEGAL_COMPLIANCE_REQUIREMENTS.md`
12. `../governance/LEGAL_COMPLIANCE_RELEASE_CHECKLIST.md`

## Control rules

- Git history is the authoritative version history for these files.
- No document becomes effective or public merely because it is merged.
- Before publication, the packet must be reconciled against the deployed application, database, AI request path, authentication, logging, exports, infrastructure, account lifecycle, and vendor configuration.
- Material legal conclusions, statutory requirements, limitation-of-liability language, indemnities, dispute provisions, and customer-contract terms require qualified legal review before final publication.
- Any code, infrastructure, database, logging, analytics, AI, authentication, or UI change that conflicts with `docs/governance/LEGAL_COMPLIANCE_REQUIREMENTS.md` is a governance change and requires explicit approval plus corresponding document review.

## Known publication blockers

The pre-release drafts intentionally do not invent unresolved business details. Before publication, Brau Consulting LLC must approve and supply or confirm: public legal/privacy contact address and email; effective date; commercial/payment terms where applicable; final institutional contracting approach; final retention/deletion implementation; final production subprocessor configuration; and final dispute-resolution/venue language after legal review.
