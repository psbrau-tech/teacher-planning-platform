# Teacher Planning Platform — Counsel Review Brief

**Provider:** Brau Consulting LLC  
**Original date:** 2026-08-13  
**Product reconciliation:** 2026-08-14  
**Status:** Pre-publication legal-review brief

## Purpose of this brief

Brau Consulting LLC is preparing Teacher Planning Platform (TPP) for broader school/district use after deployment of a controlled pilot. This brief is intended to help counsel review the accompanying Terms of Use, Privacy Policy, Acceptable Use Policy, AI Use & Accuracy Notice, Institutional Services Agreement, Security & Data Practices overview, Subprocessor List, Accessibility Statement, and related internal governance documents efficiently.

The customer-facing documents are drafts only and are not yet legally effective. The August 14 reconciliation below also distinguishes source-controlled product work from features that have actually been activated in the pilot infrastructure.

## Product summary

TPP is an adult educator/administrator productivity and instructional-planning platform. It helps teachers organize curriculum and pacing, work with authoritative instructional standards, plan weekly instruction, validate/reflect on completed work, carry lessons forward when schedules change, submit planning records, and generate school-required planning documents. Administrators have role-based visibility into permitted educator/professional operational information and reporting.

TPP provides teacher-invoked generative-AI planning assistance. AI suggestions are drafts subject to educator review and control; the service is not designed to make autonomous instructional decisions.

The product also now includes source-controlled professional-learning features that analyze already-submitted professional planning/reflection information. These features remain within the adult educator/admin boundary and are specifically designed not to become teacher-evaluation or student-analytics systems.

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

The deployed controlled-pilot baseline includes:

- Amazon Web Services in `us-east-2`;
- ECS/Fargate application hosting behind an Application Load Balancer;
- HTTPS/TLS support;
- immutable/scanned ECR images;
- CloudWatch application logs configured for 30-day retention;
- AWS Secrets Manager/protected configuration for runtime secrets;
- Supabase for database/authentication-related platform services; and
- OpenAI API/business services for approved generative-AI functions.

The application/database model includes role/authorization data, professional curriculum and planning records, governed standards/source provenance, AI usage/decision metadata, teacher validation/reflection/submission records, bounded product analytics, and permitted administrative reporting data.

### Source-controlled notification infrastructure not yet activated

As of the August 14 reconciliation, the repository also contains fail-closed infrastructure for professional operational email through Amazon SES and an isolated future scheduled-digest worker. These changes have **not** by themselves activated SES, applied the new scheduled-worker database migration, created the scheduler, added the scheduled worker's service-role secret to AWS, selected the weekly delivery time, or sent production/pilot email.

The approved future From address is `notifications@planner.guidedscholar.ai`. Activation is designed to require separate human-controlled AWS, privacy/help, database, IAM, and schedule approvals.

## AI design

### Planning assistance

TPP uses OpenAI for approved generative-AI planning assistance. AI may suggest learning targets, standards decomposition, instructional activities, assessments, resources, literacy/ACT connections where appropriate, and related professional planning fields.

Important controls include:

- student data is prohibited from AI requests;
- authoritative standards text is ingested and governed separately from generative AI;
- AI-generated interpretation/alignment is distinguishable from official source text;
- material planning suggestions remain teacher-reviewable;
- accept/edit/reject or equivalent educator control is preserved before AI suggestions become governed planning content or official exports; and
- bounded AI usage/cost metadata may be retained for operations/governance.

### Weekly Reflection / PLC Discussion remains teacher-authored

The 12 required Weekly Reflection / PLC Discussion responses are intentionally different from AI-assisted planning. TPP does not use generative AI to suggest, generate, complete, or rewrite the teacher's required reflection responses.

After the teacher explicitly submits the completed weekly packet, a separate Reflection Intelligence function may analyze the already-submitted professional reflection content. The current design supports:

- a private teacher recap based only on that teacher's submitted reflections; and
- an anonymous aggregate school PLC brief, subject to a minimum distinct-source threshold and school reporting authorization.

Generated Reflection Intelligence is an analytical/professional-learning aid, not the teacher's official reflection response and not a teacher-quality, ranking, personnel, or performance score.

