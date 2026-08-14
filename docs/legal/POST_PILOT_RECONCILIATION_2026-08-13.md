# TPP Post-Pilot Legal / Compliance Reconciliation

**Provider:** Brau Consulting LLC  
**Date:** 2026-08-13  
**Status:** Internal reconciliation record

## Purpose

This record reconciles the Teacher Planning Platform (TPP) pre-release legal/compliance packet against the implemented and deployed controlled pilot after the original 2026-08-08 governance baseline.

The purpose is to ensure that the documents describe the actual service rather than an earlier planned architecture, while preserving unresolved matters for Brau Consulting and qualified counsel instead of inventing unsupported commitments.

## Reconciliation conclusion

The original legal architecture remains materially sound. No implemented pilot feature requires expansion of the locked no-student-data boundary. The following foundational rules remain unchanged:

- TPP is an adult educator/administrator productivity platform;
- student PII and student education records are prohibited;
- generative AI is teacher-invoked draft assistance and remains subject to educator review/control;
- authoritative standards text is governed source content, not generative AI output;
- role-based authorization must prevent unauthorized cross-user/cross-organization access;
- Brau Consulting does not obtain ownership of customer curriculum/planning content merely because TPP processes it;
- unsupported guarantees concerning AI accuracy, standards compliance, security certifications, accessibility conformance, or deletion timing remain prohibited.

## Implemented service capabilities now reflected in the packet

The reconciled packet recognizes that the controlled pilot now includes, or has implemented governance for:

1. adult educator, school-administrator, district-administrator, and Platform Owner roles;
2. teacher course/curriculum setup and pacing;
3. authoritative Alabama standards and related governed reference content, including source/version provenance, snapshots, reconciliation, course mapping, and administrative controls;
4. teacher-invoked OpenAI planning assistance and reflection assistance;
5. AI usage/cost metadata and educator suggestion-decision records;
6. weekly lesson planning, schedule exceptions, validation, reflection, carry-forward/resequencing, and submission workflows;
7. administrative review/reporting of permitted educator/professional operational data;
8. PDF and related planning-document generation/export workflows;
9. first-party bounded product-usage and active-interaction telemetry approved for product-effectiveness measurement, with duration reporting restricted to the Platform Owner rather than ordinary school/district reporting.

## Deployed infrastructure facts verified from repository configuration

The pilot infrastructure definition establishes:

- AWS Region: `us-east-2`;
- Amazon ECS/Fargate application execution;
- Application Load Balancer public routing with HTTPS/TLS support;
- Amazon ECR with immutable tags and image scanning;
- Amazon CloudWatch application logs with `RetentionInDays: 30`;
- AWS Secrets Manager/protected secret injection for Supabase and OpenAI runtime credentials;
- read-only application container root filesystem with a dedicated temporary mount;
- explicit `teacher-and-curriculum-only` runtime/infrastructure boundary.

Supabase is the implemented database/authentication platform and OpenAI is the implemented generative-AI provider. Final project-region, backup, retention, DPA, and provider-account configuration details remain publication-verification items where not established by repository evidence alone.

## Material legal-document impacts

### Terms of Use

No structural rewrite is required. Existing adult-user scope, no-student-data prohibition, AI review responsibility, ownership language, third-party service language, and institutional-order precedence remain appropriate. Counsel review remains required for liability, indemnity, disclaimers, governing law/venue, dispute process, and acceptance mechanism.

### Privacy Policy

The current draft already describes implemented AI processing, permitted professional planning information, administrator visibility, first-party product analytics/active-time telemetry, 30-day AWS application logs, and the U.S.-focused service boundary. Final publication still requires completion of the vendor/configuration and retention inventory.

### Acceptable Use Policy

No material boundary change is required. Student data remains prohibited even though only adults use the service.

### AI Use & Accuracy Notice

The notice remains aligned with implemented teacher-invoked AI and authoritative-standard separation. Production OpenAI account/data-use configuration and current provider terms must be reverified immediately before publication.

### Institutional Services Agreement

The implemented school/district administration/reporting capability makes institutional contracting an active rather than hypothetical use case. Counsel should review public-school/government contracting restrictions, public-records/confidentiality interaction, appropriation/non-appropriation language if relevant, breach terms, indemnification, insurance requests, liability caps, governing law, and venue.

### Security & Data Practices

The architecture description is updated from intended/prospective language to verified controlled-pilot implementation where supported by repository evidence. No certification or penetration-test claim is made.

### Subprocessor List

AWS, Supabase, and OpenAI are now identified as deployed controlled-pilot service providers. Final production verification is still required for Supabase project/backup configuration, OpenAI account data controls and applicable contract/DPA, and any additional provider that routinely processes account/customer data.

### Retention & Deletion

The only approved numerical retention period remains the verified 30-day AWS application-log setting. No numerical active-content, backup, AI-metadata, product-analytics, audit-history, or post-termination deletion promise should be published until implemented and tested end-to-end.

### Accessibility

The DOJ Title II/WCAG 2.1 Level AA baseline remains a release/procurement requirement for covered public-school use. The pilot deployment itself does not establish full WCAG conformance. Accessibility evidence remains a publication/release item and counsel should review contract treatment.

## Product analytics reconciliation

On 2026-08-13, TPP approved bounded first-party active-interaction heartbeat telemetry for product workflow efficiency measurement. The telemetry does not record keystroke contents, mouse coordinates, teacher-entered planning/reflection text, student data, continuous login duration, or third-party advertising/session-replay identifiers.

Duration metrics are restricted to Platform Owner product-effectiveness analysis and are not exposed as ordinary school/district administrator reporting or teacher-performance scores. The Privacy Policy and Security & Data Practices drafts already reflect this decision. Any change that broadens the telemetry, audience, data captured, or purpose requires renewed privacy/governance review.

## No-student-data conclusion

No post-baseline implementation reviewed here authorizes student data. District/school administration, standards, teacher submissions, reporting, analytics, AI requests, and exports remain constrained to educator/professional operational content.

If future development proposes student accounts, rosters, identifiable student work, grades/assessment data, IEP/504 information, student-level analytics, or other student records, ordinary feature development must stop and the legal/privacy/security architecture must be reopened before implementation.

## Remaining hard publication decisions

The following remain unresolved and should be visible to counsel rather than silently filled in:

- public business address and contact channels;
- commercial/payment/renewal model;
- account/institution termination and export window;
- numerical retention/deletion schedule beyond application logs;
- final Supabase production region/backup/DPA posture;
- final OpenAI production account/data-control/DPA posture;
- incident contacts;
- WCAG 2.1 AA evidence and accessibility contract language;
- warranties/disclaimers;
- liability cap/exclusions;
- indemnification;
- governing law, venue, arbitration/jury-waiver decision;
- institutional/public-school contracting provisions;
- final acceptance/consent mechanism for Terms.

## Counsel handoff

Use `COUNSEL_REVIEW_BRIEF_2026-08-13.md` as the front document for legal review, followed by the customer-facing drafts and the relevant internal governance documents when counsel needs implementation context.
