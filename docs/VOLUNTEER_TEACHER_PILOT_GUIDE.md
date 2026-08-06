# TPP Volunteer Teacher Pilot Guide

## Pilot purpose

The Teacher Planning Platform pilot is designed to reduce repetitive weekly lesson-plan preparation while preserving teacher judgment. The volunteer teacher will use synthetic curriculum and planning content to validate the complete Friday planning cycle before full-school rollout is considered.

## Data boundary

This pilot contains teacher and curriculum information only.

Do not enter:

- student names or IDs;
- grades or assessment results tied to named students;
- IEP, 504, medical, behavioral, or accommodation information;
- student rosters or parent information;
- any other student-specific data.

## Before the session

The pilot coordinator confirms that:

- the volunteer teacher's exact `anniston.k12.al.us` Google account is active in the governed access list;
- the account has only the approved `teacher` role unless another role was explicitly authorized;
- `https://planner.guidedscholar.ai` loads without a certificate warning;
- the deployed commit, image digest, and task-definition revision are recorded;
- the **Verify TPP Pilot Deployment** workflow passed;
- browser acceptance evidence will be stored in the protected pilot record.

## Suggested synthetic test content

Use content that is realistic enough to test the workflow but is not copied from a student record.

- Curriculum: `Pilot English 10 Curriculum`
- Assignment: `English 10 — Period 2`
- Week: the next instructional Monday through Friday
- Lessons: five synthetic lessons with a clear instructional sequence
- Calendar exception: one synthetic assembly, testing period, or missed instructional day
- Literacy Standards: a nonblank synthetic standards entry
- ACT Preparation: a nonblank synthetic preparation entry

## Sign-in

1. Open `https://planner.guidedscholar.ai`.
2. Select Google sign-in.
3. Use the approved school account.
4. Confirm that teacher planning controls are available.
5. Confirm that Platform Owner or administrator-only controls are not available unless explicitly approved.

Stop and notify the coordinator if:

- the site displays a certificate warning;
- the wrong account is selected;
- the account is denied even though it is approved;
- the account receives roles that were not approved;
- any student-data feature appears.

## Pilot workflow

### 1. Curriculum

1. Create or import the synthetic sequenced curriculum.
2. Add several lessons in the intended order.
3. Save and reload the curriculum.
4. Confirm the exact lesson order persists.

### 2. Teaching assignment

1. Create the synthetic teaching assignment.
2. Select the intended curriculum.
3. Configure the normal meeting pattern.
4. Record actual instructional minutes.
5. Save and reopen the assignment.

Repeat with a second synthetic assignment if time permits. Confirm that changing one assignment does not change the other.

### 3. Generate the week

1. Select the teaching assignment.
2. Select the target week.
3. Generate the weekly plan.
4. Confirm that lessons follow the curriculum sequence and meeting pattern.
5. Add the synthetic calendar exception.
6. Confirm that only the affected instructional day changes.

### 4. Complete required planning fields

Complete and save:

- daily tasks and instructional activities;
- instructional resources;
- Literacy Standards;
- ACT Preparation;
- any required teacher notes or reflection fields.

Close the browser, reopen the site, and confirm that the latest saved draft reloads exactly.

### 5. Export the Anniston documents

Export and visually inspect:

1. Instructional Framework;
2. Week at a Glance;
3. Weekly Reflection;
4. combined packet.

Confirm:

- correct teacher, course, and week identifiers;
- correct document order;
- readable text;
- no silent truncation;
- continuation pages are clearly labeled;
- Anniston branding is intact;
- Literacy Standards and ACT Preparation appear where expected.

### 6. Friday validation

Mark different synthetic lessons as:

- completed;
- modified;
- missed;
- skipped.

Add the required note or reason where applicable. Finalize Friday validation and reopen the week to confirm the statuses persist.

### 7. Carry forward missed instruction

Generate the following week. Confirm that:

- missed instruction carries forward in sequence;
- completed instruction is not repeated improperly;
- unrelated assignments and curricula are unchanged.

## Feedback prompts

After completing the workflow, answer:

1. Which step saved the most time compared with the current process?
2. Which step required the most explanation?
3. Was any label or action unclear?
4. Did the generated schedule match how your course actually meets?
5. Did the calendar exception behave as expected?
6. Were Literacy Standards and ACT Preparation easy to complete and locate?
7. Were the exported documents ready to submit without manual reformatting?
8. Did Friday validation accurately reflect what happened during the week?
9. Did carry-forward place missed instruction where you expected it?
10. What would prevent you from using this every Friday?
11. What should be corrected before another teacher uses it?

## Defect reporting

For any problem, record:

- the acceptance test or workflow step;
- exact steps taken;
- expected result;
- actual result;
- browser and device;
- approximate time;
- redacted screenshot when useful;
- whether the problem blocks continued testing.

Do not include access tokens, account addresses in unprotected artifacts, student information, staff access-list JSON, or other secrets.

## Completion standard

The volunteer-teacher pilot is complete when the teacher can independently:

- sign in;
- select or import curriculum;
- configure an assignment and schedule;
- generate and revise a week;
- complete required planning fields;
- save and reopen a draft;
- export all approved documents;
- perform Friday validation;
- carry missed instruction forward;
- explain whether the platform is usable for the normal weekly planning cycle.
