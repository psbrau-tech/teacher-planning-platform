# Daily Formative-Assessment Analytics Decision

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Approval context

During the August 14 school-leadership review, instructional coaches requested the ability to see daily formative-assessment types teachers are already entering in lesson plans, with exit slips/tickets identified as a concrete example.

This feature extends the approved instructional-analytics direction without creating a new teacher data-entry requirement.

## Authoritative source

Daily formative-assessment analytics use only immutable, explicitly submitted `lesson_plan` records from `weekly_plan_submissions`.

The source fields are the existing Monday-Friday Week at a Glance cells for:

- Checks for Understanding (`cfu_mon` through `cfu_fri`); and
- Evidence of Student Learning (`esl_mon` through `esl_fri`).

The feature does not analyze mutable draft snapshots, completed-packet reflection text, student records, student work, or a new teacher-entered analytics field.

## First-release taxonomy

TPP performs local deterministic recognition for common planned formative-assessment types, including:

- exit tickets / exit slips;
- quick writes / short written responses;
- short quizzes;
- digital polls / response tools;
- whiteboard responses;
- response signals;
- questioning / discussion checks;
- retrieval / warm-up checks;
- observation / conference checks;
- peer / self-assessment; and
- performance / demonstration checks.

A nonblank daily CFU/evidence entry that does not match the transparent taxonomy is counted as `Other / not yet classified`. TPP does not guess the teacher's intended assessment type.

This first release does not send lesson-plan text to an AI provider for classification.

## Reporting boundary

Authorized school reporting administrators may see school-level aggregate planning signals for a selected period, including:

- submitted course-weeks represented;
- distinct teachers represented;
- number of daily CFU/evidence entries;
- recognized assessment-type counts; and
- weekday distribution of daily assessment entries.

The analytics response does not return teacher names, teacher IDs, course names, raw lesson-plan text, student data, or teacher-level rankings.

## Interpretation

These metrics describe **planned formative-assessment signals**. They do not prove that an assessment was administered, that students completed it, that students learned from it, or that a teacher is effective.

The feature may support PLC and coaching questions such as whether staff want additional exit-ticket options, whether the school is planning a diverse assessment mix, or whether unfamiliar assessment language should be added to the transparent taxonomy.

The feature may not be used by TPP to create teacher quality scores, teacher rankings, performance ratings, effort/productivity scores, or automated personnel decisions.

## Data minimization

The database reporting function returns only anonymous teacher references and the ten daily CFU/evidence fields needed for server-side classification. Raw plan text is not returned by the public API response and is not copied into a new analytics table.

No new assessment-content retention store is created in the first release.

## Release requirements

Before controlled deployment:

1. apply and verify the governed reporting RPC;
2. verify the source is limited to latest immutable submitted `lesson_plan` revisions;
3. verify no reflection content enters the source;
4. verify API responses contain aggregate counts only;
5. verify school reporting authorization and school scope;
6. verify the deterministic taxonomy against representative pilot wording;
7. review Help/privacy language for the exact release candidate; and
8. retain exact commit/image/migration evidence for release.
