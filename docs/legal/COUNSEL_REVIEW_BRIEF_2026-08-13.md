# Teacher Planning Platform — Counsel Review Brief

**Provider:** Brau Consulting LLC  
**Date:** 2026-08-13  
**Status:** Pre-publication legal-review brief

## Purpose of this brief

Brau Consulting LLC is preparing Teacher Planning Platform (TPP) for broader school/district use after deployment of a controlled pilot. This brief is intended to help counsel review the accompanying Terms of Use, Privacy Policy, Acceptable Use Policy, AI Use & Accuracy Notice, Institutional Services Agreement, Security & Data Practices overview, Subprocessor List, Accessibility Statement, and related internal governance documents efficiently.

The customer-facing documents are drafts only and are not yet legally effective.

## Product summary

TPP is an adult educator/administrator productivity and instructional-planning platform. It helps teachers organize curriculum and pacing, work with authoritative instructional standards, plan weekly instruction, validate/reflect on completed work, carry lessons forward when schedules change, submit completed planning packets, and generate school-required planning documents. Administrators have role-based visibility into permitted educator/professional operational information and reporting.

TPP also provides teacher-invoked generative-AI planning assistance. AI suggestions are drafts subject to educator review and control; the service is not designed to make autonomous instructional decisions.

## Locked data boundary

TPP is intentionally designed not to receive student personally identifiable information or student education records.

The prohibited-data boundary includes, among other things:

- student names or identifying initials;
- student IDs, usernames, email addresses, or contact information;
- identifiable grades, assessments, attendance, discipline, or interventions;
- IEP, Section 504, health, counseling, or special-education records;
- identifiable student work, media, portfolios, or assessments;
- student-level analytics or parent/guardian data linked to a student.

The service is not offered as a student information system, LMS, gradebook, special-education record system, or student work repository.

We would like counsel to confirm whether this boundary and the accompanying contractual language are sufficient to avoid unnecessarily structuring TPP as a student-record processor, while recognizing that accidental prohibited submissions must still be handled appropriately.

## Current controlled-pilot architecture

The deployed architecture presently includes:

- Amazon Web Services in `us-east-2`;
- ECS/Fargate application hosting behind an Application Load Balancer;
- HTTPS/TLS support;
- immutable/scanned ECR images;
- CloudWatch application logs configured for 30-day retention;
- AWS Secrets Manager/protected configuration for runtime secrets;
- Supabase for database/authentication-related platform services;
- OpenAI API/business services for teacher-invoked generative-AI assistance.

The application/database model includes role/authorization data, professional curriculum and planning records, governed standards/source provenance, AI usage/decision metadata, teacher validation/reflection/submission records, and permitted administrative reporting data.

## AI design

TPP uses OpenAI for teacher-invoked generative-AI assistance. AI may suggest learning targets, standards decomposition, instructional activities, assessments, resources, literacy/ACT connections where appropriate, reflection content, and related professional planning fields.

Important controls include:

- student data is prohibited from AI requests;
- authoritative standards text is ingested and governed separately from generative AI;
- AI-generated interpretation/alignment is distinguishable from official source text;
- material AI suggestions remain teacher-reviewable;
- accept/edit/reject or equivalent educator control is preserved before suggestions become governed planning content or official exports;
- bounded AI usage/cost metadata may be retained for operations/governance.

Brau Consulting's policy is not to opt TPP customer content into third-party model training without explicit governance review, updated disclosures, and any required customer authorization. We will reverify the production OpenAI account configuration and applicable provider agreement/DPA before publication.

## Standards architecture

TPP ingests authoritative educational standards and related governed reference content using deterministic source-processing rather than generative AI. The implementation preserves source/version provenance, approved snapshots, course mapping, reconciliation of changed sources, and historical plan context.

AI may explain or suggest alignment to a standard but does not create, amend, or replace authoritative standard text.

## Administration and reporting

Current roles include teacher, school administrator, district administrator, and Platform Owner capabilities. Role-based reporting is limited to educator/professional operational data within the no-student-data boundary.

TPP also has a first-party product-effectiveness telemetry mechanism using bounded active-interaction heartbeat event keys. It does not record keystroke contents, mouse coordinates, teacher-entered planning/reflection text, student data, or continuous login duration. Duration metrics are restricted to Platform Owner product analysis and are not provided through ordinary school/district administrator reporting or presented as teacher-performance scores.

We would like counsel to review whether this disclosure and role separation are appropriate for school/district contracting and privacy notices.

## Data retention status

We have deliberately not invented a broad numerical deletion schedule.

The currently verified numerical setting is:

- AWS application logs: 30 days.

Final periods remain to be established and technically verified for active planning content, account/institution termination, audit/version history, AI operational metadata, product analytics, authentication/security records, database backups, exports retained server-side if any, and support/incident records.

