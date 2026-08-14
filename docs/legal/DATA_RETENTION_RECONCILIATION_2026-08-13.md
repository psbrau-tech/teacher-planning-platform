# TPP Data Retention Reconciliation Addendum

**Provider:** Brau Consulting LLC  
**Date:** 2026-08-13  
**Status:** Internal pre-release governance addendum

This addendum supplements `DATA_RETENTION_AND_DELETION_POLICY.md` after deployment of the controlled pilot. It does not replace that policy and does not create a new public deletion promise.

## Verified numerical setting

The currently verified controlled-pilot application-log retention period is **30 days** in AWS CloudWatch Logs.

No other numerical retention period is approved solely because a vendor default exists.

## Implemented data categories now requiring final retention decisions

The deployed service now makes the following retention categories concrete:

- educator/admin account and role records;
- curriculum, pacing, schedules and lesson-planning content;
- standards selections, source snapshots, provenance and reconciliation records;
- weekly validation, reflection, submission and completed-packet records;
- plan/version/audit history;
- AI usage/cost metadata and educator suggestion-decision records;
- authentication/security records;
- first-party product-usage and active-interaction heartbeat events;
- database backups;
- generated exports if any are retained server-side;
- support records;
- incident/legal-hold evidence.

## Product analytics retention

On 2026-08-13 Brau Consulting approved bounded first-party active-interaction telemetry for Platform Owner product-effectiveness analysis. Before general release, the retention schedule should explicitly determine:

- raw heartbeat-event retention;
- aggregate/report retention;
- whether and when records are aggregated or de-identified;
- deletion behavior after account/institution termination;
- whether any longer-term product-study record has a documented legitimate purpose.

The telemetry must not be retained indefinitely merely because storage is available, and must not be repurposed into teacher-performance monitoring without a new governance/privacy review.

## Termination/deletion sequence requiring implementation verification

Before any public deletion SLA is stated, the service should verify an end-to-end sequence that can:

1. disable/revoke account access;
2. provide any contractually required export opportunity;
3. remove or anonymize active content after the approved period;
4. preserve only records required for security, financial, contractual, legal, standards-integrity or dispute purposes;
5. allow managed backups to cycle according to a documented backup period;
6. prevent a later backup restore from silently resurrecting records that had been deleted from active use;
7. document completion where an institutional agreement requires it.

## Counsel question

Counsel should advise whether applicable school/public-sector contracting practice or law should drive any minimum or maximum retention periods, and what contract language is appropriate while Brau Consulting finalizes and tests the operational schedule.

## Publication rule

Until the above schedules are approved and technically verified, customer-facing documents may describe retention functionally but should not promise a numerical deletion period beyond the verified application-log setting.
