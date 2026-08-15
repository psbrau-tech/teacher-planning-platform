# TPP Legal / Compliance Decisions Required Before Publication

**Provider:** Brau Consulting LLC  
**Status:** Internal decision register  
**Baseline:** 2026-08-14 product/legal reconciliation

This file identifies items that require Brau Consulting LLC approval, technical verification, or qualified legal review before the pre-release packet becomes effective or public.

## A. Company and product information now resolved

The following company-level information is supported by existing Brau Consulting / Guided Scholar business records and has been carried into the TPP Terms, Privacy Policy, and Institutional Services Agreement:

- Legal entity: Brau Consulting LLC
- Founder/principal: Peter Brau
- Public business/mailing address: 9570 County Road 19, Centre, AL 35960, United States
- Current public business contact email: peter@brauconsulting.com
- Current business phone: 423-557-1958

These are company-level facts, not Guided Scholar product terms. Guided Scholar student-specific, FERPA, COPPA, student-data, or product-specific provisions are not imported into TPP.

The following TPP product decision is also resolved for the notification work:

- Approved application From address for governed professional operational email: `notifications@planner.guidedscholar.ai`.

Approval of the address does not establish that AWS SES is verified/active or that scheduled delivery is enabled.

### 1. Future role-based contact aliases

Before public launch, Brau Consulting may choose to establish separate monitored aliases for general support, privacy requests, security reports, legal/contract notices, and accessibility feedback. Until such aliases are approved and operational, the verified public business contact above is the packet contact.

The TPP notification From address is an application sender identity and should not silently be treated as the legal/privacy/security contact unless Brau Consulting separately approves and monitors it for that purpose.

## B. Decisions Brau Consulting can make before commercial launch

### 2. Commercial model
Before paid use, approve:
- individual vs institutional purchasing model;
- invoice/payment due date;
- subscription or fixed-term model;
- auto-renewal or affirmative renewal;
- cancellation/refund terms if applicable;
- pilot-to-paid conversion terms.

### 3. Incident contacts
Designate a primary and alternate incident lead and maintain a private escalation method. The public business contact does not replace the need for a private incident-escalation roster.

### 4. Automatic weekly notification schedule
Before the scheduled school-admin digest is enabled, explicitly approve:
- the exact weekly EventBridge Scheduler cron expression;
- the school-local IANA timezone;
- whether the initial automatic recipient scope remains active `school_admin` accounts only;
- any suppression/holiday/week-with-no-instruction behavior desired before broader rollout.

The source-controlled activation path intentionally requires a human to supply and approve the schedule rather than embedding a guessed delivery time.

## C. Decisions to make after development/architecture verification

### 5. Retention schedule
Approve numerical retention only after implementation evidence exists for:
- active planning content;
- account termination;
- audit/version history;
- AI operational metadata;
- Reflection Intelligence/product-adoption metadata;
- professional notification-delivery records;
- authentication/security records;
- database backups;
- exports retained server-side, if any.

Current verified numerical setting: AWS application logs = 30 days.

The current PLC facilitation workspace is transient and does not create a retained PLC action-note store. If later development persists PLC action items, theme lifecycle state, named owners, or team notes, reopen retention/access decisions before activation.

### 6. Post-termination export/deletion window
Choose the standard customer export window and deletion schedule after confirming the product can reliably perform it.

### 7. Final subprocessor list and notification provider configuration
Confirm deployed production vendors and configurations, including AWS, Supabase, OpenAI, and any later DNS/email/support/monitoring/analytics/payment providers that process customer/account data.

For the source-controlled Amazon SES path specifically, verify before activation/publication:
- the exact verified email/domain identity in `us-east-2`;
- SES account sending status for intended professional recipients;
- least-privilege IAM scope;
- the runtime From address;
- any applicable service-level data/retention/configuration choices;
- whether customer agreements require subprocessor-change notice.

### 8. Scheduled-worker credential and deployment evidence
Before automatic digest delivery is enabled, verify:
- the scheduled-digest database migration is applied and accepted;
- the Supabase service-role key exists in its own governed AWS Secrets Manager path;
- the interactive web task does not receive the service-role credential;
- the scheduled worker receives only the approved minimum secret set;
- live GitHub deployment-role and CloudFormation execution-role policies match the accepted source-controlled least-privilege policies;
- the scheduled worker uses an accepted immutable application image.

### 9. Accessibility evidence
Complete and retain explicit WCAG 2.1 Level AA evidence for covered public-school workflows and applicable generated documents. WCAG 2.2 may be tested additionally.

The printable PLC facilitation artifact should be included in the applicable accessibility/document review rather than assumed exempt.

## D. Qualified legal review required

### 10. Terms of Use
Counsel should review:
- limitation of liability;
- individual-user indemnification;
- warranty disclaimers;
- governing law/venue;
- whether arbitration or a jury waiver is appropriate;
- enforceability/acceptance mechanism.

### 11. Institutional Services Agreement
Counsel should review:
- public-school/government contracting restrictions;
- indemnity limitations;
- appropriations/non-appropriation issues if applicable;
- governing law and venue;
- insurance requirements if requested;
- confidentiality/public-records interaction;
- liability caps and exclusions;
- breach-notification contractual language.

### 12. Privacy and incident obligations
Counsel should confirm the final public Privacy Policy and incident notification language against the actual customer/data footprint and applicable law.

Counsel should also review the professional-email data flow, including whether automated operational admin notices require any additional institutional notice, suppression, recordkeeping, or contractual treatment.

### 13. Professional-learning / personnel-evaluation boundary
Counsel should review whether additional contractual or public-facing language is advisable to distinguish:
- post-submission Reflection Intelligence;
- anonymous aggregate school PLC themes;
- planned formative-assessment analytics; and
- Platform Owner product-adoption/active-time analytics

from formal teacher evaluation, personnel ranking, employment decision, or student-outcome systems.

The product governance currently prohibits TPP from presenting these signals as teacher-quality, effort, productivity, ranking, or personnel-performance scores.

### 14. AI provisions
Counsel should review the distinction between:
- AI-assisted planning drafts that remain educator-controlled; and
- post-submission Reflection Intelligence generated from already teacher-authored professional reflections.

The 12 required Weekly Reflection / PLC Discussion responses themselves remain teacher-authored; AI suggestion, generation, completion, or rewriting of those required responses is disabled by design.

### 15. Accessibility
For public-school contracting, counsel/procurement review should confirm how the DOJ Title II web/mobile accessibility rule applies to the specific customer and contract, including generated PDFs, printable PLC artifacts, and any claimed exceptions.

## E. Not currently required because of the locked product boundary

Unless the product scope changes, the packet does not create a student-data workflow, COPPA parental-consent workflow, FERPA student-record processing agreement, student DPA, parent portal terms, or child-account terms.

Professional-learning analytics and professional operational email do not change this boundary. If TPP later proposes student accounts, student records, student assessment results, or student-level analytics, stop ordinary feature development and reopen the legal/security architecture before implementation.

## F. Merge vs publication or activation

This governance packet may be merged into the repository while still marked pre-release so development can follow it. **Merge does not make the Terms or policies legally effective or public.** Publication/effective status is a separate approval gate after the decisions and verification above are complete.

Likewise, merging source-controlled SES or scheduled-worker infrastructure does not verify a sender, apply a database migration, create/enable the EventBridge schedule, supply a service-role secret, or authorize email delivery. Those are separate controlled release actions.
