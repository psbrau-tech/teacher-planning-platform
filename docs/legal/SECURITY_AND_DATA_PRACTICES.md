# Teacher Planning Platform — Security & Data Practices

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Procurement / Security Review Overview  
**Original baseline:** 2026-08-08  
**Post-pilot reconciliation:** 2026-08-14

This document summarizes the current controlled-pilot security and data-handling posture of Teacher Planning Platform (TPP) and identifies source-controlled release work that remains unactivated. It is not a certification, warranty, penetration-test report, SOC report, or substitute for a signed customer security addendum.

## 1. Data boundary

TPP is designed for adult educator and administrator use and for educator/account, curriculum, standards, scheduling, lesson-planning, validation, teacher-authored reflection, professional-learning, reporting, notification, export, product-usage, and related professional operational data. TPP is not designed to collect, store, or process student personally identifiable information or student education records.

This boundary is enforced as a product, legal, operational, AI-request, testing, and development-governance requirement. No administrator/reporting, professional-learning, assessment-planning, or notification capability changes that boundary.

## 2. Deployed controlled-pilot architecture

The current deployed controlled-pilot architecture includes:

- application workloads hosted on Amazon Web Services (AWS) in `us-east-2`;
- Amazon ECS/Fargate application execution behind an Application Load Balancer;
- HTTPS/TLS support on the public application endpoint;
- Amazon ECR immutable container images with image scanning enabled;
- Amazon CloudWatch application logging;
- AWS Secrets Manager/protected deployment configuration for runtime secrets, including the OpenAI API credential;
- Supabase for database/authentication-related platform services;
- OpenAI API/business services for approved generative-AI functions;
- a read-only application container root filesystem with a dedicated temporary mount;
- explicit infrastructure/runtime tagging/configuration preserving the `teacher-and-curriculum-only` boundary.

The repository also contains fail-closed infrastructure for Amazon SES professional operational email and an isolated future scheduled-digest worker. Those source-controlled paths are not represented here as active pilot services merely because the code has been merged. SES identity verification/activation, the scheduled-worker migration, the service-role secret, live IAM-policy changes, the delivery schedule, and the scheduled stack remain controlled release actions until separately verified and activated.

The infrastructure definition is evidence of intended/current configuration only to the extent it has been deployed and verified. Final publication must confirm the actual deployed state and any provider configuration not represented in source control.

## 3. Authentication and authorization

TPP uses authenticated user accounts and server-enforced role-based authorization. Current product roles include teacher, school-administrator, district-administrator, and Platform Owner capabilities as implemented and approved.

Authorization requirements include:

- approved-account/domain controls for the applicable environment;
- server-side permission checks rather than client-side hiding alone;
- role and ownership boundaries preventing unauthorized cross-user/cross-organization access;
- isolation of elevated/service-role credentials from normal browser execution and the interactive web application where not required;
- regression testing of denied as well as allowed authorization paths.

Institutional reporting is limited to permitted educator/professional operational information and does not authorize student data.

The source-controlled scheduled-email design uses a separately governed short-lived worker rather than expanding the interactive web task's database privileges. The intended service-role database functions return a purpose-limited professional recipient/aggregate-metrics manifest rather than generic application table access in worker code.

## 4. Encryption and transport

The controlled pilot is designed to use HTTPS/TLS on the public endpoint through the AWS load balancer. Runtime secrets are delivered through protected secret mechanisms rather than source code or browser-side configuration.

Provider-specific encryption-at-rest, database encryption, backup encryption, secret encryption, and related settings must be verified in the actual production/provider configuration before external publication of detailed claims.

## 5. Secrets and credentials

Passwords, API keys, private keys, OAuth client secrets, access/refresh tokens, database service-role credentials, and equivalent secrets must not be committed to source, returned to browser code, or intentionally logged.

The current pilot infrastructure supports protected AWS secret injection for Supabase configuration and the OpenAI API key. The source-controlled scheduled-digest design, if later activated, requires a separately stored Supabase service-role secret available only to the isolated scheduled task; the interactive web task must not receive that credential. The scheduled task is also intentionally designed not to receive the OpenAI key, Supabase anon key, or OAuth credentials.

