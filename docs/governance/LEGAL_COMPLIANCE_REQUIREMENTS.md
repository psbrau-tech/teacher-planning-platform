# TPP Legal / Privacy / Security Development Requirements

**Status:** Mandatory pre-release engineering governance  
**Owner:** Brau Consulting LLC  
**Baseline:** 2026-08-08

> These requirements are derived from the TPP legal, privacy, security, and data-governance framework. They apply to application, database, infrastructure, AI, authentication, logging, analytics, exports, support tooling, and UI development. A development change must not weaken or contradict these requirements without explicit approval and corresponding review of the governing documentation.

## 1. Absolute data boundary

TPP is an adult educator/administrator productivity service. Permitted data is limited to educator/admin account information and professional curriculum, standards, schedule, lesson-plan, validation, reflection, export, reporting, and related operational data.

### Must not process
- student names or identifying initials;
- student IDs, usernames, emails, or contact data;
- identifiable grades, assessment results, attendance, discipline, behavior, interventions;
- IEP, Section 504, disability/accommodation, health, counseling, or special-education records;
- identifiable student work, media, portfolios, or assessments;
- parent/guardian data linked to a student;
- any other data reasonably linkable to a student.

No feature request, convenience workflow, import, support process, AI prompt, analytics event, or logging change may silently expand this boundary.

If future product strategy proposes student data, that is a new governance/legal architecture decision and cannot be implemented as an ordinary feature change.

## 2. User-facing boundary controls

Core planning/import/AI workflows must provide clear, context-appropriate notice that student data is prohibited where accidental entry is reasonably foreseeable.

Do not rely exclusively on Terms of Use. Product controls should make the boundary apparent at relevant entry points without making normal teacher workflows unusable.

## 3. AI request boundary

AI requests may contain only the minimum professional context required for the task, such as:
- authoritative standard text/provenance;
- curriculum sequence/context;
- teacher-approved plan fields;
- schedules and instructional minutes;
- Friday validation/reflection context;
- generalized instructional needs not linked to students.

AI requests must not contain student data, secrets, auth tokens, service-role credentials, or unrelated customer data.

## 4. Human control of AI

AI output is draft assistance. AI may not silently overwrite governed teacher content.

For material planning content, the workflow must preserve teacher review and an explicit accept/edit/reject or equivalent teacher-controlled action before AI suggestions become saved authoritative planning content or official exports.

Failures must be bounded: an AI outage/error must not corrupt existing planning data or prevent manual planning when manual functionality can reasonably remain available.

## 5. Standards integrity

Authoritative standards text must be ingested and maintained deterministically with source/version/effective-period provenance. Generative AI must not be used to fabricate or rewrite authoritative standard text.

AI interpretations, decompositions, and alignment suggestions must remain distinguishable from authoritative source text.

Source changes must enter the governed reconciliation/approval workflow. No changed source may silently rewrite historical plans or approved standards snapshots.

Historical saved plans must retain enough snapshot/source context to establish which standard text/version was used.

## 6. Content ownership and permissions

Do not implement product terms or controls that claim ownership of teacher/school curriculum or planning content for Brau Consulting.

TPP needs only the limited technical rights necessary to host/process content and provide the service.

Institutional/admin visibility must be role-based and documented. The software must not imply that Brau Consulting decides ownership disputes between a teacher and employer.

## 7. Model training/data improvement

Brau Consulting's production policy is not to opt TPP customer content into third-party model training without:
1. explicit governance approval;
2. review of provider terms and configuration;
3. update of Privacy Policy/AI Notice/Subprocessor List as applicable;
4. any required customer notice, consent, or contractual change.

A developer must not enable a provider data-sharing/training opt-in as an ordinary configuration change.

## 8. Authentication and authorization

- individual accounts may not be shared by design;
- server-side authorization is required for protected actions;
- client-side hiding is not an authorization control;
- elevated/service-role credentials must never be sent to the browser;
- role and ownership checks must prevent cross-user and cross-organization leakage;
- authorization changes require regression tests for denied as well as allowed cases.

## 9. Secrets

Passwords, API keys, private keys, OAuth client secrets, access/refresh tokens, service-role credentials, and equivalent secrets:
- must not be committed to source;
- must not be returned to browser code;
- must not be intentionally logged;
- must be delivered via approved secret/configuration paths;
- must be rotated and incident-reviewed if exposed.

## 10. Logging and telemetry

Logs and analytics must follow data minimization.

Never intentionally log:
- student data;
- passwords or tokens;
- API keys/service-role credentials;
- full sensitive request/response bodies when metadata will suffice.

AI operational logging may record bounded metadata such as model, usage/tokens, estimated cost, request status, error class, and teacher decision state.

