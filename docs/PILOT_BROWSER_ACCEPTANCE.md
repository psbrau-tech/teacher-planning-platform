# TPP Controlled Pilot Browser Acceptance

## Purpose

This package governs live browser acceptance for `https://planner.guidedscholar.ai` after:

- database migrations are applied;
- governed staff access is provisioned;
- the AWS pilot stack is stable;
- ACM is issued and attached;
- the `planner` DNS record resolves directly to the AWS load balancer;
- Supabase and Google OAuth settings are complete.

The acceptance boundary is teacher and curriculum data only. Do not enter student names, student IDs, grades, accommodations, IEP information, or other student-specific data.

## Required participants

| Persona | Required governed roles | Required evidence |
|---|---|---|
| Platform Owner | `platform_admin`, `teacher` | Same authenticated session visibly exposes both owner and teacher capabilities |
| School Administrator | `school_admin` | Administrator capabilities are available without teacher or platform-owner controls unless separately approved |
| Volunteer Teacher | `teacher` | Complete weekly planning, standards/AI assistance, validation, and export workflow |
| Unapproved school account | none | Authentication may succeed at the identity provider, but application authorization must be denied |
| Non-school account | none | School-domain restriction or authorization layer must deny access |

Use approved test accounts only. Do not write account addresses into screenshots, issue comments, PR comments, or public artifacts.

## Acceptance record

Complete one record for each test session.

| Field | Value |
|---|---|
| Acceptance date and local time | |
| Tester role | |
| Browser and version | |
| Operating system/device | |
| Application hostname | `planner.guidedscholar.ai` |
| Deployed commit | |
| Exact ECR image digest | |
| ECS task-definition ARN/revision | |
| Supabase migration status | |
| GitHub verification run | |
| Result | Pass / Fail / Blocked |
| Defect references | |

## Evidence rules

1. Capture only the minimum evidence required to prove the result.
2. Redact school-account email addresses when evidence will leave the protected acceptance record.
3. Do not capture access tokens, authorization headers, browser storage, Supabase keys, AWS account credentials, staff access-list JSON, or OpenAI API keys.
4. Use synthetic curriculum and planning content during acceptance.
5. Record the exact deployed image digest and task definition before beginning.
6. A failed test is not accepted because a later step happened to work; record the failure and retest after correction.
7. Do not combine Platform Owner, administrator, and teacher evidence into one persona unless the governed account intentionally holds the corresponding concurrent roles.
8. AI-assisted planning remains teacher-controlled: suggestions must not silently overwrite saved teacher content.
9. Current standards must be traceable to an authoritative source and version/effective date. Runtime planning must remain usable if the external standards source is temporarily unavailable.

## Gate A — Operational baseline

| ID | Test | Expected result | Evidence | Result |
|---|---|---|---|---|
| OPS-01 | Run **Verify TPP Pilot Deployment** with the deployed commit | Read-only workflow passes | Workflow run reference | |
| OPS-02 | Open `/health` through the public HTTPS hostname | HTTP 200 without a certificate warning | Timestamped result | |
| OPS-03 | Open the application root | Authenticated application shell loads from the same origin | Screenshot without account address | |
| OPS-04 | Confirm HTTP behavior | HTTP redirects to HTTPS after TLS attachment | Browser/network result | |
| OPS-05 | Confirm application logs | Current startup/request logs exist in the dedicated 30-day CloudWatch log group | Read-only verification summary | |

Stop acceptance if any operational baseline test fails.

## Gate B — Authentication and authorization

| ID | Persona/action | Expected result | Evidence | Result |
|---|---|---|---|---|
| AUTH-01 | Platform Owner signs in with approved Google school account | Sign-in succeeds | Redacted screenshot | |
| AUTH-02 | Inspect Platform Owner session | Both `platform_admin` and `teacher` capabilities are available | Redacted screenshot | |
| AUTH-03 | School Administrator signs in | Administrator capability is available | Redacted screenshot | |
| AUTH-04 | Volunteer Teacher signs in | Teacher workflow is available | Redacted screenshot | |
| AUTH-05 | Approved account signs out and signs back in | Governed identity and roles persist | Result note | |
| AUTH-06 | Unapproved `anniston.k12.al.us` account attempts access | Application denies authorization and exposes no planning data | Redacted result | |
| AUTH-07 | Non-school Google account attempts access | Access is denied | Redacted result | |
| AUTH-08 | Direct unauthenticated API request | Protected API returns HTTP 401 | HTTP result | |
| AUTH-09 | Teacher attempts administrator-only action | Action is absent or denied | Result note | |
| AUTH-10 | Administrator attempts Platform Owner-only action | Action is absent or denied | Result note | |