Brau Consulting's policy is not to opt TPP customer content into third-party model training without explicit governance review, updated disclosures, and any required customer authorization. We will reverify the production OpenAI account configuration and applicable provider agreement/DPA before publication.

## Standards architecture

TPP ingests authoritative educational standards and related governed reference content using deterministic source-processing rather than generative AI. The implementation preserves source/version provenance, approved snapshots, course mapping, reconciliation of changed sources, and historical plan context.

AI may explain or suggest alignment to a standard but does not create, amend, or replace authoritative standard text.

## Administration, professional-learning analytics, and reporting

Current roles include teacher, school administrator, district administrator, and Platform Owner capabilities. Role-based reporting is limited to educator/professional operational data within the no-student-data boundary.

### Reflection Intelligence and PLC artifact

The school Reflection Intelligence design uses anonymous source references for aggregate common themes and requires support from at least two distinct teacher sources before a common theme is returned. The source-controlled PLC facilitation artifact formats the already-generated aggregate brief into a transient one-to-two-page professional-learning handout with a fixed facilitation protocol and non-persistent action workspace. It does not make an additional AI request or create a new retained PLC-note store.

### Planned formative-assessment analytics

The product also includes school-level analysis of daily formative-assessment types teachers already place in submitted lesson plans, such as exit tickets/slips and other checks for understanding. Classification is deterministic rather than generative-AI based. The analytics describe **planned instructional/formative-assessment signals** only; they do not collect student assessment results and do not claim that a planned activity was actually administered. The reporting surface does not return teacher names, course names, raw lesson-plan text, or student data for this purpose and is not framed as a teacher-performance measure.

### Product-effectiveness telemetry

TPP has a first-party product-effectiveness telemetry mechanism using bounded active-interaction heartbeat event keys. It does not record keystroke contents, mouse coordinates, teacher-entered planning/reflection text, student data, or continuous login duration. Duration metrics are restricted to Platform Owner product analysis and are not provided through ordinary school/district administrator reporting or presented as teacher-performance scores.

We would like counsel to review whether these disclosure and role-separation choices are appropriate for school/district contracting, privacy notices, personnel/evaluation concerns, and professional-learning use.

## Professional operational email design

The first-release admin email design is deliberately content-minimized. An authenticated administrator may request, and a future isolated scheduler may deliver when separately activated, a weekly school operations digest containing counts such as configured assignments and submitted/missing weekly plan/packet totals plus a link back to authenticated TPP.

The first-release email contract excludes teacher names or teacher-level exception lists, teacher reflection text, AI-generated instructional insight, student data/results/work, and teacher-quality/performance information.

The automatic path is designed as a separate short-lived ECS task rather than giving the interactive web application a Supabase service-role credential. Its service-role database access is restricted through purpose-built functions that return a minimized recipient/metrics manifest. The scheduled-delivery ledger is designed to retain professional profile/school identifiers, delivery state, week, and timestamps but not the recipient email address, email body, or SES MessageId.

We would appreciate counsel's view on the sufficiency of this professional-email disclosure, whether any customer agreement should address automated operational notices, and whether there are employment/personnel concerns even when email contents are aggregate/minimized.

## Data retention status

We have deliberately not invented a broad numerical deletion schedule.

The currently verified numerical setting is:

- AWS application logs: 30 days.

Final periods remain to be established and technically verified for active planning content, account/institution termination, audit/version history, AI operational metadata, product analytics, notification-delivery records, authentication/security records, database backups, exports retained server-side if any, and support/incident records.

We would appreciate counsel's advice regarding appropriate contract language while those operational schedules are finalized, and whether any applicable law or public-school procurement expectation should drive minimum/maximum periods.

## Accessibility

Because TPP is intended for public-school customers, the governance packet treats WCAG 2.1 Level AA as the explicit DOJ Title II technical baseline for covered web/mobile content, with WCAG 2.2 AA potentially used as an additional engineering target.

