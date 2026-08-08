# TPP Legal / Compliance Decisions Required Before Publication

**Provider:** Brau Consulting LLC  
**Status:** Internal decision register  
**Baseline:** 2026-08-08

This file identifies items that require Brau Consulting LLC approval, technical verification, or qualified legal review before the pre-release packet becomes effective or public.

## A. Decisions Brau Consulting can make now

### 1. Public contact channels
Approve the public email addresses or aliases to use for:
- general support;
- privacy requests;
- security reports;
- legal/contract notices;
- accessibility feedback.

These may be separate aliases or route to the same managed inbox, but the published addresses must be actively monitored.

### 2. Public business mailing address
Approve the business mailing address Brau Consulting LLC wants published in the Terms, Privacy Policy, and institutional agreement. Do not publish a personal residence unless Brau Consulting intentionally chooses to use it as the company's public legal address.

### 3. Commercial model
Before paid use, approve:
- individual vs institutional purchasing model;
- invoice/payment due date;
- subscription or fixed-term model;
- auto-renewal or affirmative renewal;
- cancellation/refund terms if applicable;
- pilot-to-paid conversion terms.

### 4. Incident contacts
Designate a primary and alternate incident lead and maintain a private escalation method.

## B. Decisions to make after development/architecture verification

### 5. Retention schedule
Approve numerical retention only after implementation evidence exists for:
- active planning content;
- account termination;
- audit/version history;
- AI operational metadata;
- authentication/security records;
- database backups;
- exports retained server-side, if any.

Current verified numerical setting: AWS application logs = 30 days.

### 6. Post-termination export/deletion window
Choose the standard customer export window and deletion schedule after confirming the product can reliably perform it.

### 7. Final subprocessor list
Confirm deployed production vendors and configurations, including AWS, Supabase, OpenAI, and any later DNS/email/support/monitoring/analytics/payment providers that process customer/account data.

### 8. Accessibility evidence
Complete and retain explicit WCAG 2.1 Level AA evidence for covered public-school workflows and applicable generated documents. WCAG 2.2 may be tested additionally.

## C. Qualified legal review required

### 9. Terms of Use
Counsel should review:
- limitation of liability;
- individual-user indemnification;
- warranty disclaimers;
- governing law/venue;
- whether arbitration or a jury waiver is appropriate;
- enforceability/acceptance mechanism.

### 10. Institutional Services Agreement
Counsel should review:
- public-school/government contracting restrictions;
- indemnity limitations;
- appropriations/non-appropriation issues if applicable;
- governing law and venue;
- insurance requirements if requested;
- confidentiality/public-records interaction;
- liability caps and exclusions;
- breach-notification contractual language.

### 11. Privacy and incident obligations
Counsel should confirm the final public Privacy Policy and incident notification language against the actual customer/data footprint and applicable law.

### 12. Accessibility
For public-school contracting, counsel/procurement review should confirm how the DOJ Title II web/mobile accessibility rule applies to the specific customer and contract, including generated PDFs and any claimed exceptions.

## D. Not currently required because of the locked product boundary

Unless the product scope changes, the packet does not create a student-data workflow, COPPA parental-consent workflow, FERPA student-record processing agreement, student DPA, parent portal terms, or child-account terms.

If TPP later proposes student accounts or student records, stop ordinary feature development and reopen the legal/security architecture before implementation.

## E. Merge vs publication

This governance packet may be merged into the repository while still marked pre-release so development can follow it. **Merge does not make the Terms or policies legally effective or public.** Publication/effective status is a separate approval gate after the decisions and verification above are complete.
