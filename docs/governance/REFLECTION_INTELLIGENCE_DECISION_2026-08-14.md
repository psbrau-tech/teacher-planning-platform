# Reflection Intelligence Decision — Teacher Recaps, School PLC Briefs, and Notification Direction

**Date:** 2026-08-14  
**Status:** Approved for implementation  
**Scope:** Teacher Planning Platform (TPP) controlled pilot  
**Approval context:** Anniston High School principal, assistant principal, and instructional coaches approved moving forward with the Reflection Intelligence analytics, role-based email-notification direction, and PLC/faculty artifacts described in the approved concept review.

## Purpose

Move TPP from storing weekly planning packets to helping teachers and school leaders learn from the professional reflections teachers already author as part of the Friday closeout workflow.

The feature is designed to produce useful instructional insight while preserving the existing no-student-data boundary and avoiding teacher surveillance or personnel evaluation.

## Locked source boundary

Reflection Intelligence may analyze only teacher-authored professional reflection responses from an explicitly submitted `completed_packet` record.

The 12 Weekly Reflection / PLC Discussion prompts remain teacher-authored. TPP may not generate, complete, rewrite, or suggest answers to those prompts.

Mutable working drafts are not an authoritative Reflection Intelligence source. The immutable completed-packet submission is the source of record for synthesis.

## Approved outputs

### Private teacher insight

A teacher may request a private weekly recap and longitudinal 4-12 week pattern summary from the teacher's own submitted reflections. The output may identify recurring instructional themes, strategies the teacher reports working, challenges the teacher reports, and carry-forward ideas.

This output is private to the teacher. It is not an administrator teacher-quality report.

### School weekly PLC brief

Authorized school reporting administrators may request a school-scoped aggregate PLC brief from submitted teacher reflections for a selected week. The brief may contain:

- common successes;
- common challenges;
- emerging instructional themes;
- possible PLC discussion questions;
- possible actions; and
- support needs.

School synthesis uses anonymous per-teacher source references. A common theme must be supported by at least two distinct teacher sources before it is shown. Multiple course reflections from one teacher do not count as multiple teachers.

### PLC/faculty handout

The school brief may be rendered as a transient, print-friendly PLC/faculty handout. The first implementation should avoid unnecessary server-side artifact retention. The handout is an instructional-learning artifact, not an evaluation report.

### Notification layer

The approved product direction includes role-based email notifications using AWS services. Email implementation is a separate release slice because it adds an operational communication data flow and infrastructure/IAM configuration. Email content must remain school-scoped, minimize professional content, contain no student data, and link users back to authenticated TPP for details.

## AI rules

AI is permitted to synthesize teacher-authored submitted reflections. AI is not permitted to author the required reflection responses.

Reflection Intelligence prompts and output processing must prohibit:

- teacher quality scores;
- ranking or comparison of teachers;
- performance, productivity, or effort judgments;
- teacher identity inference from anonymous school sources;
- student identity or student-specific inference; and
- unsupported claims not grounded in the submitted reflections.

TPP must perform a local preflight for common high-risk student-specific markers before sending reflection text to the approved AI provider. This is an additional safeguard and does not replace the product's explicit prohibition on student data at entry.

## Operational reporting remains separate

Named teacher information may continue to appear where operationally necessary for existing submission/compliance follow-up, such as missing lesson plans or missing completed packets.

Instructional Reflection Intelligence must remain distinct from that operational reporting. An administrator must not receive a named teacher instructional quality score or named AI judgment derived from reflection content.

## Analytics

TPP may record content-free Reflection Intelligence adoption events such as:

- private teacher recap generated;
- school PLC brief generated; and
- PLC handout viewed/used.

These records may contain bounded event metadata such as school, authenticated actor, event key, and timestamp. They may not contain teacher-entered reflection text, generated insight text, student data, or teacher-quality scores.

Platform Owner product analytics may report aggregate feature adoption. These metrics are product-effectiveness signals, not teacher-performance measures.

## Data minimization and retention

The first implementation generates Reflection Intelligence output on demand and does not create a new server-side retained store of generated teacher recaps or PLC briefs. Source reflections remain governed by the existing professional planning-content retention rules.

A later feature that stores generated insights, sharing decisions, theme lifecycle records, or retained handouts must receive a retention/data-inventory review before release.

## Accessibility

Teacher and administrator Reflection Intelligence UI must preserve keyboard access, visible focus, semantic headings/labels, error identification, zoom/reflow, and other applicable WCAG 2.1 AA engineering requirements.

The initial PLC handout should use accessible HTML/print markup rather than making an unsupported accessibility claim for a newly generated PDF.

## Release requirements

Before production activation of this slice:

1. apply and verify the governed database migration and RLS/RPC behavior;
2. verify teacher-private and school-aggregate authorization boundaries;
3. verify school synthesis does not expose teacher identity;
4. verify the two-distinct-teacher aggregation threshold;
5. verify AI request context contains only permitted professional reflection content;
6. verify AI provider/account data-use settings remain approved;
7. update the privacy/data inventory to reflect reflection synthesis and content-free usage telemetry;
8. run regression tests confirming AI-authored reflection assistance remains disabled; and
9. retain exact commit/image/migration evidence for the controlled release.

## Deferred release slices

The following are approved product direction but are intentionally deferred from the first Reflection Intelligence foundation release:

- teacher-selected named/anonymous insight sharing;
- persisted school theme lifecycle (`Emerging → Recurring → Discussed → Action Taken → Resolved/Persistent`);
- prompt optimization/rotation of the 12 district prompts;
- potentially-minimal reflection heuristics beyond completion status; and
- automatic/scheduled AWS SES delivery.

Those changes require their own implementation evidence and, where applicable, further governance/privacy reconciliation before activation.