We have not represented that the pilot deployment itself proves complete WCAG conformance. We would like counsel to advise on contract language, generated planning PDFs/electronic documents, printable PLC artifacts, representations/warranties, remediation obligations, and any procurement considerations related to Title II accessibility requirements.

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
- `../governance/REFLECTION_INTELLIGENCE_DECISION_2026-08-14.md`
- `../governance/DAILY_FORMATIVE_ASSESSMENT_ANALYTICS_DECISION_2026-08-14.md`
- `../governance/PLC_FACILITATION_ARTIFACT_DECISION_2026-08-14.md`
- `../governance/ADMIN_EMAIL_NOTIFICATION_DECISION_2026-08-14.md`
- `../governance/SES_NOTIFICATION_INFRASTRUCTURE_DECISION_2026-08-14.md`
- `../governance/SCHEDULED_ADMIN_DIGEST_DECISION_2026-08-14.md`

## Specific questions for counsel

Please focus legal review on the following issues:

1. **Terms enforceability and acceptance** — appropriate click-through/acceptance mechanism, amendment process, and institutional-versus-individual precedence.
2. **Limitation of liability** — appropriate cap, exclusions, carve-outs, and treatment for governmental/public-school customers.
3. **Indemnification** — whether and how individual indemnification should apply and how to avoid provisions public entities cannot legally provide.
4. **Warranty/disclaimer language** — particularly for AI-generated content, standards alignment, availability, instructional decisions, and aggregate Reflection Intelligence.
5. **Governing law, venue, arbitration, and jury waiver** — recommended approach for Brau Consulting LLC and public-school customers.
6. **Institutional/public-school agreement terms** — appropriations/non-appropriation, public-records/confidentiality, insurance, breach terms, termination, procurement clauses, and governmental restrictions.
7. **Privacy posture** — whether the no-student-data architecture and policy language appropriately limit student-record obligations; treatment of accidental prohibited data; educator/admin account information; product analytics; professional reflection analysis; operational emails; and institutional administrator visibility.
8. **Personnel/evaluation boundary** — whether additional contractual or product language is advisable to distinguish school-level Reflection Intelligence, formative-assessment planning analytics, and product-usage analytics from formal teacher evaluation/personnel decision systems.
9. **Incident/breach obligations** — recommended contractual notification language and interaction with Alabama and other applicable state breach laws.
10. **Retention/deletion** — recommended contractual framework while final operational schedules are being technically verified, including professional notification-delivery records.
11. **AI provisions** — provider disclosure, human-review responsibility, post-submission reflection synthesis, model-training/data-use language, changing models/providers, and any additional AI-specific provisions advisable for school customers.
12. **Automated professional communications** — whether weekly operational admin email requires any specific contractual, notice, suppression, recordkeeping, or public-sector communication terms beyond the current minimized design.
13. **Accessibility** — Title II/WCAG 2.1 AA contracting implications, representations, generated PDFs/print artifacts, remediation obligations, and procurement language.
14. **Intellectual property** — user/institution ownership, Brau Consulting's limited processing license, AI output treatment, feedback, standards/reference content, and employment-created materials.
15. **Subprocessors** — notice/change provisions, DPA expectations, AWS SES treatment as part of the existing AWS relationship, and whether a separate data-processing/security addendum is advisable despite the no-student-data boundary.
16. **Commercial model** — recommended structure for school/district subscriptions, renewal, cancellation, nonpayment, and pilot-to-paid conversion once commercial terms are finalized.

## Matters intentionally not included

The current product scope does not include student accounts, student rosters, student education records, parent portals, under-13 accounts, or student-facing AI workflows. Accordingly, the packet does not currently include COPPA parental-consent terms, a student DPA, parent terms, or a FERPA-specific student-record processing agreement.

If counsel believes a school-facing agreement should nevertheless contain specific FERPA or student-data disclaimers because educators could accidentally submit prohibited information, we would appreciate recommended language that preserves rather than expands the no-student-data architecture.

## Requested review outcome

We are seeking:

- redlines or comments on the customer-facing documents;
- confirmation of provisions that should remain separate versus incorporated into the Terms or institutional agreement;
- recommended language for unresolved liability, indemnity, venue/dispute, privacy, incident, accessibility, public-school contracting, professional analytics, and automated professional communications issues;
- identification of any missing document that should be added before broader school/district deployment; and
- identification of any current language that unnecessarily creates obligations beyond the actual TPP service or data boundary.
