# Teacher Planning Platform — Security & Data Practices

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Procurement / Security Review Overview  
**Baseline:** 2026-08-08

This document summarizes the intended security and data-handling posture of Teacher Planning Platform (TPP). It is not a certification, warranty, penetration-test report, or substitute for a signed customer security addendum.

## 1. Data boundary

TPP is designed for adult educator and administrator use and for teacher/account, curriculum, standards, scheduling, lesson-planning, validation, export, and related professional data. TPP is not designed to collect, store, or process student personally identifiable information or student education records.

This boundary is enforced as a product, legal, and operational requirement. User-facing notices, AI request boundaries, testing, and development governance should reinforce the same rule.

## 2. Current pilot architecture

The controlled pilot architecture includes:
- web/application workloads hosted on Amazon Web Services (AWS) in `us-east-2`;
- Amazon ECS/Fargate application execution behind an Application Load Balancer;
- HTTPS/TLS on the public application endpoint when the controlled TLS configuration is enabled;
- Amazon ECR immutable container images with image scanning enabled;
- Amazon CloudWatch application logging;
- Supabase for database/authentication-related platform services;
- OpenAI API/business services for teacher-invoked generative AI assistance;
- AWS Secrets Manager / protected deployment configuration for runtime secrets as implemented by the deployment architecture.

Production architecture must be reverified before this document is published externally.

## 3. Authentication and authorization

TPP uses authenticated user accounts and role-based authorization. Pilot access is constrained by approved accounts/domain configuration and governed roles. Individual accounts must not be shared.

The application is designed to enforce authorization server-side rather than relying solely on client-side visibility controls. Database access controls and role/ownership checks are part of the defense-in-depth model.

## 4. Encryption and transport

The deployed pilot uses HTTPS/TLS for the public application endpoint once TLS is attached, with an AWS load-balancer security policy supporting modern TLS. AWS and other material providers offer encryption for customer data in transit and at rest according to their service configurations and agreements.

Before production publication, Brau Consulting will verify database encryption, backup encryption, secret encryption, and any provider-specific encryption configuration actually used by TPP.

## 5. Secrets and credentials

Secrets such as API keys, database credentials, and service-role credentials must not be committed to source code, exposed to browser clients, or intentionally written to application logs.

Runtime secrets are intended to be delivered through protected environment/secret mechanisms. Service-role or elevated database credentials must remain isolated from normal browser execution.

## 6. Logging and monitoring

TPP logs bounded operational information necessary for reliability, security, troubleshooting, and auditability. The controlled pilot AWS application log group is configured for 30-day retention.

Application and AI logging must not intentionally include passwords, access tokens, API keys, service-role credentials, or prohibited student data. AI usage/cost records may contain bounded metadata such as model identifier, token/usage counts, estimated cost, request status, and educator decision state.

A final production inventory of audit logs, authentication logs, database logs, infrastructure logs, AI operational records, and retention periods is a release requirement.

## 7. AI data handling

AI assistance is teacher-invoked and must be limited to permitted professional context. TPP is designed so AI suggestions remain reviewable drafts and require educator control before becoming governed planning content or exports.

OpenAI's current business/API terms state that customer API input and output are not used to develop or improve OpenAI services unless the customer explicitly agrees. Brau Consulting's governance policy is not to opt TPP customer content into model training without prior review, updated disclosures, and any required contractual authorization.

The production OpenAI account setting and applicable provider terms must be reverified before external publication.

## 8. Standards integrity

Authoritative standards ingestion is governed separately from generative AI. Official source text should be fetched and parsed deterministically, stored with source/version provenance, and protected from silent AI rewriting.

Changed authoritative sources are intended to enter a review/reconciliation process rather than silently replacing approved standards used for historical plans. Historical plan integrity should preserve the standards/source context applicable at the time of the saved plan.

## 9. Secure development and release controls

Current repository/release controls include code review through pull requests, automated CI tests, immutable container images, controlled deployment workflows, protected environment configuration, explicit deployment roles, and exact-image verification practices.

Changes affecting the legal/privacy/security boundary must be checked against `docs/governance/LEGAL_COMPLIANCE_REQUIREMENTS.md` before release.

## 10. Data minimization

TPP should collect and retain only information reasonably necessary for educator planning, account administration, reliability, security, auditability, contractual obligations, and approved product improvement.

The no-student-data design materially reduces the sensitivity and regulatory complexity of the service. It does not eliminate the need to protect educator account information, professional content, credentials, or institutional confidential information.

## 11. Data location and providers

The pilot application runtime is in AWS `us-east-2`. Supabase and OpenAI processing locations and retention behavior depend on their contracted service, project configuration, and applicable provider terms. Those details must be verified and recorded in the final Subprocessor List and production data-flow inventory before general release.

## 12. Retention and deletion

The pilot AWS application-log retention period is 30 days. Other data categories use service-specific retention until the final production retention schedule is approved and implemented.

The final schedule must address at least active account data, planning content, audit history, deleted accounts, AI operational metadata, application logs, database backups, export artifacts retained server-side if any, and incident/legal holds.

## 13. Vulnerability and incident handling

Suspected vulnerabilities and security events are handled under the TPP Incident Response Policy. Brau Consulting will investigate credible incidents, contain risk, preserve necessary evidence, coordinate with material providers, and provide notifications required by applicable law and contract.

## 14. Business continuity and recovery

TPP uses managed cloud infrastructure, but final production backup, restore, recovery-point, and recovery-time objectives are not represented as contractual commitments until tested and approved. Any customer-facing SLA or disaster-recovery commitment must match tested production capability.

## 15. Customer responsibilities

Customers and users are responsible for:
- keeping credentials and endpoints secure;
- limiting access to authorized personnel;
- promptly removing access when personnel no longer require it;
- staying within the no-student-data boundary;
- reviewing AI-generated content before use;
- using lawful source materials and respecting intellectual-property rights;
- reporting suspected security incidents promptly.

## 16. Security review contact

[SECURITY CONTACT EMAIL TO BE APPROVED]

## Production-verification gate

Before external publication, verify: production AWS region/services; TLS and certificate state; Supabase project region and backup retention; RLS/authorization posture; authentication providers; OpenAI account/data-sharing configuration; secret path; log inventory and retention; backup/restore behavior; deletion procedures; incident contacts; vulnerability-reporting process; and all material subprocessors.
