# TPP Legal / Compliance Decisions Required Before Publication

**Provider:** Brau Consulting LLC  
**Status:** Internal decision register  
**Baseline:** 2026-08-14 company-contact reconciliation

This file identifies items that require Brau Consulting LLC approval, technical verification, or qualified legal review before the pre-release packet becomes effective or public.

## A. Company information now resolved

The following company-level information is supported by existing Brau Consulting / Guided Scholar business records and has been carried into the TPP Terms, Privacy Policy, and Institutional Services Agreement:

- Legal entity: Brau Consulting LLC
- Founder/principal: Peter Brau
- Public business/mailing address: 9570 County Road 19, Centre, AL 35960, United States
- Current public business contact email: peter@brauconsulting.com
- Current business phone: 423-557-1958

These are company-level facts, not Guided Scholar product terms. Guided Scholar student-specific, FERPA, COPPA, student-data, or product-specific provisions are not imported into TPP.

### 1. Future role-based contact aliases

Before public launch, Brau Consulting may choose to establish separate monitored aliases for general support, privacy requests, security reports, legal/contract notices, and accessibility feedback. Until such aliases are approved and operational, the verified public business contact above is the packet contact.

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

## C. Decisions to make after development/architecture verification

### 4. Retention schedule
Approve numerical retention only after implementation evidence exists for:
- active planning content;
- account termination;
- audit/version history;
- AI operational metadata;
- authentication/security records;
- database backups;
- exports retained server-side, if any.

Current verified numerical setting: AWS application logs = 30 days.

### 5. Post-termination export/deletion window
Choose the standard customer export window and deletion schedule after confirming the product can reliably perform it.

### 6. Final subprocessor list
Confirm deployed production vendors and configurations, including AWS, Supabase, OpenAI, and any later DNS/email/support/monitoring/analytics/payment providers that process customer/account data.

### 7. Accessibility evidence
Complete and retain explicit WCAG 2.1 Level AA evidence for covered public-school workflows and applicable generated documents. WCAG 2.2 may be tested additionally.

## D. Qualified legal review required

### 8. Terms of Use
Counsel should review:
- limitation of liability;
- individual-user indemnification;
- warranty disclaimers;
- governing law/venue;
- whether arbitration or a jury waiver is appropriate;
- enforceability/acceptance mechanism.

### 9. Institutional Services Agreement
Counsel should review:
- public-school/government contracting restrictions;
- indemnity limitations;
- appropriations/non-appropriation issues if applicable;
- governing law and venue;
- insurance requirements if requested;
- confidentiality/public-records interaction;
- liability caps and exclusions;
- breach-notification contractual language.

### 10. Privacy and incident obligations
Counsel should confirm the final public Privacy Policy and incident notification language against the actual customer/data footprint and applicable law.

### 11. Accessibility
For public-school contracting, counsel/procurement review should confirm how the DOJ Title II web/mobile accessibility rule applies to the specific customer and contract, including generated PDFs and any claimed exceptions.

## E. Not currently required because of the locked product boundary

Unless the product scope changes, the packet does not create a student-data workflow, COPPA parental-consent workflow, FERPA student-record processing agreement, student DPA, parent portal terms, or child-account terms.

If TPP later proposes student accounts or student records, stop ordinary feature development and reopen the legal/security architecture before implementation.

## F. Merge vs publication

This governance packet may be merged into the repository while still marked pre-release so development can follow it. **Merge does not make the Terms or policies legally effective or public.** Publication/effective status is a separate approval gate after the decisions and verification above are complete.
