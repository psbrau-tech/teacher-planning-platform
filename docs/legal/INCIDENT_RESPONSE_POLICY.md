# Teacher Planning Platform — Incident Response Policy

**Provider:** Brau Consulting LLC  
**Status:** Internal Pre-Release Governance Draft  
**Baseline:** 2026-08-08

This policy governs response to suspected or confirmed security, privacy, data-boundary, credential, availability, or integrity incidents affecting Teacher Planning Platform (TPP).

## 1. Objectives

Incident response must prioritize:
1. protection of users, customer organizations, and Brau Consulting systems;
2. containment of unauthorized access, data exposure, or integrity loss;
3. preservation of sufficient evidence for diagnosis and required notification;
4. restoration of safe service;
5. timely legal/contractual assessment and communication;
6. root-cause correction and prevention of recurrence.

## 2. Incident categories

Examples include:
- unauthorized account or privileged access;
- exposed, leaked, or misused credentials/API keys;
- prohibited student data entering TPP;
- unauthorized disclosure, alteration, or deletion of customer content;
- cross-user or cross-organization authorization leakage;
- AI request leakage or unintended inclusion of prohibited data;
- malicious code, dependency compromise, or infrastructure compromise;
- significant availability or data-integrity failure;
- standards-source integrity compromise or unauthorized replacement of authoritative content;
- logging of secrets or other prohibited sensitive information;
- material vendor/subprocessor security event affecting TPP data.

## 3. Severity framework

### Critical
Active compromise, confirmed broad unauthorized access, exposed privileged credentials with active risk, material cross-tenant disclosure, destructive attack, or incident reasonably likely to cause serious harm or mandatory urgent notification.

### High
Confirmed unauthorized access or disclosure with limited scope, compromised non-public credentials, prohibited student data propagated to multiple systems/providers, or material integrity failure affecting governed planning records.

### Medium
Contained security/control failure without confirmed unauthorized disclosure, limited accidental sensitive submission, or vulnerability with meaningful exploit potential.

### Low
Security observation, unsuccessful attempt, minor configuration issue, or low-risk defect with no evidence of unauthorized access or material data impact.

Severity may change as investigation develops.

## 4. Response roles

Until Brau Consulting assigns a larger incident team, the designated TPP incident lead coordinates technical containment, evidence, customer communication, vendor escalation, and legal review. The same person should not make irreversible evidence-destroying changes before preserving the minimum evidence needed for diagnosis unless immediate containment requires it.

**Publication/operations blocker:** designate primary and alternate incident contacts and maintain current phone/email escalation information outside the public repository where appropriate.

## 5. Response process

### A. Detect and record
Create an incident record with discovery time, reporter, systems affected, initial symptoms, suspected data categories, current severity, and containment status. Do not paste secrets or unnecessary sensitive content into the incident ticket.

### B. Contain
As appropriate:
- revoke sessions or disable affected accounts;
- rotate exposed credentials/keys;
- isolate affected workloads or integrations;
- stop a vulnerable deployment or AI route;
- disable exports or features causing leakage;
- block unauthorized network or application access;
- prevent additional prohibited data processing.

### C. Preserve evidence
Preserve relevant logs, request IDs, timestamps, deployment/image identifiers, database audit records, provider incident notices, and configuration state. Minimize copying of customer content and prohibited data.

### D. Investigate
Determine root cause, start/end time, systems and providers involved, accounts/data affected, whether information was actually acquired or merely exposed, persistence mechanisms, and whether the issue remains exploitable.

### E. Eradicate and recover
Remove malicious or unsafe conditions, patch or roll back affected code/configuration, rotate secrets, restore known-good state, reconcile data integrity, and verify authorization boundaries before returning affected functionality to normal use.

### F. Notify and coordinate
Assess obligations under applicable law, customer agreements, insurance requirements, and provider contracts. Use qualified legal counsel for notification decisions where appropriate.

### G. Post-incident review
Document root cause, timeline, impact, corrective actions, owner, verification evidence, and policy/code/test changes. Add regression tests or release checks when feasible.

## 6. Alabama legal review trigger

Brau Consulting is an Alabama provider and must evaluate the Alabama Data Breach Notification Act of 2018 when an event involves covered sensitive personally identifying information. The Act includes duties concerning reasonable security measures, breach investigation, notification to affected individuals, notification to the Attorney General in specified circumstances, third-party-agent notices, and disposal.

The existence of a security event does not automatically mean statutory notice is required. Applicability depends on the data, acquisition, harm/risk analysis, relationship of the parties, and other facts. Legal counsel should be consulted for a potentially reportable breach.

## 7. Prohibited student-data event

Because TPP is not intended to process student data, discovery of identifiable student information is itself a governance event even if there is no external attacker.

Response should determine:
- source and user action that introduced the data;
- whether it reached the database, logs, AI provider, exports, backups, or support systems;
- whether access was limited to authorized personnel or disclosed more broadly;
- whether the customer organization must be notified;
- what active copies can be safely deleted;
- what technical/UI safeguard should prevent recurrence.

Do not normalize student data into the ordinary TPP retention lifecycle.

## 8. Vendor incidents

When AWS, Supabase, OpenAI, or another material provider reports an incident that may affect TPP, create an internal incident record, determine TPP exposure, preserve vendor communications, and follow contractual/provider escalation channels.

## 9. Communications

External incident communications must be factual, scoped to verified information, and updated as facts change. Do not speculate about impact, attackers, or legal obligations. Preserve copies of material customer and regulator communications.

## 10. Testing and maintenance

Before general release, conduct at least one tabletop exercise covering:
- exposed credential;
- cross-account authorization defect;
- accidental student-data submission reaching an AI request;
- provider outage or incident;
- restoration/rollback path.

Review this policy at least annually and after any material incident or architectural change.
