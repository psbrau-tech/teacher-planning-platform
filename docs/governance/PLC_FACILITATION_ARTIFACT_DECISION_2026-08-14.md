# PLC Facilitation Artifact Decision

**Date:** 2026-08-14  
**Status:** Approved implementation slice  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Purpose

The school Reflection Intelligence surface already produces an anonymous aggregate weekly PLC brief from teacher-authored submitted reflections. The PLC facilitation artifact turns that brief into a practical one-to-two-page professional-learning resource. The artifact may also include a compact aggregate snapshot of daily formative-assessment types already present in submitted lesson plans for the same week.

This design does not create a new teacher task, a new retained content store, or a second AI pass over lesson-plan assessment text. It is intended to help instructional coaches, administrators, and PLC teams connect aggregate teacher reflection themes with aggregate planning signals in a bounded professional-learning conversation.

## Source boundary

The reflection portion of the artifact may use only the already-generated school PLC brief fields:

- common successes;
- common challenges;
- emerging themes;
- PLC discussion questions;
- possible actions; and
- support needs.

The optional formative-assessment planning snapshot may use only the already-governed aggregate response from `/api/v1/assessment-analytics/school` for the same Monday-starting week. That response is derived from immutable submitted lesson-plan Checks for Understanding / Evidence of Student Learning fields and returns aggregate counts rather than raw lesson-plan text.

The assessment snapshot may include:

- planned daily formative-assessment entry count;
- submitted course-week coverage;
- anonymous teacher coverage;
- exit tickets/slips count; and
- up to three other common recognized planned assessment types.

The artifact does not independently retrieve raw reflection text or raw lesson-plan text. It does not receive teacher names, teacher identifiers, course names, student information, student assessment results, or student-level analytics.

The school reflection brief remains subject to the existing minimum of two distinct anonymous teacher sources for any supported common theme.

## Artifact design

The printable artifact is deliberately condensed to support a one-to-two-page meeting handout. It includes:

1. meeting context and the number of anonymous reflection sources represented;
2. up to three common successes, common challenges, and emerging themes;
3. the optional aggregate formative-assessment planning snapshot for the same week;
4. a fixed 40-minute facilitation protocol;
5. a bounded set of PLC discussion questions, possible actions, and support needs;
6. a non-persistent action-planning workspace for the team to complete during the meeting; and
7. explicit professional-learning, planning-signal, and data-boundary safeguards.

The fixed protocol is not AI-generated. It is a deterministic facilitation structure applied to the already-generated aggregate brief. The formative-assessment snapshot uses the existing deterministic assessment taxonomy.

## AI processing boundary

Generating the school Reflection Intelligence brief remains the single AI synthesis step for reflection content.

Adding the assessment planning snapshot must not send lesson-plan text to OpenAI or another AI provider. The assessment classification and snapshot formatting are deterministic. Printing or reformatting the facilitation artifact must not trigger another AI request over either the reflection brief or the assessment snapshot.

This preserves a clear provenance chain:

teacher-authored reflection -> governed anonymous aggregate AI synthesis -> deterministic PLC artifact formatting

and, separately:

submitted lesson-plan assessment fields -> deterministic aggregate classification -> deterministic PLC assessment snapshot.

## Graceful degradation

The reflection brief remains the core PLC artifact. If the aggregate assessment analytics endpoint is unavailable, the artifact may still be generated from the governed reflection brief with a bounded notice that the optional assessment planning snapshot is unavailable.

An unavailable assessment snapshot must not cause TPP to infer, fabricate, or substitute assessment counts.

## No new retention

The artifact remains transient/client-side for this slice. TPP does not persist:

- the printed handout;
- the aggregate snapshot as a separate PLC record;
- meeting notes;
- selected action items;
- named owners;
- revisit dates; or
- handwritten/typed team annotations.

Persisted PLC action tracking, theme lifecycle state, teacher-selected sharing, and recognition remain separate future governance decisions.

## Evaluation boundary

The artifact is a professional-learning aid. Reflection themes and assessment-planning counts must not be used by TPP to:

- score, rank, rate, compare, or evaluate teachers;
- create an assessment-use compliance rate or frequency target;
- infer teacher effort, productivity, effectiveness, or personnel performance;
- identify which teacher supplied a reflection theme or planned a particular assessment type;
- infer student-level outcomes, mastery, or assessment performance; or
- collect student-specific information during PLC discussion.

A planned assessment count does not establish that an assessment was administered. Weekly counts must be interpreted alongside course-week and anonymous-teacher coverage and differences in class schedules.

The print footer and facilitation safeguards must state these boundaries clearly.

## Adoption telemetry

The existing content-free `plc_handout_viewed` event remains sufficient for this slice. No additional meeting-content, assessment-content, or combined-profile telemetry is required.