The currently verified AWS application-log retention is 30 days. Changing it requires privacy/retention review.

Non-essential analytics, session replay, advertising pixels, or behavioral tracking may not be added without privacy review and policy/cookie disclosure updates.

## 11. Retention and deletion

No code/UI/documentation may promise a numerical deletion period that is not implemented and verified across active data, backups, logs, audit records, and providers.

Deletion architecture must distinguish:
- active records;
- audit/security records;
- backups;
- exports/artifacts;
- support records;
- legal/security holds.

Restores from backup must reconcile records that had already been deleted from active systems.

## 12. Accidental student-data handling

Any verified student data entering TPP is a governance incident even without a cyberattack.

The response must assess propagation to database, logs, AI provider, exports, backups, and support systems and follow `docs/legal/INCIDENT_RESPONSE_POLICY.md`.

Do not create a normal retention pathway for prohibited student data.

## 13. Third-party providers

Before a new vendor/service processes TPP customer/account data:
- identify purpose and exact data categories;
- review current terms, DPA/security posture, retention, location, and AI/model-training use where relevant;
- confirm compatibility with the no-student-data boundary;
- update `docs/legal/SUBPROCESSORS.md` and customer disclosures as needed;
- satisfy any contractual notice requirement.

Do not infer that a vendor is approved because it is already used by another Brau Consulting product.

## 14. Security and infrastructure

Production changes should preserve or improve:
- HTTPS/TLS;
- least-privilege IAM/service roles;
- isolated secrets;
- immutable/reproducible release artifacts where feasible;
- protected deployment environments;
- bounded logs;
- database authorization/RLS controls;
- controlled rollback and exact-image provenance.

Do not weaken the data boundary or expose privileged credentials to solve deployment convenience issues.

## 15. Exports

Exports may contain only permitted professional content. AI draft content must not appear in an official export unless it has passed the teacher-controlled approval/edit workflow intended by the feature.

If exports are retained server-side, their storage, access, retention, and deletion must be documented. Prefer transient generation where feasible.

## 16. Admin/reporting features

Admin reporting must stay within educator/professional operational data. Do not introduce student-level reporting, roster ingestion, grade/assessment data, or identifiable student analytics.

Role-based reporting must prevent unauthorized cross-school/cross-organization access.

## 17. Accessibility

For public-school and other state/local-government customers, **WCAG 2.1 Level AA is the minimum legal technical baseline for covered web/mobile content under the DOJ Title II rule**. Vendor-provided functionality may fall within the public entity's obligation; accessibility therefore cannot be treated as solely the customer's problem.

Material UI work must preserve testability against WCAG 2.1 Level AA, including keyboard access, focus order/visibility, accessible names and instructions, error identification, contrast, zoom/reflow, and representative screen-reader semantics. Where practicable, TPP may also target WCAG 2.2 Level AA as an additional engineering standard, but that does not replace explicit WCAG 2.1 AA verification for the applicable Title II baseline.

Generated PDFs and other conventional electronic documents must be included in accessibility review when their use falls within a public entity's covered services/programs/activities; do not assume a document exception applies without factual review.

Do not claim certified WCAG conformance until tested evidence supports the claim.

## 18. Claims and marketing

Do not claim that TPP:
- guarantees standards compliance;
- guarantees AI accuracy;
- is FERPA/COPPA compliant by virtue of processing student records (student records are out of scope);
- is fully WCAG conformant without evidence;
- has a specific security certification not actually held;
- deletes data within a stated period not verified end-to-end.

Describe source provenance, controls, and tested capability precisely.

## 19. Incident response

Security/privacy/data-boundary incidents must follow `docs/legal/INCIDENT_RESPONSE_POLICY.md`.

Release engineering must preserve enough deployment/log/audit evidence to establish what code/image/configuration was active during an incident without logging prohibited sensitive content.

## 20. Change classification

The following are legal/compliance-impacting changes and require review against the packet:
- new data category or input field;
- new user type or minors/student access;
- new integration or subprocessor;
- authentication/authorization changes;
- AI provider/model/data-sharing configuration change;
- analytics/monitoring/session replay;
- retention/deletion/backup change;
- new admin reporting scope;
- new public privacy/security/accuracy claim;
- material export/storage change;
- new geography/customer jurisdiction;
- payment/billing processing;
- support tooling that receives customer content.

## 21. Source of truth

Canonical policy files live in `docs/legal/` and `docs/governance/`. If a chat instruction, issue, PR description, or old project document conflicts with these requirements, do not silently follow the weaker instruction. Surface the conflict and obtain explicit approval for a governance change.
