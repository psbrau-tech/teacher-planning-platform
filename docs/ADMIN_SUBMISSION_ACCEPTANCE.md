# TPP Admin Submission and District Reporting Acceptance

## Scope

This acceptance package covers the approved professional administrative enhancement:

- explicit teacher weekly-plan submission and resubmission;
- school-administrator weekly submission oversight;
- district-administrator district-scoped oversight;
- continued Platform Administrator operational controls;
- removal of UI language that implies student records are a supported TPP data object.

The locked TPP data boundary remains unchanged: educator/admin account information and professional curriculum, standards, schedule, lesson-plan, validation, reflection, export, reporting, and related operational data only. Do not use student data during testing.

## Role model

| Role | Scope | Required behavior |
|---|---|---|
| `teacher` | Own professional planning work | Save, submit, revise, resubmit, validate, and export own plans |
| `school_admin` | One governed school | Read submission status and professional planning reporting for that school only |
| `district_admin` | Governed district | Read submission status across schools in the same district only; no school-management write authority is implied |
| `platform_admin` | Platform operations | Standards governance and platform-only reporting; governed submission reporting remains professional data only |

## Submission lifecycle

| State | Expected result |
|---|---|
| Saved but never submitted | `Not submitted` / draft |
| Explicit teacher submission | `Submitted` with submission timestamp |
| Edit after submission | `Revised after submission`; official exports disabled until resubmission |
| Explicit resubmission | `Submitted` again with refreshed submission timestamp |
| Stale-revision submission | Rejected; newer work is not overwritten |

## Teacher acceptance

1. Save a synthetic weekly plan and confirm it is visibly not submitted.
2. Submit the saved revision and confirm visible `Submitted` state.
3. Confirm official HQI export controls are available only for the current submitted revision.
4. Edit and save one field after submission; confirm status changes to `Revised after submission`.
5. Confirm official export controls are disabled until resubmission.
6. Resubmit and confirm `Submitted` state returns.
7. Reopen the week and confirm the current submission state and timestamp persist.
8. Attempt a stale revision save/submission where reproducible; confirm it is rejected.

## School Administrator acceptance

1. Sign in with a governed `school_admin` identity.
2. Confirm teacher planning tabs are absent unless that identity separately holds `teacher`.
3. Open Administration and select a target week.
4. Confirm each active teacher/course in the school has a status: submitted, revised after submission, draft/not started, or no active course.
5. Confirm submission timestamp and generated-document count are visible when applicable.
6. Confirm records from another school are not returned.
7. Confirm Platform Administrator-only standards governance and AI cost controls are absent.

## District Administrator acceptance

1. Sign in with a governed `district_admin` identity.
2. Confirm Administration is available without teacher workflow controls unless separately authorized.
3. Select a week and confirm professional submission status is visible across schools in the same district.
4. Confirm the school name is visible for each teacher/course record.
5. Confirm a school outside the governed district cannot be queried or returned.
6. Confirm district reporting is read-only and does not grant school calendar/curriculum management writes.
7. Confirm Platform Administrator-only standards governance and AI cost controls are absent.

## Platform Administrator regression

1. Confirm concurrent `platform_admin + teacher` behavior still works for the Platform Owner.
2. Confirm Platform Administrator standards-governance and AI cost controls remain available.
3. Confirm weekly submission reporting contains professional educator data only.
4. Confirm no service-role/database/OAuth credentials are exposed to the browser.

## Data-boundary/UI regression

1. Confirm the prior `0 student records` dashboard metric is removed.
2. Confirm boundary language states that TPP uses teacher/curriculum/professional planning data only without implying a student-record module exists.
3. Confirm no student roster, grade, IEP/504, identifiable student work, or student analytics field has been introduced.
4. Confirm exported documents contain only the teacher-approved submitted professional plan.

## Release decision

This enhancement may be accepted only when role-isolation tests pass at both API and browser layers, district reporting cannot cross the governed district, a stale revision cannot overwrite or submit newer work, official exports require the current submitted revision, and no student-data capability is introduced.