We would appreciate counsel's advice regarding appropriate contract language while those operational schedules are finalized, and whether any applicable law or public-school procurement expectation should drive minimum/maximum periods.

## Accessibility

Because TPP is intended for public-school customers, the governance packet treats WCAG 2.1 Level AA as the explicit DOJ Title II technical baseline for covered web/mobile content, with WCAG 2.2 AA potentially used as an additional engineering target.

We have not represented that the pilot deployment itself proves complete WCAG conformance. We would like counsel to advise on contract language, generated planning PDFs/electronic documents, representations/warranties, remediation obligations, and any procurement considerations related to Title II accessibility requirements.

## Documents submitted for review

Primary customer-facing drafts:

1. `TERMS_OF_USE.md`
2. `PRIVACY_POLICY.md`
3. `ACCEPTABLE_USE_POLICY.md`
4. `AI_USE_AND_ACCURACY_NOTICE.md`
5. `INSTITUTIONAL_SERVICES_AGREEMENT.md`
6. `SECURITY_AND_DATA_PRACTICES.md`
7. `SUBPROCESSORS.md`
8. `ACCESSIBILITY_STATEMENT.md`

Useful internal context:

- `POST_PILOT_RECONCILIATION_2026-08-13.md`
- `DECISIONS_REQUIRED_BEFORE_PUBLICATION.md`
- `DATA_RETENTION_AND_DELETION_POLICY.md`
- `INCIDENT_RESPONSE_POLICY.md`
- `../governance/LEGAL_COMPLIANCE_REQUIREMENTS.md`
- `../governance/LEGAL_COMPLIANCE_RELEASE_CHECKLIST.md`
- `../governance/PRODUCT_ANALYTICS_DECISION_2026-08-13.md`

## Specific questions for counsel

Please focus legal review on the following issues:

1. **Terms enforceability and acceptance** — appropriate click-through/acceptance mechanism, amendment process, and institutional-versus-individual precedence.
2. **Limitation of liability** — appropriate cap, exclusions, carve-outs, and treatment for governmental/public-school customers.
3. **Indemnification** — whether and how individual indemnification should apply and how to avoid provisions public entities cannot legally provide.
4. **Warranty/disclaimer language** — particularly for AI-generated content, standards alignment, availability, and instructional decisions.
5. **Governing law, venue, arbitration, and jury waiver** — recommended approach for Brau Consulting LLC and public-school customers.
6. **Institutional/public-school agreement terms** — appropriations/non-appropriation, public-records/confidentiality, insurance, breach terms, termination, procurement clauses, and governmental restrictions.
7. **Privacy posture** — whether the no-student-data architecture and policy language appropriately limit student-record obligations; treatment of accidental prohibited data; educator/admin account information; product analytics; and institutional administrator visibility.
8. **Incident/breach obligations** — recommended contractual notification language and interaction with Alabama and other applicable state breach laws.
9. **Retention/deletion** — recommended contractual framework while final operational schedules are being technically verified.
10. **AI provisions** — provider disclosure, human-review responsibility, model-training/data-use language, changing models/providers, and any additional AI-specific provisions advisable for school customers.
11. **Accessibility** — Title II/WCAG 2.1 AA contracting implications, representations, generated PDFs, remediation obligations, and procurement language.
12. **Intellectual property** — user/institution ownership, Brau Consulting's limited processing license, AI output treatment, feedback, standards/reference content, and employment-created materials.
13. **Subprocessors** — notice/change provisions, DPA expectations, and whether a separate data-processing/security addendum is advisable despite the no-student-data boundary.
14. **Commercial model** — recommended structure for school/district subscriptions, renewal, cancellation, nonpayment, and pilot-to-paid conversion once commercial terms are finalized.

## Matters intentionally not included

The current product scope does not include student accounts, student rosters, student education records, parent portals, under-13 accounts, or student-facing AI workflows. Accordingly, the packet does not currently include COPPA parental-consent terms, a student DPA, parent terms, or a FERPA-specific student-record processing agreement.

If counsel believes a school-facing agreement should nevertheless contain specific FERPA or student-data disclaimers because educators could accidentally submit prohibited information, we would appreciate recommended language that preserves rather than expands the no-student-data architecture.

## Requested review outcome

We are seeking:

- redlines or comments on the customer-facing documents;
- confirmation of provisions that should remain separate versus incorporated into the Terms or institutional agreement;
- recommended language for unresolved liability, indemnity, venue/dispute, privacy, incident, accessibility, and public-school contracting issues;
- identification of any missing document that should be added before broader school/district deployment;
- identification of any current language that unnecessarily creates obligations beyond the actual TPP service or data boundary.