Exposure of a credential is treated as a security incident and triggers containment/rotation review.

## 6. Logging, monitoring, notification records, and product telemetry

TPP uses bounded operational records for reliability, security, troubleshooting, auditability, AI governance/cost control, approved professional-notification delivery accounting, and approved product-effectiveness measurement.

The controlled-pilot AWS application log group is configured for **30-day retention**.

Application and AI logging must not intentionally include passwords, access tokens, API keys, service-role credentials, prohibited student data, or full sensitive request/response bodies where bounded metadata is sufficient.

AI operational records may include model identifier, token/usage counts, estimated cost, request status, failure class, and educator accept/edit/reject decision state where applicable.

The approved professional-notification design favors content-free or minimized delivery records. The source-controlled automatic-delivery ledger is designed to retain school/profile identifiers, notification type, week, delivery state, and timestamps, but not the recipient email address, email body, Amazon SES MessageId, reflection text, generated instructional insight, teacher names, or student data.

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

## 7. AI and Reflection Intelligence data handling

AI-assisted planning is teacher-invoked and limited by governance to permitted professional context. Student information, secrets, authentication credentials, and unrelated customer data are prohibited from AI requests.

Material AI planning suggestions remain reviewable drafts and require educator control before becoming governed planning content or official exports. AI failure should be bounded so existing saved work is not corrupted and manual planning remains usable where intended.

The required Weekly Reflection / PLC Discussion is teacher-authored. Generative AI is not permitted to suggest, generate, complete, or rewrite those required responses.

After explicit submission, approved Reflection Intelligence may analyze teacher-authored professional reflections to create a private teacher recap or an anonymous aggregate school PLC brief. The school synthesis is subject to authorization and minimum distinct-source controls. Generated recaps/themes are professional-learning aids, not teacher-performance, personnel, ranking, or student-outcome scores.

OpenAI is the implemented pilot AI provider. Brau Consulting's governance policy is not to opt TPP customer content into third-party model training without explicit approval, current provider review, updated disclosures, and any required customer authorization. The production OpenAI account/project configuration, applicable agreement/DPA, and customer-content data-use setting must be reverified immediately before publication.

## 8. Standards integrity

Authoritative standards and related governed reference content are processed separately from generative AI. Official source text is intended to be acquired and parsed deterministically with source/version/effective-period provenance and governed snapshots.

AI-generated explanations, decompositions, alignments, or planning suggestions must remain distinguishable from authoritative standard text. Source changes enter governed reconciliation/approval rather than silently rewriting approved or historical plan content.

## 9. Professional-learning and formative-assessment analytics

School-level Reflection Intelligence uses anonymous aggregate source references for common themes and requires multiple distinct teacher sources under the approved design. The printable PLC facilitation artifact is derived from an already-generated aggregate brief and does not trigger a second AI request or create a retained PLC-note store in its current form.

Daily formative-assessment analytics classify existing submitted lesson-plan fields deterministically. They describe planned checks for understanding/evidence-of-learning strategies; they do not collect student assessment results and do not establish that a planned activity was actually administered. The reporting API is designed not to return raw lesson-plan text, teacher names, or course names for that analytics purpose.

These professional-learning/product signals must not be represented as teacher-quality, effort, productivity, ranking, or personnel-performance scores.

## 10. Secure development and release controls

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

New notification infrastructure is intentionally fail-closed. Source-controlled activation workflows require explicit release confirmations and are not proof that SES or scheduled delivery is active.

Legal/privacy/security-impacting changes are governed by `docs/governance/LEGAL_COMPLIANCE_REQUIREMENTS.md` and the release checklist.

## 11. Data minimization

TPP should collect and retain only information reasonably necessary for educator planning, account/institution administration, professional learning, approved operational communication, reliability, security, auditability, contractual obligations, standards governance, approved product-effectiveness analysis, and lawful service improvement.

