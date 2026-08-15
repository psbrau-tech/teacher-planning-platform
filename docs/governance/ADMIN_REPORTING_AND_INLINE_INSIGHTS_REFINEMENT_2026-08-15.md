# Administration reporting and inline Reflection Insights refinement

**Decision date:** 2026-08-15  
**Status:** Approved live-pilot UX refinement; existing professional-data boundary remains controlling

## Administrator submission follow-up

The separate administrator-facing Friday Submission Status report is removed from the normal Administration view. Administrator submission follow-up is consolidated into the existing **Weekly submissions** report so a busy administrator does not have to interpret two substantially overlapping teacher/class submission reports.

The consolidated Weekly submissions experience retains:

- Monday-starting week selection;
- governed school filtering where authorized;
- multi-select teacher filtering;
- course filtering;
- Upcoming lesson plan and Completed weekly packet as separate immutable records;
- bulk review/download of selected submitted artifacts; and
- clear green submitted status and yellow needs-follow-up status treatment.

The teacher Dashboard Friday status remains available because it serves a different self-service purpose: it tells each teacher which of their own current-week closeout and following-week planning obligations still require submission.

This UI consolidation does **not** remove or weaken the authenticated Friday-status backend functions used to compute governed status or support separately activated reminder/digest infrastructure. Scheduled email delivery remains separately governed and inactive until its existing release gates are satisfied.

## Administrator instructional-learning flow

Administration should read in a practical sequence rather than as disconnected reports:

**Planned formative-assessment mix → Week-over-week planned assessment trend → School Reflection Summary → PLC Meeting Guide**

The **School Reflection Summary** must be visibly presented as its own administrator-facing evidence view after it is generated. It remains an anonymous aggregate synthesis of submitted teacher-authored professional reflections, subject to the existing source-threshold rules.

The **PLC Meeting Guide** follows the summary and uses it as the evidence base for the meeting. The same School Reflection Summary must be carried into the printable PLC Meeting Guide so the printed artifact is not a generic agenda. The guide may add the already-governed suggested focus, deterministic aggregate formative-assessment planning snapshot, fixed 40-minute facilitation protocol, and non-persistent action workspace.

## Teacher Friday Reflection Insights

Private Reflection Insights remain optional **Step 4** after the Completed Weekly Packet has been reviewed and before **Step 5 Continue**. The controls and generated recap now render inline inside Step 4 rather than opening a separate right-side panel.

The privacy and professional-learning boundary is unchanged. The recap uses only the teacher's own submitted professional reflections, requires the existing no-student-data confirmation, does not alter the teacher-authored reflection, and is not a teacher-performance score.

## Shared UI consistency

Transient success/error toast notifications in the authenticated planning shell automatically dismiss after five seconds while retaining the existing manual dismiss control.

PDF preview headers use one consistent layout with the preview title on the left and **Close preview** on the right. This is a presentation-only correction; document content and immutable submission behavior are unchanged.

## Governance boundary

This refinement introduces no database migration, no student data, no teacher ranking or evaluation, no new AI processing of lesson-plan text, no notification activation, and no retained PLC action notes. Existing authorization, RLS, immutable submission, Reflection Intelligence aggregation, and scheduled-notification controls remain in force.
