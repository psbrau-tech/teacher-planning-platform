# Product Analytics Decision — Active TPP Interaction Time

**Date:** 2026-08-13  
**Status:** Approved for Pilot implementation  
**Scope:** Teacher Planning Platform (TPP)

## Purpose

Measure product workflow efficiency without treating login duration as meaningful teacher work time and without creating a teacher-performance monitoring surface.

## Approved measurement

TPP may record bounded first-party 30-second active-interaction heartbeat event keys for:

- Course Setup;
- Weekly Planning, including AI-assisted planning workflow time;
- Teacher Reflection, specifically the required teacher-authored reflection step; and
- Friday Closeout outside the reflection step, including validation and packet review.

The existing aggregate Friday-closeout measure may include reflection for continuity. Separate reflection and other-closeout measures are retained so product analysis can distinguish them.

## Activity rules

A heartbeat is eligible only when:

- the TPP browser tab is visible;
- the authenticated user has interacted recently;
- the active workflow area can be classified into an approved bounded category; and
- the browser tab currently owns the short-lived local activity lease used to reduce double-counting across multiple open TPP tabs.

Hidden or idle tabs do not continue accumulating active time.

## Data minimization

The telemetry does not record:

- keystroke contents;
- mouse coordinates;
- teacher-entered planning or reflection text;
- student data;
- continuous login duration; or
- third-party advertising/session-replay identifiers.

## Interpretation

Active TPP interaction time is not total teacher planning time. Teachers may plan, think, discuss, review source material, or work in other applications outside TPP.

The first 14 days from each teacher's first measured active TPP use are treated as onboarding/familiarization. Day 15+ is treated as steady-state use for product analysis.

Planning and reflection are reported separately because the required teacher-authored reflection may take materially different time than AI-assisted planning.

## Access boundary

Duration metrics are Platform Owner-only product-effectiveness measures. School and district administrator reporting does not receive active-time duration metrics. The metrics must not be presented as teacher-quality, effort, productivity, or performance scores.

## Governance impact

This is an approved analytics/monitoring change under `LEGAL_COMPLIANCE_REQUIREMENTS.md`. The Privacy Policy and Security & Data Practices drafts are updated with the implemented telemetry description. No new vendor or subprocessor is introduced.
