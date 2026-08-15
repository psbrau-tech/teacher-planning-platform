# PLC Facilitation Artifact Decision

**Date:** 2026-08-14  
**Status:** Approved implementation slice  
**Scope:** Teacher Planning Platform (TPP) controlled pilot

## Purpose

The school Reflection Intelligence surface already produces an anonymous aggregate weekly PLC brief from teacher-authored submitted reflections. This slice turns that brief into a more useful one-to-two-page PLC facilitation artifact without introducing a second AI request, a new teacher task, or a new retained content store.

The artifact is intended to help instructional coaches, administrators, and PLC teams move from aggregate reflection themes to a structured professional-learning conversation.

## Source boundary

The artifact may use only the already-generated school PLC brief fields:

- common successes;
- common challenges;
- emerging themes;
- PLC discussion questions;
- possible actions; and
- support needs.

The artifact does not retrieve raw reflection text independently and does not receive teacher names, teacher identifiers, course names, student information, or student-level assessment information.

The school brief remains subject to the existing minimum of two distinct anonymous teacher sources for any supported common theme.

## Artifact design

The printable artifact is deliberately condensed to support a one-to-two-page meeting handout. It includes:

1. meeting context and the number of anonymous teacher sources represented;
2. up to three common successes, common challenges, and emerging themes;
3. a fixed 40-minute facilitation protocol;
4. a bounded set of PLC discussion questions, possible actions, and support needs;
5. a non-persistent action-planning workspace for the team to complete during the meeting; and
6. explicit professional-learning and data-boundary safeguards.

The fixed protocol is not AI-generated. It is a deterministic facilitation structure applied to the already-generated aggregate brief.

## No additional AI processing

Generating or printing the facilitation artifact must not trigger another OpenAI request. The artifact is formatting and meeting scaffolding around the previously generated school brief.

This preserves a clear provenance chain:

teacher-authored reflection -> governed anonymous aggregate synthesis -> deterministic PLC artifact formatting.

## No new retention

The artifact remains transient/client-side for this slice. TPP does not persist:

- the printed handout;
- meeting notes;
- selected action items;
- named owners;
- revisit dates; or
- handwritten/typed team annotations.

Persisted PLC action tracking, theme lifecycle state, teacher-selected sharing, and recognition remain separate future governance decisions.

## Evaluation boundary

The artifact is a professional-learning aid. It must not be used to:

- score, rank, rate, compare, or evaluate teachers;
- infer teacher effort, productivity, effectiveness, or personnel performance;
- identify which teacher supplied a theme;
- infer student-level outcomes; or
- collect student-specific information during PLC discussion.

The print footer and facilitation safeguards must state this boundary clearly.

## Adoption telemetry

The existing content-free `plc_handout_viewed` event remains sufficient for this slice. No additional meeting-content telemetry is required.