Product analytics should favor bounded event keys and aggregate reporting over capture of teacher-entered content or high-granularity behavioral data.

The no-student-data design materially reduces the service's sensitivity and regulatory complexity but does not eliminate obligations to protect educator identity/account data, professional content, institutional confidential information, credentials, security records, professional email addresses, or operational metadata.

## 12. Data location and providers

The controlled-pilot application runtime is configured for AWS `us-east-2`.

Supabase and OpenAI processing locations, retention, backup behavior, and contractual data-processing terms depend on the applicable project/account configuration and provider agreements. These must be verified in the final Subprocessor List/data-flow inventory before publication.

If the source-controlled professional-email path is activated, Amazon SES is intended to operate in the approved AWS Region with `notifications@planner.guidedscholar.ai` as the application From address. Sender verification, SES account status, exact IAM policy, delivery configuration, and provider terms/settings remain release-verification requirements rather than current claims.

## 13. Retention and deletion

The only currently approved numerical retention period in this overview is the verified **30-day AWS application-log retention**.

A final retention schedule remains required for:

- active educator/admin accounts;
- curriculum and planning content;
- standards selections/snapshots and historical provenance;
- validation/reflection/submission and audit/version history;
- AI operational metadata;
- first-party product-usage/active-time telemetry;
- professional notification-delivery records;
- authentication/security records;
- database backups;
- server-retained exports, if any;
- support/incident/legal-hold records;
- account/institution termination.

No public numerical deletion SLA should be made until implementation is verified end-to-end, including backups and restore behavior.

## 14. Vulnerability and incident handling

Suspected vulnerabilities, unauthorized access, credential exposure, accidental prohibited student-data submission, provider incidents, and other security/privacy events are handled under the TPP Incident Response Policy.

Brau Consulting will investigate credible incidents, contain risk, preserve the minimum necessary evidence, coordinate with affected providers/customers, and provide notifications required by applicable law and contract.

## 15. Business continuity and recovery

TPP uses managed cloud infrastructure. Backup, restore, recovery-point, recovery-time, uptime, and disaster-recovery representations are not contractual commitments unless specifically tested, approved, and included in an applicable customer agreement.

## 16. Accessibility and electronic documents

Accessibility is treated as a product/procurement requirement for public-school use. The governance baseline requires explicit evaluation against WCAG 2.1 Level AA where the DOJ Title II rule applies. WCAG 2.2 AA may be used as an additional engineering target.

No claim of certified or complete WCAG conformance is made by this document. Generated PDFs and other electronic planning documents, including printable PLC artifacts where used as covered public-entity materials, must be included in accessibility review when applicable to covered public-entity services/programs/activities.

## 17. Customer responsibilities

Customers and users are expected to:

- keep credentials secure;
- limit access to authorized personnel;
- promptly remove access when no longer required;
- stay within the no-student-data boundary;
- review AI-generated content before use;
- treat professional-learning/product analytics according to applicable policy and law rather than as TPP-generated personnel scores;
- use lawful source materials and respect intellectual-property rights;
- report suspected unauthorized access or security/privacy incidents promptly.

## 18. Security review contact

[SECURITY CONTACT EMAIL TO BE APPROVED]

## Final pre-publication verification gate

Before external publication, verify and record:

- actual deployed AWS Region/services, TLS and certificate state;
- any activated SES identity/account status, sender configuration, and professional-email data path;
- any activated scheduled-worker task, service-role secret, IAM policy, EventBridge schedule, and delivery ledger;
- Supabase project region, encryption/backup/restore retention, enabled services and DPA posture;
- database RLS/authorization posture;
- authentication providers/account controls;
- OpenAI production account/project data-use configuration and current contractual terms/DPA;
- Reflection Intelligence production authorization/request/data path;
- runtime secret path;
- complete log/telemetry/notification/browser-storage inventory and retention;
- export storage behavior;
- backup/restore and deletion procedures;
- incident and vulnerability-reporting contacts;
- accessibility evidence;
- all material subprocessors and customer-notice requirements.
