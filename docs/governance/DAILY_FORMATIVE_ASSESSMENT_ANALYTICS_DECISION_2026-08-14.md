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

This release does not send lesson-plan text to an AI provider for classification.

## Reporting boundary

Authorized school reporting administrators may see school-level aggregate planning signals for a selected period, including:

- submitted course-weeks represented;
- distinct teachers represented;
- number of daily CFU/evidence entries;
- recognized assessment-type counts;
- weekday distribution of daily assessment entries; and
- week-over-week counts for submitted course-weeks, anonymous teacher coverage, daily assessment entries, exit tickets/slips, and the most common additional assessment types.

The analytics response does not return teacher names, teacher IDs, course names, raw lesson-plan text, student data, or teacher-level rankings.

## Weekly trend interpretation

Weekly trends reuse the same submitted-plan source and deterministic taxonomy. No new teacher entry, AI request, database analytics store, or student-result source is introduced.

The trend intentionally reports **raw school-level planning counts** rather than a percentage, compliance rate, or teacher comparison. TPP displays submitted course-week and anonymous-teacher coverage alongside each week so instructional coaches can interpret changes in context.

TPP does not assume every course meets five days per week. A lower count from one week to another may reflect differences in submitted course-weeks, school schedules, class meeting patterns, or the assessment strategies teachers planned. The product must not convert these counts into an expectation that every teacher or course use a particular assessment type at a particular frequency.

Exit tickets/slips remain visible as a trend category even when the recognized count is zero so coaches can track the specific planning signal they requested without treating zero as a performance finding.

## Interpretation

These metrics describe **planned formative-assessment signals**. They do not prove that an assessment was administered, that students completed it, that students learned from it, or that a teacher is effective.

The feature may support PLC and coaching questions such as whether staff want additional exit-ticket options, whether the school is planning a diverse assessment mix, whether a strategy is appearing more often across submitted plans, or whether unfamiliar assessment language should be added to the transparent taxonomy.

The feature may not be used by TPP to create teacher quality scores, teacher rankings, performance ratings, effort/productivity scores, compliance rates, or automated personnel decisions.

## Data minimization

The database reporting function returns only anonymous teacher references and the ten daily CFU/evidence fields needed for server-side classification. Raw plan text is not returned by the public API response and is not copied into a new analytics table.

The weekly trend is computed in the application from that same bounded source and returns aggregate weekly counts only. No new assessment-content retention store is created.

## Release requirements

Before controlled deployment:

1. apply and verify the governed reporting RPC;
2. verify the source is limited to latest immutable submitted `lesson_plan` revisions;
3. verify no reflection content enters the source;
4. verify API responses contain aggregate counts only;
5. verify school reporting authorization and school scope;
6. verify the deterministic taxonomy against representative pilot wording;
7. verify weekly trend counts use the same source/taxonomy and preserve coverage context;
8. review Help/privacy language for the exact release candidate; and
9. retain exact commit/image/migration evidence for release.
