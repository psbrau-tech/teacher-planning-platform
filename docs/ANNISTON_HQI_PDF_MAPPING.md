# Anniston HQI Document Mapping

## Source

Anniston City Schools supplied one three-page fillable PDF containing 57 AcroForm text fields. TPP treats that file as the source container for **three separate planning documents**, not as one fixed three-page output that must hold all content at any cost.

The three document types are:

1. **High Quality Instruction Planning Framework** — source page 1
2. **Week at a Glance** — source page 2
3. **Weekly Reflection / PLC Discussion** — source page 3

Each document may remain one page when content fits at a normal readable font size or expand to two or more pages when continuation space is required. TPP must never truncate content or shrink text to an unreadable size merely to preserve a one-page boundary.

## Visual identity is part of the contract

The source PDF is not merely a field inventory. Its visual structure is required output behavior.

The generated first page for each document must preserve the corresponding source page's:

- dark-green title and section bars;
- gold accent line and Wright Way Leadership Group attribution;
- bordered teacher, course, grade, week, and topic fields;
- section boxes, labels, instructional prompts, and page geometry;
- Week at a Glance matrix structure, weekday columns, and component rows;
- Weekly Reflection two-column question/response grid;
- footer treatment and source-document identity.

A plain text report with headings is not an acceptable substitute, even when all text is present and wrapped correctly.

The required rendering model is hybrid:

1. Use the district-approved source page as the exact branded first-page background.
2. Overlay readable, wrapped content inside the mapped source regions.
3. When content cannot fit at the approved minimum font size, move the excess and any following section(s) to a continuation page.
4. Continuation pages must use the same visual language: dark-green section bars, bordered content regions, matching typography, attribution, and document identity.
5. The combined packet is assembled from the three independently rendered, visually faithful documents.

## Confirmed field inventory

### Document 1 - High Quality Instruction Planning Framework

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

### Document 2 - Week at a Glance

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

### Document 3 - Weekly Reflection / PLC Discussion

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

## Pagination and readability rules

1. Each source page establishes the exact visual first page of its own document.
2. Narrative text uses a normal, readable body font size; automatic shrink-to-fit is not an accepted overflow strategy.
3. Text wraps inside its assigned region.
4. A section may expand vertically when space remains on the page.
5. If expansion would collide with the next section, the next section moves to the following page.
6. If one section itself exceeds a page, it continues in a matching labeled content region on the next page.
7. Continuation pages repeat the teacher, course, week, document title, section label, and page numbering needed to keep printed pages attributable.
8. Content is never silently truncated.
9. A combined packet may be offered as a convenience download, but it is assembled from the three independently generated documents.
10. Teachers may download any of the three documents separately.

## Generation rules

1. Teacher approval is required before export.
2. Official standards wording must not be rewritten by AI.
3. Student-specific reflection fields remain teacher-entered or teacher-approved.
4. Missing optional content produces a blank field rather than invented content.
5. Editable exports retain appropriate form fields on the source page; continuation pages retain full readable content.
6. Flattened exports are produced only after the teacher approves the final plan.
7. Every generated document records document type, template version, payload hash, generating user, generation time, page count, continuation-page count, and whether the output was editable or flattened.

## Acceptance requirements

Automated tests must verify text preservation, wrapping, page counts, and document order. Visual acceptance must separately verify:

- source-page formatting parity;
- correct placement within the original boxes and grids;
- no overlaps or clipped content;
- matching continuation-page branding;
- readable typography;
- correct independent-document and combined-packet order.

Passing text-based tests alone does not constitute document acceptance.

## Template handling

The district-approved source file is installed at:

`backend/assets/anniston_hqi_lesson_plan.fillable.pdf`

The application verifies that the source exposes the confirmed 57 fields and three source pages. A visually similar or scanned copy is not an acceptable substitute.
