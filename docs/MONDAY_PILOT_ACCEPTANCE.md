# Monday Pilot Acceptance Gate

TPP is ready for volunteer-teacher use only when every P0 item below is verified in the deployed pilot environment.

## Access and data boundary

- Google SSO accepts an approved, verified school account.
- Unapproved accounts are denied.
- The pilot contains teacher, course, curriculum, schedule, standards, and planning data only.
- The interface warns teachers not to enter student names, IDs, grades, IEP data, or other student-specific information.

## Teacher setup

- A teacher can create at least one teaching assignment.
- A teacher can configure period, block, or mixed meeting patterns.
- Multiple teaching assignments remain independent.
- A teacher can import or manually enter a sequenced curriculum.

## Weekly planning

- The planner excludes noninstructional calendar dates.
- Scheduling uses available instructional minutes.
- Long lessons split only when the curriculum permits splitting.
- A teacher can edit and save a weekly draft.
- Stale edits are rejected through revision protection.
- A teacher can reopen the saved draft without losing content.

## Friday validation

- Every scheduled lesson can be marked completed, modified, missed, or skipped.
- Missed lessons require a reason.
- Carry-forward decisions preserve curriculum order.
- Generating the next week does not change unrelated assignments.

## Documents

- The Anniston theme uses the approved header: `Anniston City Schools — Instructional Planning Framework`.
- The footer reads: `Prepared with Teacher Planning Platform`.
- The approved ACS/Bulldog logo appears when the production asset is installed.
- A neutral placeholder appears when no district logo is installed.
- Instructional Framework, Week at a Glance, and Weekly Reflection download separately.
- The combined packet preserves that order.
- Text wraps, sections expand, and pages flow without truncation or unreadable shrink-to-fit.
- Teacher approval is required before final export.

## Reliability and operations

- Backend lint, strict typing, and tests pass.
- Frontend production build passes.
- Health endpoint responds successfully.
- Runtime secrets are loaded from AWS Secrets Manager and are not exposed by API responses or logs.
- Application logs provide enough context to diagnose authentication, save, generation, and export failures without logging secret values.

## Pilot handoff

- Volunteer teacher accounts or allowed domains are configured.
- Pilot URL is `https://planner.guidedscholar.ai`.
- A feedback channel is published.
- Known limitations are shared with pilot teachers.
- A rollback path exists for the deployed service.