Any unauthorized data visibility is a release-blocking defect.

## Gate C — Curriculum and assignment setup

Use synthetic content such as `Pilot English 10 Curriculum`.

| ID | Action | Expected result | Evidence | Result |
|---|---|---|---|---|
| CURR-01 | Create or import a sequenced curriculum | Curriculum is saved and listed | Screenshot | |
| CURR-02 | Add multiple lessons in an intentional sequence | Lesson order persists after reload | Before/after evidence | |
| CURR-03 | Configure an independent teaching assignment | Assignment links to the intended curriculum | Screenshot | |
| CURR-04 | Configure a period/block pattern | Meeting days and minutes save correctly | Screenshot | |
| CURR-05 | Configure selected weekdays or custom pattern | Only selected instructional days are scheduled | Generated-week evidence | |
| CURR-06 | Create a second assignment using a different curriculum | Changes do not alter the first curriculum or assignment | Comparison note | |
| CURR-07 | Reload the browser session | Curricula and assignment setup persist | Screenshot | |

## Gate D — Weekly planning

Use the next approved instructional week and enter only synthetic instructional content.

| ID | Action | Expected result | Evidence | Result |
|---|---|---|---|---|
| PLAN-01 | Select an assignment and target week | Correct assignment and week are visible | Screenshot | |
| PLAN-02 | Generate the week | Lessons follow curriculum sequence, meeting pattern, and instructional minutes | Generated plan | |
| PLAN-03 | Apply a calendar exception or missed day | Exception affects only the intended day | Before/after comparison | |
| PLAN-04 | Complete `Literacy Standards` | Nonblank value saves and reloads | Screenshot | |
| PLAN-05 | Complete `ACT Preparation` | Nonblank value saves and reloads | Screenshot | |
| PLAN-06 | Edit daily tasks and resources | Edits persist after reload | Before/after evidence | |
| PLAN-07 | Save the weekly draft | Save succeeds with visible confirmation | Screenshot | |
| PLAN-08 | Close and reopen the browser | Latest saved draft reloads exactly | Comparison note | |
| PLAN-09 | Attempt an outdated revision save, when reproducible | Stale revision is rejected rather than overwriting newer work | Result note | |
| PLAN-10 | Work on the second assignment | First assignment remains unchanged | Comparison note | |

## Gate E — Authoritative standards and AI planning assistance

This is a release-blocking pilot gate. Use only the bounded pilot course set: Army JROTC LET 1–4, English 10, and Business Administration. Where Alabama publishes the applicable course standards, ingest from the current authoritative Alabama source. For curriculum governed by another authoritative issuer, retain equivalent source/version provenance and any approved Alabama/local mapping.

"Live standards" means the current authoritative standards are ingested into governed, refreshable snapshots. Weekly planning must not require the external standards website to be available at runtime.

| ID | Action | Expected result | Evidence | Result |
|---|---|---|---|---|
| STD-AI-01 | Import/refresh the current authoritative standards for a pilot course | Standard codes/text are stored with authoritative source, version/effective date, and retrieval provenance | Source/import record | |
| STD-AI-02 | Open a pilot teaching assignment | Only standards relevant to the mapped pilot course are offered; unrelated course standards do not appear | Screenshot | |
| STD-AI-03 | Select one or more standards for a target week and save/reopen | Selected standard code/text persist exactly and remain traceable to the source snapshot | Before/after evidence | |
| STD-AI-04 | Invoke AI planning assistance from selected standards | AI returns a teacher-reviewable draft grounded in the selected standards and existing curriculum/plan context | Screenshot/result note | |
| STD-AI-05 | Review AI breakdown of standards | Suggestions include useful learning targets and Know/Understand/Do components aligned to the selected standard text | Comparison note | |
| STD-AI-06 | Review additional HQI suggestions | Activities, assessments, resources, Literacy Standards/ACT connections where appropriate, and other suggested HQI fields remain visibly draft suggestions | Screenshot | |
| STD-AI-07 | Accept some AI suggestions, edit one, and reject one | Only teacher-approved/edited values enter the working plan; rejected suggestions do not overwrite teacher content | Before/after evidence | |
| STD-AI-08 | Complete Friday validation and invoke Weekly Reflection assistance | Reflection suggestion is grounded in the saved plan and validation outcome, is teacher-reviewable, and can be accepted/edited/rejected | Screenshot/result note | |
| STD-AI-09 | Inspect AI usage/cost evidence | Model/request usage and estimated cost are logged without exposing API keys, tokens, or student data | Redacted usage record | |
| STD-AI-10 | Force or simulate an AI-service failure | Clear bounded failure is shown; existing manual planning remains intact and usable with no partial overwrite | Result note | |
| STD-AI-11 | Inspect AI request boundary | Inputs contain only governed teacher/curriculum/standards/planning/validation context; no student-specific data is sent | Redacted review note | |
| STD-AI-12 | Temporarily make the external standards source unavailable or use the stored snapshot without refreshing | Previously ingested standards remain usable for weekly planning; refresh failure does not block existing standards use | Result note | |

