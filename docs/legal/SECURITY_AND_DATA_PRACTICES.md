# Teacher Planning Platform — Security & Data Practices

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Procurement / Security Review Overview  
**Original baseline:** 2026-08-08  
**Post-pilot reconciliation:** 2026-08-13

This document summarizes the current controlled-pilot security and data-handling posture of Teacher Planning Platform (TPP). It is not a certification, warranty, penetration-test report, SOC report, or substitute for a signed customer security addendum.

## 1. Data boundary

TPP is designed for adult educator and administrator use and for educator/account, curriculum, standards, scheduling, lesson-planning, validation, reflection, reporting, export, product-usage, and related professional operational data. TPP is not designed to collect, store, or process student personally identifiable information or student education records.

This boundary is enforced as a product, legal, operational, AI-request, testing, and development-governance requirement. No administrator/reporting capability changes that boundary.

## 2. Deployed controlled-pilot architecture

The current controlled-pilot architecture includes:

- application workloads hosted on Amazon Web Services (AWS) in `us-east-2`;
- Amazon ECS/Fargate application execution behind an Application Load Balancer;
- HTTPS/TLS support on the public application endpoint;
- Amazon ECR immutable container images with image scanning enabled;
- Amazon CloudWatch application logging;
- AWS Secrets Manager/protected deployment configuration for runtime secrets, including the OpenAI API credential;
- Supabase for database/authentication-related platform services;
- OpenAI API/business services for teacher-invoked generative-AI assistance;
- a read-only application container root filesystem with a dedicated temporary mount;
- explicit infrastructure/runtime tagging/configuration preserving the `teacher-and-curriculum-only` boundary.

The infrastructure definition is evidence of the controlled-pilot configuration. Final publication must still confirm the actual deployed state and any provider configuration not represented in source control.

## 3. Authentication and authorization

TPP uses authenticated user accounts and server-enforced role-based authorization. Current product roles include teacher, school-administrator, district-administrator, and Platform Owner capabilities as implemented and approved.

Authorization requirements include:

- approved-account/domain controls for the applicable environment;
- server-side permission checks rather than client-side hiding alone;
- role and ownership boundaries preventing unauthorized cross-user/cross-organization access;
- isolation of elevated/service-role credentials from normal browser execution;
- regression testing of denied as well as allowed authorization paths.

Institutional reporting is limited to permitted educator/professional operational information and does not authorize student data.

## 4. Encryption and transport

The controlled pilot is designed to use HTTPS/TLS on the public endpoint through the AWS load balancer. Runtime secrets are delivered through protected secret mechanisms rather than source code or browser-side configuration.

Provider-specific encryption-at-rest, database encryption, backup encryption, secret encryption, and related settings must be verified in the actual production/provider configuration before external publication of detailed claims.

## 5. Secrets and credentials

Passwords, API keys, private keys, OAuth client secrets, access/refresh tokens, database service-role credentials, and equivalent secrets must not be committed to source, returned to browser code, or intentionally logged.

The current pilot infrastructure supports protected AWS secret injection for Supabase configuration and the OpenAI API key. Exposure of a credential is treated as a security incident and triggers containment/rotation review.

## 6. Logging, monitoring, and product telemetry

TPP uses bounded operational records for reliability, security, troubleshooting, auditability, AI governance/cost control, and approved product-effectiveness measurement.

The controlled-pilot AWS application log group is configured for **30-day retention**.

Application and AI logging must not intentionally include passwords, access tokens, API keys, service-role credentials, prohibited student data, or full sensitive request/response bodies where bounded metadata is sufficient.

AI operational records may include model identifier, token/usage counts, estimated cost, request status, failure class, and educator accept/edit/reject decision state.

### First-party active-interaction telemetry

On 2026-08-13 Brau Consulting approved bounded first-party active-interaction telemetry for product workflow-efficiency analysis. The current design uses fixed 30-second heartbeat event keys for approved workflow categories such as Course Setup, Weekly Planning, Teacher Reflection, and Friday Closeout.

A heartbeat is eligible only when the TPP tab is visible, the authenticated user has interacted recently, the workflow area can be classified into an approved category, and the tab owns the short-lived local activity lease used to reduce double-counting across multiple open TPP tabs.

The telemetry does **not** record:

- keystroke contents;
- mouse coordinates;
- teacher-entered planning/reflection text;
- student data;
- continuous login duration;
- third-party advertising or session-replay identifiers.

Duration reporting is restricted to the Platform Owner for product-effectiveness analysis. It is not part of ordinary school/district administrator reporting and must not be represented as a teacher-quality, effort, productivity, or performance score.

Any expansion of data captured, purpose, reporting audience, or use of a third-party analytics/session-replay provider requires new privacy/governance review before release.

## 7. AI data handling

AI assistance is teacher-invoked and limited by governance to permitted professional context. Student information, secrets, authentication credentials, and unrelated customer data are prohibited from AI requests.

