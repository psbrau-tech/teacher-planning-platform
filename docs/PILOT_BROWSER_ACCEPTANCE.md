# TPP Controlled Pilot Browser Acceptance

## Boundary

- Teacher and curriculum data only.
- No student names, IDs, grades, accommodations, rosters, or student accounts.
- Use only approved `anniston.k12.al.us` staff accounts.
- Record the exact deployed commit, image digest, ECS task-definition revision, and acceptance date.

## Evidence record

For each step, capture:

- tester role;
- browser and device;
- UTC and America/Chicago timestamps;
- expected result;
- observed result;
- pass, fail, or blocked;
- screenshot reference when useful, excluding secrets and protected access-list contents;
- defect link when failed.

## Platform Owner acceptance

Confirm in one authenticated session that the governed Platform Owner account:

1. authenticates through the approved Google school account;
2. receives both Platform Owner and Teacher navigation and capabilities;
3. can access administrative configuration without losing teacher access;
4. cannot access any student-data feature because none exists in the pilot boundary;
5. can create or select teacher curriculum and planning records;
6. can export each approved Anniston document and the combined packet.

## School administrator acceptance

Confirm that an approved `school_admin` account:

1. authenticates successfully;
2. sees school-administrator capabilities but not Platform Owner-only controls;
3. can review governed teacher access and school-level configuration exposed by the application;
4. cannot assume teacher capabilities unless the access list explicitly grants `teacher`;
5. cannot access any unapproved school or student information.

## Volunteer teacher acceptance

Confirm that an approved `teacher` account can:

1. authenticate through Google SSO;
2. see only teacher capabilities;
3. import or select a sequenced curriculum;
4. configure independent teaching assignments;
5. configure period, block, selected-weekday, and custom meeting patterns;
6. generate a week using actual instructional minutes and calendar exceptions;
7. save and reopen a weekly draft;
8. complete required Literacy Standards and ACT Preparation fields;
9. export the Instructional Framework, Week at a Glance, Weekly Reflection, and combined packet;
10. validate lessons as completed, modified, missed, or skipped;
11. carry missed instruction into the next week without changing unrelated curricula;
12. observe the teacher-and-curriculum-only boundary throughout the workflow.

## Negative authorization checks

Verify that:

- an authenticated but unapproved school account receives no governed profile or application data;
- a non-Anniston account cannot enter the pilot;
- a teacher cannot open Platform Owner or administrator-only controls;
- an administrator without `teacher` cannot open teacher-only planning records;
- direct unauthenticated API requests return an authentication failure;
- no secret, connection string, access-list JSON, or service-role value appears in browser responses or exported files.

## Acceptance disposition

The pilot is accepted only when:

- every required scenario passes;
- all blocking defects are resolved and retested;
- deployed provenance is recorded;
- Platform Owner dual-role concurrency is confirmed;
- administrator and volunteer-teacher acceptance are complete;
- the teacher-and-curriculum-only boundary remains intact.
