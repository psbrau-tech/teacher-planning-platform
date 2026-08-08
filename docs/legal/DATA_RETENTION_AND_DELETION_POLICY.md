# Teacher Planning Platform — Data Retention & Deletion Policy

**Provider:** Brau Consulting LLC  
**Status:** Internal Pre-Release Governance Draft  
**Baseline:** 2026-08-08

This policy defines the retention/deletion framework that TPP implementation and customer-facing promises must follow. It intentionally distinguishes verified current settings from retention periods that still require approval and implementation.

## 1. Principles

TPP will:
- minimize collection to permitted professional data necessary for the service;
- not intentionally collect student personally identifiable information or student education records;
- retain data only for a documented operational, security, contractual, legal, or customer purpose;
- avoid publishing deletion promises that have not been technically verified;
- distinguish active data, soft-deleted data, backups, logs, audit records, and legal/security holds;
- document exceptions rather than silently retaining data beyond policy.

## 2. Current verified retention

| Data category | Current verified setting | Status |
|---|---:|---|
| AWS pilot application logs | 30 days | Verified from current pilot infrastructure configuration |

No other numerical retention period is approved by this policy solely because a vendor default exists.

## 3. Retention schedule requiring implementation approval

Before general release, Brau Consulting must approve and TPP must technically implement/test the following schedule categories:

| Category | Required decision |
|---|---|
| Active educator/admin account profile | Retain while account/institutional relationship is active plus approved post-termination period |
| Curriculum and lesson-planning content | Customer-controlled active retention plus approved post-termination export/deletion period |
| Teaching schedules and planning exceptions | Align with planning-content lifecycle and audit needs |
| Saved standards selections/source snapshots | Preserve sufficient provenance for historical plan integrity; define archival period |
| Plan/version/audit history | Define minimum audit period and deletion behavior after account/institution termination |
| AI request operational metadata | Define bounded operational/cost/audit period; avoid unnecessary prompt/body duplication |
| Authentication/security events | Define security retention consistent with detection/investigation needs |
| Database backups | Define backup retention/cycling and treatment of deleted records |
| Generated exports | Prefer transient generation unless server-side retention is intentionally required; verify implementation |
| Support records | Define business/support retention and delete sensitive attachments when no longer necessary |
| Incident evidence/legal hold | Retain only while incident, legal, insurance, or contractual need remains |

## 4. Account and institutional termination

The final implementation must support a documented sequence:
1. disable or revoke user access;
2. provide any contractually required export opportunity;
3. delete or anonymize active content after the approved period unless retention is required;
4. allow backups to cycle according to documented backup retention rather than attempting unsafe ad hoc backup editing;
5. preserve only records required for security, financial, contractual, legal, or dispute purposes;
6. document completion when required by an institutional agreement.

## 5. Accidental prohibited student data

If student information enters TPP contrary to policy:
- do not treat it as normal customer content;
- contain further access/processing;
- identify where the data propagated, including AI requests, logs, database records, exports, and backups as applicable;
- delete or remediate active copies as soon as reasonably safe and lawful;
- assess whether the event constitutes a security/privacy incident requiring customer or legal notification;
- preserve only the minimum incident evidence necessary without unnecessarily reproducing the prohibited content.

## 6. Deletion requests

Deletion requests must be authenticated and evaluated against institutional ownership/administration, contract, legal obligations, security needs, and technical backup behavior. For institution-managed accounts, the authorized institutional administrator may control or need to approve deletion of institutional content.

## 7. Logs and secrets

Secrets, access tokens, passwords, API keys, and service-role credentials must not be intentionally logged. If discovered in logs, treat the event as a security incident, rotate affected secrets where appropriate, and remediate the logged copies according to incident procedures.

## 8. Backups

Backup retention must be documented before publication of any deletion SLA. Deleted active records may remain in immutable or managed backups until the backup expires. Restoring a backup must not silently reintroduce deleted content into active use without reconciliation.

## 9. Legal and security holds

A documented legal, regulatory, insurance, contractual, fraud, abuse, or security-investigation need may temporarily suspend ordinary deletion for the minimum relevant records. Holds must be scoped and released when no longer necessary.

## 10. Change control

Any change to retention periods must be reviewed for impact on the Privacy Policy, institutional agreement, security overview, database/infrastructure settings, backup configuration, and customer commitments.

## Release blocker

General release must not occur with numerical public deletion promises until the schedule above is approved, implemented, and verified end-to-end.