Material AI suggestions remain reviewable drafts and require educator control before becoming governed planning content or official exports. AI failure should be bounded so existing saved work is not corrupted and manual planning remains usable where intended.

OpenAI is the implemented pilot AI provider. Brau Consulting's governance policy is not to opt TPP customer content into third-party model training without explicit approval, current provider review, updated disclosures, and any required customer authorization. The production OpenAI account/project configuration, applicable agreement/DPA, and customer-content data-use setting must be reverified immediately before publication.

## 8. Standards integrity

Authoritative standards and related governed reference content are processed separately from generative AI. Official source text is intended to be acquired and parsed deterministically with source/version/effective-period provenance and governed snapshots.

AI-generated explanations, decompositions, alignments, or planning suggestions must remain distinguishable from authoritative standard text. Source changes enter governed reconciliation/approval rather than silently rewriting approved or historical plan content.

## 9. Secure development and release controls

Current repository/release controls include:

- pull-request-based review;
- automated CI and regression testing;
- immutable container-image practices;
- image scanning;
- controlled deployment workflows;
- protected runtime/deployment secrets;
- dedicated/least-privilege deployment and runtime roles as implemented;
- exact-image/release provenance and verification practices;
- database authorization/RLS and application-level permission tests;
- controlled rollback practices.

Legal/privacy/security-impacting changes are governed by `docs/governance/LEGAL_COMPLIANCE_REQUIREMENTS.md` and the release checklist.

## 10. Data minimization

TPP should collect and retain only information reasonably necessary for educator planning, account/institution administration, reliability, security, auditability, contractual obligations, standards governance, approved product-effectiveness analysis, and lawful service improvement.

Product analytics should favor bounded event keys and aggregate reporting over capture of teacher-entered content or high-granularity behavioral data.

The no-student-data design materially reduces the service's sensitivity and regulatory complexity but does not eliminate obligations to protect educator identity/account data, professional content, institutional confidential information, credentials, security records, or operational metadata.

## 11. Data location and providers

The controlled-pilot application runtime is configured for AWS `us-east-2`.

Supabase and OpenAI processing locations, retention, backup behavior, and contractual data-processing terms depend on the applicable project/account configuration and provider agreements. These must be verified in the final Subprocessor List/data-flow inventory before publication.

## 12. Retention and deletion

The only currently approved numerical retention period in this overview is the verified **30-day AWS application-log retention**.

A final retention schedule remains required for:

- active educator/admin accounts;
- curriculum and planning content;
- standards selections/snapshots and historical provenance;
- validation/reflection/submission and audit/version history;
- AI operational metadata;
- first-party product-usage/active-time telemetry;
- authentication/security records;
- database backups;
- server-retained exports, if any;
- support/incident/legal-hold records;
- account/institution termination.

No public numerical deletion SLA should be made until implementation is verified end-to-end, including backups and restore behavior.

## 13. Vulnerability and incident handling

Suspected vulnerabilities, unauthorized access, credential exposure, accidental prohibited student-data submission, provider incidents, and other security/privacy events are handled under the TPP Incident Response Policy.

Brau Consulting will investigate credible incidents, contain risk, preserve the minimum necessary evidence, coordinate with affected providers/customers, and provide notifications required by applicable law and contract.

## 14. Business continuity and recovery

TPP uses managed cloud infrastructure. Backup, restore, recovery-point, recovery-time, uptime, and disaster-recovery representations are not contractual commitments unless specifically tested, approved, and included in an applicable customer agreement.

## 15. Accessibility and electronic documents

Accessibility is treated as a product/procurement requirement for public-school use. The governance baseline requires explicit evaluation against WCAG 2.1 Level AA where the DOJ Title II rule applies. WCAG 2.2 AA may be used as an additional engineering target.

No claim of certified or complete WCAG conformance is made by this document. Generated PDFs and other electronic planning documents must be included in accessibility review when applicable to covered public-entity services/programs/activities.

## 16. Customer responsibilities

Customers and users are expected to:

- keep credentials secure;
- limit access to authorized personnel;
- promptly remove access when no longer required;
- stay within the no-student-data boundary;
- review AI-generated content before use;
- use lawful source materials and respect intellectual-property rights;
- report suspected unauthorized access or security/privacy incidents promptly.

## 17. Security review contact

[SECURITY CONTACT EMAIL TO BE APPROVED]

## Final pre-publication verification gate

Before external publication, verify and record:

- actual deployed AWS Region/services, TLS and certificate state;
- Supabase project region, encryption/backup/restore retention, enabled services and DPA posture;
- database RLS/authorization posture;
- authentication providers/account controls;
- OpenAI production account/project data-use configuration and current contractual terms/DPA;
- runtime secret path;
- complete log/telemetry/browser-storage inventory and retention;
- export storage behavior;
- backup/restore and deletion procedures;
- incident and vulnerability-reporting contacts;
- accessibility evidence;
- all material subprocessors and customer-notice requirements.