Release-blocking defects include fabricated or altered standard text presented as authoritative, missing provenance, cross-course standards leakage, silent AI overwrite, student data entering AI requests, unbounded AI errors, or inability to plan when the external standards source is temporarily unavailable.

## Gate F — Anniston document exports

Use the accepted branded templates and inspect PDFs generated from the accepted standards/AI-assisted teacher-approved plan.

| ID | Export | Expected result | Evidence | Result |
|---|---|---|---|---|
| EXP-01 | Instructional Framework | Correct identifiers, selected standards, teacher-approved content, branding, and readable continuation pages | Export retained in protected evidence folder | |
| EXP-02 | Week at a Glance | Correct week, daily sequence, standards, ACT preparation, and branding | Export retained | |
| EXP-03 | Weekly Reflection | Correct identifiers and teacher-approved reflection fields | Export retained | |
| EXP-04 | Combined packet | Documents appear in the approved order without truncation | Export retained | |
| EXP-05 | Re-export after changing one field | New export contains the change and unrelated fields remain stable | Comparison note | |

Release-blocking export defects include silent truncation, wrong teacher/course/week identifiers, incorrect standards, unapproved AI draft text, unreadable text, missing required fields, broken branding, or incorrect packet order.

## Gate G — Friday validation and carry-forward

| ID | Action | Expected result | Evidence | Result |
|---|---|---|---|---|
| VAL-01 | Mark one scheduled lesson completed | Status persists | Screenshot | |
| VAL-02 | Mark one lesson modified and record the change | Status and note persist | Screenshot | |
| VAL-03 | Mark one lesson missed | Missed status persists | Screenshot | |
| VAL-04 | Mark one lesson skipped with reason | Status and reason persist | Screenshot | |
| VAL-05 | Finalize Friday validation | Validation snapshot saves with current revision | Confirmation | |
| VAL-06 | Generate the following week | Missed instruction carries forward in sequence | Week comparison | |
| VAL-07 | Inspect unrelated curriculum/assignment | Carry-forward did not change unrelated work | Comparison note | |
| VAL-08 | Reopen the validated week | Validation record and statuses reload | Screenshot | |

## Gate H — Data-boundary and failure behavior

| ID | Test | Expected result | Evidence | Result |
|---|---|---|---|---|
| SAFE-01 | Review visible labels and help text | Teacher-and-curriculum-only boundary is clear | Screenshot | |
| SAFE-02 | Search forms and exports for student-specific fields | No student roster, student account, named-student grade, or IEP field exists | Review note | |
| SAFE-03 | Trigger a validation error with incomplete required fields | Clear bounded error; no partial or corrupt save | Screenshot | |
| SAFE-04 | Refresh during normal editing | Last completed save remains intact | Result note | |
| SAFE-05 | Simulate temporary network loss before saving | User receives a clear failure and can retry without silent data loss | Result note | |
| SAFE-06 | Inspect browser console during primary workflows | No secret, access token, API key, or sensitive stack trace is logged | Redacted note | |

## Defect record

For every failed test, record:

| Field | Value |
|---|---|
| Defect ID | |
| Acceptance test ID | |
| Severity | Release blocker / High / Medium / Low |
| Persona | |
| Exact steps | |
| Expected result | |
| Actual result | |
| Deployed commit and image digest | |
| Browser/device | |
| Redacted evidence location | |
| Root cause | |
| Corrective PR | |
| Retest result | |

## Acceptance decision

The controlled pilot may proceed only when:

- all operational, authentication, curriculum/setup, weekly-planning, standards/AI-assistance, export, validation, and data-boundary gates pass;
- the bounded pilot standards set is current, traceable to authoritative source/version provenance, and usable from governed snapshots;
- AI suggestions are demonstrably teacher-invoked, teacher-controlled, logged for usage/cost, and constrained to teacher/curriculum data with no student data;
- no release-blocking or high-severity defect remains open;
- the Platform Owner dual-role session is verified;
- the unapproved-account denial is verified;
- the exact deployed image digest and task-definition revision are recorded;
- the volunteer teacher confirms the workflow is usable for the following Friday planning cycle.

Full-school rollout is a separate decision and requires pilot evidence, administrator approval, defect closeout, monitoring review, and explicit authorization.
