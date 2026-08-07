# Teacher Planning Platform (TPP) — Version 1 Pilot Scope

## Mission
Reduce the time Anniston City Schools teachers spend converting instructional decisions into the required three-page lesson-plan PDF while preserving authoritative standards provenance and teacher instructional judgment.

## Pilot boundary
- Anniston City Schools only.
- Teacher and curriculum data only; no student data.
- Invited pilot users only.
- Anniston fillable lesson-plan PDF only.
- The governed standards library includes the complete current Alabama State Department of Education / Alabama Achieves academic and Career and Technical Education standards/course-of-study catalog rather than only the first browser-acceptance courses.
- The Alabama catalog includes all currently published subject/course families and classes discovered from the authoritative state catalogs, including English Language Arts, mathematics, science, social studies/history, arts education, digital literacy/computer science, world languages, health, physical education, driver/traffic safety, career preparedness/work-based learning, all published CTE clusters/courses, JROTC/Government and Public Administration where Alabama publishes them, and any additional current Alabama K–12 Course of Study family.
- Where a mapped course has an additional authoritative issuer, such as U.S. Army Cadet Command for Army JROTC, TPP retains supplemental issuer/version provenance alongside the Alabama catalog relationship rather than substituting the external issuer for Alabama provenance.
- Standards are ingested deterministically from authoritative sources into governed, refreshable snapshots with exact source/version provenance. OpenAI is never used to invent, paraphrase, or rewrite authoritative standards text.
- Weekly planning must not depend on an external standards website being online.
- The authoritative catalog and every governed standards source are revalidated on the first workday of every month. A detected or newly discovered source change is staged for review and must not silently replace a currently approved source/snapshot.
- AI features are teacher-invoked drafts and require teacher review before they alter working planning content or saved exports.
- Guided Scholar integration and student-level recommendations are future opportunities, not Version 1 pilot features.

## Standards course-mapping contract
1. TPP presents the Alabama catalog using a two-level teacher workflow: **Subject / Career Cluster** followed by **Grade / Course**.
2. A teaching assignment maps to exactly one primary Alabama catalog course for Version 1.
3. Teachers create and correct their own teaching-assignment mapping. Platform administrators govern authoritative catalogs, sources, snapshots, and exceptional catalog corrections; they do not configure every teacher course.
4. Before any weekly planning exists, a teacher may change the mapping normally.
5. After weekly planning exists, a mapping change requires an explicit warning and affirmative confirmation.
6. A mapping correction applies to the current open/unvalidated week and future planning. Standards selections belonging to the former course are cleared from open/unvalidated weeks and must be reselected.
7. Validated historical weeks retain the exact standard entry IDs, source snapshots, wording, and provenance that were actually used; mapping corrections never rewrite historical evidence.
8. Teacher-facing course names remain independent from catalog names. For example, `JROTC LET 2 - 4th Period` may map to `Government & Public Administration → Army JROTC II`.

## Literacy and ACT alignment contract
1. The primary course standards remain clearly distinguished from cross-disciplinary recommendations.
2. Literacy recommendations are selected from governed, authoritative Alabama ELA standards/reference records; AI may recommend IDs and explain the instructional connection but may not fabricate or paraphrase an authoritative standard as if it were official text.
3. ACT Preparation recommendations use governed ACT College and Career Readiness skill/reference records where legally and operationally approved for use. AI may recommend IDs and instructional applications but may not invent an ACT standard or present a merely similar phrase as official ACT wording.
4. If no authentic literacy or ACT connection exists, the system may return no recommendation rather than generate filler.
5. All displayed authoritative/reference wording is resolved by the server from governed records after the AI returns candidate IDs.
6. Primary standards, literacy alignments, ACT skills, and instructional objectives retain stable structured identifiers wherever practical so future integrations can consume the relationships without reverse-engineering generated prose.

## Required capabilities
1. Teacher authentication and role-based access.
2. Multiple independent teaching assignments per teacher.
3. Mixed traditional-period, block, A/B, selected-day, and custom recurring schedules.
4. Separate curriculum queue for every teaching assignment.
5. School calendar exclusions and one-time schedule exceptions.
6. Weekly planning by actual instructional minutes.
7. Comprehensive current Alabama authoritative standards catalog discovery, ingestion, provenance, refresh, course mapping, and weekly teacher selection.
8. Teacher-controlled Subject / Career Cluster → Grade / Course mapping with explicit warned correction behavior and immutable historical standards provenance.
9. Scheduled standards-catalog and source drift validation on the first workday of every month, with auditable unchanged/changed/new/unavailable results; detected changes remain pending until reviewed and approved, and source failures do not invalidate the last approved snapshot.
10. Teacher-invoked OpenAI planning assistance grounded in selected primary standards and governed teacher/curriculum/planning data, including suggested learning targets, Know/Understand/Do, activities, assessments, resources, literacy connections, ACT preparation where authentic, and other planning fields.
11. Teacher-controlled AI accept/edit/reject behavior with no silent overwrite.
12. Teacher-invoked OpenAI Weekly Reflection suggestions grounded in the saved weekly plan and Friday validation.
13. Daily validation: completed, modified, missed, or not needed.
14. Missed-lesson carry-forward and manual resequencing.
15. Exact Anniston three-page PDF population, preview, editable export, and flattened export.
16. Audit history for plan, standards mapping, standards selection, schedule, and AI-decision changes.
17. Basic school administrator report.
18. AI usage and estimated-cost logging without exposing secrets or student data.

## Pilot acceptance test
A teacher can configure a teaching assignment by selecting the correct Subject / Career Cluster and Grade / Course from the comprehensive governed Alabama catalog; select exact authoritative standards for the week; receive clearly separated, teacher-controlled planning, literacy, and ACT suggestions grounded in governed IDs; save and reopen the plan without losing provenance; correct an erroneous course mapping only after an explicit warning while validated history remains unchanged; validate the current week; carry forward an interrupted lesson without altering unrelated courses; receive a teacher-controlled Weekly Reflection suggestion; and generate the Anniston lesson-plan PDF in approximately five minutes. The platform can also prove that the complete governed standards catalog is checked on the first workday of each month without silently replacing approved standards and that all pilot workflows remain inside the teacher-and-curriculum-only data boundary.

## Future-compatible architecture, not Version 1 functionality
Preserve structured IDs/relationships for standards, literacy alignments, ACT skills, learning targets, and instructional-skill classifications so future systems may support:
- Guided Scholar assignment/template recommendations from instructional intent;
- longitudinal skill-growth analysis;
- teacher-approved class or student-specific task recommendations;
- standards → skill → assignment → performance → growth → next-recommendation relationships.

No student data is introduced into TPP by preserving this structural compatibility.

## Deferred
- Guided Scholar integration.
- Student evidence ingestion.
- Longitudinal student feedback in TPP.
- Student-specific assignment/task recommendations.
- Class-level student-performance analytics.
- Multi-district onboarding.
- Multiple district templates.
- Calendar-provider integrations.
- Advanced approval chains.
- Full infrastructure-cost allocation.
- Curriculum marketplace.
