# TPP Accepted Pilot Baseline — 2026-08-20

**Status:** Live accepted baseline  
**Environment:** TPP controlled Pilot  
**Hostname:** `planner.guidedscholar.ai`  
**AWS region:** `us-east-2`

## Exact accepted state

- Application `main` SHA: `b33bf905e98012b857c4434039fced08ff89137b`
- Applied database migration head: `20260820020000`
- Migration file: `20260820020000_fix_ai_suggestion_decision_actor_ambiguity.sql`
- Included release pull requests:
  - PR #108 — restore teacher AI usage actor logging
  - PR #109 — show class-period duration in Course Setup
  - PR #110 — show duration and order classes by start time on the dashboard
  - PR #111 — make pacing lessons map one-to-one with class days
  - PR #112 — restore AI planning suggestion saves

The controlled database preview, database application, and application deployment workflows were
reported successful by the release operator. The deployment workflow is the authoritative source
for the immutable image digest, ECS task-definition revision, and captured prior rollback task
definition; those values are not guessed or duplicated in this record.

## Live acceptance results

The release operator completed live Pilot testing and reported all checks passed:

- class duration appears in Course Setup;
- class duration appears on the dashboard;
- classes are ordered by start time;
- each pacing lesson maps to one class day;
- the pacing minute override is absent;
- governed AI planning generation succeeds;
- a teacher can explicitly use an AI planning suggestion;
- the weekly plan saves successfully; and
- reopening the saved week preserves the accepted planning text.

## Automated evidence

Before merge and deployment:

- the full backend suite passed with 589 tests;
- Ruff lint passed;
- mypy type checking passed;
- the production frontend build passed;
- GitHub CI passed on PR #112 exact head
  `f1a341995f61d180f205c2fc1e3ca2d90bab243f`; and
- Alabama Arts real-source verification passed on that exact head.

PR #111 independently passed CI and Alabama Arts real-source verification before merge.

## Baseline behavior

This baseline establishes the following behavior for future regression and rollback decisions:

1. A pacing row is a daily instructional lesson, not a minute allocation. The saved class schedule
   supplies the available minutes for that date.
2. Historical pacing-minute values remain readable for compatibility but do not split, combine, or
   suppress lessons.
3. AI output remains a teacher-reviewable draft. A teacher must explicitly accept, edit, or reject a
   suggestion before it enters the working plan.
4. Accepted or edited AI text can be saved in the weekly plan and remains present when that plan is
   reopened.
5. The data boundary remains adult educator/administrator professional planning data only. Student
   PII and student education records remain prohibited.

## Operational boundaries

- This baseline does not itself activate SES application sending.
- This baseline does not itself activate either automatic Friday notification dispatcher.
- Applied notification schema and operational notification activation remain separate states.
- Future releases must use the exact-SHA, exact-migration, Help-review, and controlled-deployment
  workflow gates documented in `docs/PILOT_DEPLOYMENT.md`.
- Application rollback must use the prior immutable image/task definition captured by the successful
  deployment workflow. Database migrations are corrected forward; application rollback does not
  reverse this migration history.

## Acceptance decision

**PASS —** this exact application and migration state is the new accepted TPP Pilot baseline.
