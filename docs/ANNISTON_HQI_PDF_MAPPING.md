# Anniston HQI PDF Mapping

## Source

The Version 1 document target is the three-page fillable **HQI Lesson Plan Framework** supplied by Anniston City Schools. The original PDF contains 57 AcroForm text fields. The source template must be preserved unchanged and copied for every generated plan.

## Confirmed field inventory

### Page 1 - High Quality Instruction Planning Framework

| PDF field | TPP source |
|---|---|
| `teacher` | Teacher profile display name |
| `course` | Teaching assignment course name |
| `grade` | Teaching assignment grade or grade band |
| `week_of` | Monday date for the generated week |
| `unit_topic` | Unit title and weekly topic |
| `standards` | Approved standards attached to scheduled lessons |
| `know` | Facts, vocabulary, concepts, and prerequisite knowledge |
| `understand` | Enduring understandings |
| `do` | Observable skills and performances |
| `plds` | Level 3+ performance-level descriptors / proficiency scale |
| `misconceptions` | Common misconceptions to monitor |
| `formative` | Weekly formative assessments |
| `summative` | Weekly summative assessments |
| `performance_task` | Performance task or authentic application |
| `resources` | Resources, materials, and links |

### Page 2 - Week at a Glance

Each weekday has six fields. Day suffixes are `mon`, `tue`, `wed`, `thu`, and `fri`.

| Prefix | Planning component |
|---|---|
| `clt_` | Clear learning target and success criteria |
| `rrt_` | Rigorous and relevant task |
| `cfu_` | Checks for understanding |
| `ri_` | Responsive instruction |
| `sic_` | Strong instructional culture |
| `esl_` | Evidence of student learning |

Examples: `clt_mon`, `rrt_wed`, and `esl_fri`.

### Page 3 - Weekly Reflection / PLC Discussion

The fields are `reflect_1` through `reflect_12`, in the order printed on the form:

1. What knowledge has been building this week?
2. What understandings are being developed?
3. What evidence is demonstrating mastery?
4. What misconceptions emerged?
5. What standard(s) or parts of the standard need reteaching?
6. Which students need intervention?
7. What is the plan for intervention (Tier 2 and Tier 3)?
8. Which students need enrichment?
9. What is the plan for enrichment?
10. Which instructional moves worked?
11. What instructional adjustments will I make next week?
12. What are next week's instructional priorities?

## Generation rules

1. Teacher approval is required before export.
2. Official standards wording must not be rewritten by AI.
3. Student-specific reflection fields remain teacher-entered or teacher-approved.
4. Missing optional content produces a blank field rather than invented content.
5. The editable export retains AcroForm fields.
6. The flattened export is produced only after the teacher approves the final plan.
7. Every generated document records template version, payload hash, generating user, generation time, and whether the output was editable or flattened.

## Template handling

The binary source template is not yet committed to the repository. Before document-generation acceptance, place the district-approved original at:

`backend/assets/anniston_hqi_lesson_plan.fillable.pdf`

The application must verify at startup that the template exposes exactly the confirmed 57 fields. A visually similar or scanned copy is not an acceptable substitute.
