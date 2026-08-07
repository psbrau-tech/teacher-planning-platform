# Teacher Planning Platform (TPP) — Version 1 Pilot Scope

## Mission
Reduce the time Anniston City Schools teachers spend converting instructional decisions into the required three-page HQI lesson-plan PDF.

## Pilot boundary
- Anniston City Schools only.
- Teacher and curriculum data only; no student data.
- Invited pilot users only.
- Anniston HQI fillable PDF only.
- Current authoritative standards support initially limited to Army JROTC LET 1–4, English 10, and Business Administration.
- Standards are ingested from authoritative sources into governed, refreshable snapshots with source/version provenance; weekly planning must not depend on an external standards website being online.
- The authoritative standards sources are revalidated on the first workday of every month. A detected source change is staged for review and must not silently replace the currently approved standards snapshot.
- AI features are teacher-invoked drafts and require teacher approval before they alter saved planning content or exports.

## Required capabilities
1. Teacher authentication and role-based access.
2. Multiple independent teaching assignments per teacher.
3. Mixed traditional-period, block, A/B, selected-day, and custom recurring schedules.
4. Separate curriculum queue for every teaching assignment.
5. School calendar exclusions and one-time schedule exceptions.
6. Weekly planning by actual instructional minutes.
7. Current authoritative standards ingestion, provenance, refresh, course mapping, and teacher selection for the bounded pilot course set.
8. Scheduled standards-source drift validation on the first workday of every month, with an auditable unchanged/changed/unavailable result for each source; detected changes remain pending until reviewed and approved, and source failures do not invalidate the last approved snapshot.
9. Teacher-invoked OpenAI planning assistance grounded in selected standards and governed teacher/curriculum/planning data, including suggested learning targets, Know/Understand/Do, activities, assessments, resources, Literacy Standards/ACT connections where appropriate, and other HQI planning fields.
10. Teacher-invoked OpenAI Weekly Reflection suggestions grounded in the saved weekly plan and Friday validation, with teacher accept/edit/reject control.
11. Daily validation: completed, modified, missed, or not needed.
12. Missed-lesson carry-forward and manual resequencing.
13. Exact Anniston three-page HQI PDF population, preview, editable export, and flattened export.
14. Audit history for plan and schedule changes.
15. Basic school administrator report.
16. AI usage and estimated-cost logging without exposing secrets or student data.

## Pilot acceptance test
A teacher with four curricula and a mixed period/block schedule can use the current authoritative standards for the assigned course, while the platform can prove those sources are automatically revalidated on the first workday of each month without silently replacing approved standards; the teacher can invoke and approve/edit/reject AI planning suggestions, validate the current week, carry forward an interrupted lesson without altering unrelated courses, receive a teacher-controlled Weekly Reflection suggestion, review the following week, and generate the Anniston HQI PDF in approximately five minutes while remaining inside the teacher-and-curriculum-only data boundary.

## Deferred
- Guided Scholar integration.
- Student evidence ingestion.
- Multi-district onboarding.
- Multiple district templates.
- Broad Alabama standards catalog beyond the bounded pilot course set.
- Calendar-provider integrations.
- Advanced approval chains.
- Full infrastructure-cost allocation.
- Curriculum marketplace.
