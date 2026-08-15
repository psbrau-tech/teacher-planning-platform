type Props = { roles: string[] };

export function HelpPage({ roles }: Props) {
  const isTeacher = roles.includes("teacher");
  const isAdmin = roles.some(
    (role) => ["school_admin", "district_admin", "platform_admin"].includes(role),
  );
  const isPlatformAdmin = roles.includes("platform_admin");

  return (
    <section className="panel help-page">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Pilot help</p>
          <h2>Teacher Planning Platform help</h2>
          <p className="supporting">
            Current guidance for Course Setup, Curriculum & Pacing, weekly planning, Friday
            closeout, professional-learning analytics, notifications, surveys, administration, and
            Platform Owner reporting.
          </p>
        </div>
      </div>
      <div className="guidance-card">
        <strong>Data boundary</strong>
        <p>
          TPP is for educator/account information, curriculum, standards, schedules, lesson plans,
          weekly reflection, professional-learning information, and related professional planning
          content. Do not enter student names, IDs, grades or assessment results, IEP/504
          information, health or discipline information, identifiable student work, or other
          student-specific information. Use class- or group-level instructional observations.
        </p>
      </div>

      {isTeacher && (
        <section className="help-section">
          <h3>Teacher workflow</h3>
          <div className="help-notes">
            <h3>One-time pre-TPP baseline</h3>
            <p>
              <strong>TPP may ask for a short baseline after sign-in.</strong> The five required
              questions should take about 60–90 seconds. Answer them based on your normal planning,
              submission, and reflection experience <strong>before you began using TPP</strong>,
              even if you have already used TPP during the Pilot. The optional written response is
              also about the pre-TPP process.
            </p>
            <p>
              Choose <strong>Continue for now</strong> if you need to get to your planning work.
              TPP will ask again on a later sign-in until the one-time baseline is submitted. The
              baseline is used to evaluate product workload/value over time, not to score teacher
              performance. Keep the same no-student-information boundary in the optional comment.
            </p>
          </div>

          <div className="help-notes">
            <h3>Set up each class once</h3>
            <p>
              <strong>Step 1 — Class & Schedule.</strong> Enter the class name, optional course
              code, grade(s), meeting days/times, and effective dates. Curriculum is intentionally
              not selected during this step. Use <strong>Add another class</strong> when you are
              ready to create the next section.
            </p>
            <p>
              <strong>Step 2 — Curriculum & Pacing.</strong> Choose one path:
              <strong> Upload Excel</strong>, <strong>Build in TPP</strong>, or
              <strong> Reuse mine</strong>. Upload Excel reads the workbook into a compact review;
              then choose <strong>Save Curriculum & Pacing & Continue</strong>. Nothing is saved
              merely by selecting the file. Leave Optional Minutes Override blank to use the class
              schedule.
            </p>
            <p>
              <strong>If you build pacing in TPP.</strong> Start with a complete first instructional
              week rather than a single placeholder lesson. Enter enough lessons to cover the
              class&apos;s normal meeting days that first week — from one lesson for a once-weekly class
              through five lessons for a daily class. You can add the rest of the semester/year now
              or extend future unscheduled pacing later.
            </p>
            <p>
              <strong>Step 3 — Authoritative Standards.</strong> Map the class to the governed
              Alabama subject/career-cluster course used for weekly standards selection.
            </p>
            <p>
              <strong>Step 4 — Ready.</strong> Review the class, pacing, and standards summary. The
              class is then ready for Weekly Plan.
            </p>
            <p>
              <strong>My curricula only.</strong> Course Setup lists active curricula created by
              your teacher account. A Platform Owner who also has a Teacher role still sees only
              their own curricula in the teacher setup flow. An unused curriculum can be retired;
              TPP will not retire one that is still attached to an active class.
            </p>
          </div>

          <div className="help-notes">
            <h3>Curriculum & Pacing across the year</h3>
            <p>
              <strong>Each class has independent progress.</strong> Two classes can reuse one
              curriculum without sharing progress. Completing, missing, carrying forward, or
              scheduling a lesson in one class does not mark that lesson complete in another class.
            </p>
            <p>
              <strong>Edit current curriculum.</strong> The current-year curriculum is a living
              pacing document. Lessons already scheduled or submitted by a class using the
              curriculum are preserved. You can edit, replace, reorder, or add future unscheduled
              lessons after the preserved point and can extend the sequence when you need more
              instruction later in the year.
            </p>
            <p>
              <strong>Shared curriculum changes.</strong> A curriculum used by one active class
              opens the future pacing editor directly. When multiple active classes use the same
              curriculum, TPP asks how the edit should apply. Choose
              <strong> Update shared future pacing</strong> to change the common future sequence, or
              <strong> Create a separate copy for this class</strong> when one class needs a
              different path. Historical weekly plans and completed packets are never rewritten.
            </p>
            <p>
              <strong>Download Excel.</strong> Download Curriculum & Pacing at any time. The file
              contains the latest saved sequence, including changes made in TPP, rather than only
              the workbook originally uploaded.
            </p>
            <p>
              <strong>Create new version / copy.</strong> Use the final refined curriculum as the
              starting point for another class or a future school year. The copy starts with no
              class progress attached.
            </p>
            <p>
              <strong>Reuse later.</strong> Active saved curricula remain available in your teacher
              curriculum list for reuse. Download Excel whenever you want a portable copy. TPP does
              not publish a numerical post-termination retention promise in the teacher Help page.
            </p>
          </div>

          <div className="help-notes">
            <h3>Build a weekly plan</h3>
            <p>
              <strong>1. Choose the class and week.</strong> TPP treats every planning week as
              Monday through Friday. Previous/Next week navigation and date selection resolve to the
              Monday that begins the week; the server rejects a non-Monday week identity.
            </p>
            <p>
              <strong>2. Reconcile schedule changes, then build/confirm the week.</strong> If a
              testing day, rally, closure, or other event means the class will not meet, choose
              <strong> No class / postpone pacing for this day</strong> before rebuilding. A skipped
              meeting does not consume the pacing lesson; TPP keeps curriculum order and resumes on
              the next available class meeting. TPP then uses the class&apos;s saved Curriculum & Pacing,
              independent progress, schedule, school calendar, schedule exceptions, and
              teacher-selected carry-forward. Review the scheduled lessons and explicitly confirm
              the week&apos;s curriculum before continuing.
            </p>
            <p>
              <strong>3. Save authoritative standards.</strong> Confirm the governed standards
              relevant to this week&apos;s scheduled curriculum.
            </p>
            <p>
              <strong>4. Use planning assistance if helpful.</strong> Review, edit, accept,
              regenerate, or skip suggestions. AI does not silently save planning text.
            </p>
            <p>
              <strong>5. Review and save the plan.</strong> Review the Instructional Planning
              Framework and Week at a Glance in district PDF order, then save the working revision.
            </p>
            <p>
              <strong>6. Review the PDF.</strong> Choose <strong>View PDF</strong> to open and review
              the saved Weekly Lesson Plan. Downloading or printing is also available, but those
              actions do not substitute for the review gate. Viewing the PDF does not submit or
              resubmit the weekly plan.
            </p>
            <p>
              <strong>7. Submit explicitly.</strong> After PDF review, use the separate
              <strong> Submit weekly plan</strong> step when you are ready to create the immutable
              administrator-visible upcoming lesson-plan record.
            </p>
          </div>

          <div className="help-notes">
            <h3>Every Friday after the first week</h3>
            <p>
              <strong>1. Validate the current week.</strong> Record what actually happened and
              choose whether missed or modified instruction should carry forward.
            </p>
            <p>
              <strong>2. Complete the teacher-authored reflection.</strong> Complete all 12 Weekly
              Reflection / PLC Discussion prompts yourself using class- or group-level observations
              only. TPP does not suggest, generate, complete, or rewrite those required reflection
              responses.
            </p>
            <p>
              <strong>3. Review the Completed Weekly Packet.</strong> Review the immutable packet
              containing that week&apos;s Instructional Planning Framework, Week at a Glance, and
              teacher-authored reflection. View, Download, and Print remain available.
            </p>
            <p>
              <strong>4. Review Reflection Insights if useful.</strong> After the reflection is
              submitted and the completed packet is reviewed, the Friday validation page offers an
              optional private recap based only on your own already-submitted professional
              reflections. The recap is an AI-generated analytical aid; it does not alter your
              submitted reflection and is not an official response or teacher-performance score.
              Reflection Insights are optional and do not block the Friday workflow.
            </p>
            <p>
              <strong>5. Continue to the following week.</strong> TPP moves to the next Monday and
              uses that class&apos;s accumulated pacing progress plus your carry-forward decisions.
            </p>
            <p>
              <strong>Friday submission status.</strong> The Dashboard shows each active required
              class separately. It identifies whether the current week&apos;s teacher-authored
              reflection/completed packet has been submitted and whether the following week&apos;s
              lesson plan has been submitted. Saved drafts do not count as submitted. A class with
              no expected instructional meeting in a relevant week is shown as not required rather
              than falsely missing.
            </p>
            <p>
              <strong>Friday courtesy reminder.</strong> When separately activated, TPP checks the
              same submitted status at 2:00 PM Friday in the school&apos;s local timezone. Teachers with
              everything required submitted receive no email. A teacher with an outstanding item
              receives one friendly reminder that names the exact class or classes and whether the
              missing item is this week&apos;s reflection/completed packet, next week&apos;s lesson plan, or
              both. The email does not contain reflection text, lesson-plan content, student data,
              generated instructional insight, or teacher-quality/performance scoring.
            </p>
            <p>
              <strong>If you refresh after closeout.</strong> TPP should recognize an already
              submitted Completed Weekly Packet and return you to packet review rather than asking
              you to submit the reflection again.
            </p>
            <p>
              <strong>One-time Pilot feedback.</strong> Pilot teachers may receive a short feedback
              request after the Pilot cycle is complete. It asks what was useful, what created
              friction, and what should improve before broader rollout. Choose
              <strong> Remind me later</strong> if you need to keep working; the survey never blocks
              planning or Friday closeout. Keep the same no-student-information boundary in written
              feedback.
            </p>
          </div>

          <div className="help-notes">
            <h3>Common teacher questions</h3>
            <p>
              <strong>I clicked a Course Setup action and the page has not changed yet.</strong> Some
              curriculum loads or saves can take several seconds. The Course Setup working indicator
              confirms that TPP is still processing the action; wait for it to finish rather than
              clicking the same action repeatedly.
            </p>
            <p>
              <strong>I uploaded Excel and nothing changed.</strong> Confirm the success message and
              compact lesson review, then select <strong>Save Curriculum & Pacing & Continue</strong>.
              Uploading alone does not write anything to the database.
            </p>
            <p>
              <strong>My schedule changed or I need to postpone one class day.</strong> Add the
              schedule adjustment before rebuilding/reconciling the week. Choose
              <strong> No class / postpone pacing for this day</strong> when the meeting will not
              occur; use reduced instructional minutes when the class still meets on a shortened
              schedule.
            </p>
            <p>
              <strong>A lesson was not taught unexpectedly.</strong> Record that during Friday
              validation and select carry-forward only when it should remain in sequence.
            </p>
            <p>
              <strong>I planned next week early.</strong> Previously scheduled lessons are part of
              that class&apos;s progress cursor, so building another week must not duplicate them.
              Friday validation still records what actually happened and controls carry-forward.
            </p>
            <p>
              <strong>I changed a submitted lesson plan.</strong> Save the revision, review its PDF,
              and use the explicit resubmit action so the upcoming lesson-plan record reflects the
              new immutable revision.
            </p>
          </div>
        </section>
      )}

      {isAdmin && (
        <section className="help-section">
          <h3>Administrator workflow</h3>
          <ol className="help-steps">
            <li><strong>Open Administration:</strong> Choose the reporting period needed for the operational summary.</li>
            <li><strong>Review Friday submission status:</strong> Use the current-week closeout / following-week planning report for teacher- and class-level operational follow-up.</li>
            <li><strong>Review weekly submissions:</strong> Select the Monday-starting week and optionally narrow the list by school, multiple teachers, or course.</li>
            <li><strong>See both records:</strong> Each teacher/course row shows the pre-instruction <strong>Upcoming lesson plan</strong> and the end-of-week <strong>Completed weekly packet</strong> separately.</li>
            <li><strong>Review one record:</strong> Open the lesson-plan submission to see the Instructional Planning Framework + Week at a Glance, or open the completed packet to see those documents plus the teacher reflection.</li>
            <li><strong>Review many records:</strong> Choose Upcoming lesson plans or Completed weekly packets for bulk review, select individual rows or all filtered records, then review/download/print the selected immutable PDFs as one administrator packet.</li>
          </ol>
          <div className="help-notes">
            <h3>What administration is reviewing</h3>
            <p>
              The upcoming lesson plan proves the plan was submitted before instruction. The
              completed weekly packet is a separate end-of-week record that attaches the
              teacher-authored reflection to that same week&apos;s plan. The following week&apos;s lesson
              plan appears under its own Monday-starting week and receives a completed packet only
              after that week&apos;s Friday closeout.
            </p>
            <p>
              <strong>Friday submission status is operational.</strong> The live report shows the
              current week&apos;s required completed packet/reflection and the following week&apos;s required
              lesson plan by teacher and class, using immutable submissions rather than draft
              presence. It is for workflow follow-up, not teacher ranking, instructional-quality
              inference, effort/productivity scoring, or personnel evaluation.
            </p>
          </div>

          <div className="help-notes">
            <h3>School Reflection Summary and PLC Meeting Guide</h3>
            <p>
              <strong>The School Reflection Summary uses submitted professional reflections.</strong>
              TPP may generate an anonymous aggregate school summary only through the governed
              reporting role and source-threshold rules. Common themes require support from at
              least two distinct anonymous teacher sources. The summary identifies common
              successes, common challenges, emerging themes, discussion questions, possible
              actions, and support needs. It is for professional learning and discussion, not
              teacher ranking, quality scoring, personnel evaluation, or student outcome inference.
            </p>
            <p>
              <strong>The PLC Meeting Guide embeds that School Reflection Summary.</strong> The
              meeting guide is therefore grounded in what teachers collectively reported rather
              than being a generic agenda. It adds a suggested meeting focus, the governed aggregate
              formative-assessment planning snapshot when available, a fixed 40-minute facilitation
              protocol, and a non-persistent team action workspace. Formatting the guide does not
              make a second AI request. The action workspace is not stored by TPP in the current
              design; do not add student-specific information to PLC notes.
            </p>
          </div>

          <div className="help-notes">
            <h3>Daily formative-assessment analytics</h3>
            <p>
              The Administration view may summarize the types of daily formative checks already
              written into submitted lesson plans, including items such as exit tickets/slips,
              quick writes, questioning, response signals, retrieval checks, digital checks, and
              other planned strategies. Classification is deterministic and does not send lesson-
              plan text to AI merely to classify an assessment type.
            </p>
            <p>
              These counts describe <strong>planned formative-assessment signals</strong>. They are
              not student assessment results, do not prove the activity was actually administered,
              and are not teacher-performance measures. The analytics API does not return raw
              lesson-plan text, teacher names, or course names for this purpose.
            </p>
          </div>

          <div className="help-notes">
            <h3>Friday professional operational email</h3>
            <p>
              Email delivery is a separately governed infrastructure feature. The normal
              administrator workflow does not require a manual weekly-email button. When automatic
              delivery is activated, TPP first sends a courtesy reminder at 2:00 PM Friday only to
              teachers who still have a required submission missing. At 3:30 PM Friday, eligible
              school administrators receive the aggregate school status. The Anniston Pilot uses
              the school-local <strong>America/Chicago</strong> timezone. The approved application
              From address is <strong>notifications@planner.guidedscholar.ai</strong>.
            </p>
            <p>
              The administrator email is limited to aggregate current-week closeout and
              following-week lesson-plan counts plus a link back to authenticated TPP. It does not
              include teacher names, class-level exception lists, reflection text, lesson-plan
              content, AI-generated instructional insight, student information, or
              teacher-quality/performance scores. Named operational follow-up remains inside the
              authenticated application.
            </p>
            <p>
              Automatic delivery is enabled only through a controlled release after the approved
              SES sender, scheduled-delivery database migration, isolated service-role worker,
              least-privilege IAM, Help/privacy review, and exact Friday schedules are verified.
              A manual send path, if retained, is for controlled operational recovery rather than
              the normal administrator workflow.
            </p>
          </div>
        </section>
      )}

      {isPlatformAdmin && (
        <section className="help-section">
          <h3>Platform Owner workflow</h3>
          <div className="help-notes">
            <p>
              Open <strong>Administration</strong>, then choose the Platform Owner-only
              <strong> Owner</strong> tab. Owner reporting is consolidated there instead of mixing
              Platform Owner controls into school administration or using floating report buttons.
              The Owner tab contains product-usage reporting, Pilot feedback, the pre-TPP teacher
              baseline, Reflection Intelligence adoption, governed standards operations, and AI
              cost reporting.
            </p>
            <p>
              <strong>Product usage</strong> is for product adoption, not teacher evaluation. It
              shows the authorized → authenticated → active onboarding funnel, measured curriculum
              setup pathways, weekly planning and AI usage, PDF review activity, submissions,
              closeouts, and Pilot survey response counts.
            </p>
            <p>
              <strong>Reflection Intelligence adoption</strong> reports product-use counts such as
              private recaps generated, aggregate School Reflection Summaries generated, PLC Meeting
              Guide use, and, when activated, minimized administrator-digest delivery. These are
              product adoption/operations signals. They contain no reflection text or student data
              and must not be used to rank staff or infer teacher quality, effort, productivity, or
              performance.
            </p>
            <p>
              <strong>Teacher baseline</strong> reports pre-TPP workload/value measures by school
              without returning teacher identity to the Owner view. Use it later as a comparison
              point for planning time, usefulness, reflection reuse, and PLC/faculty use. Optional
              comments are professional product/process feedback and remain subject to the no-student-data boundary.
            </p>
            <p>
              TPP uses existing authoritative records where they already exist. Interaction metrics
              that could not previously be inferred — such as Excel versus Build in TPP or PDF
              viewing — begin when the telemetry release is deployed. A zero before that point does
              not prove a feature was never used. Passive product telemetry records bounded event
              keys only and does not copy teacher planning/reflection text into the telemetry table.
            </p>
            <p>
              <strong>Active TPP interaction time</strong> is a Platform Owner product-effectiveness
              measure, not an administrator or teacher-performance measure. TPP estimates it with
              fixed 30-second activity heartbeats only while the TPP tab is visible and has recent
              interaction; hidden or idle tabs stop counting. The first 14 days of measured use for
              each teacher are reported as onboarding/familiarization and later use as steady state.
              Active TPP interaction time is not total teacher planning time and is not exposed to
              school or district administrators.
            </p>
          </div>
        </section>
      )}

      <section className="help-section">
        <h3>Pilot support checklist</h3>
        <p>
          If something does not look right, first confirm the selected class and Monday-starting
          week, refresh or reopen the saved week, and note the exact action that produced the issue.
          Do not enter student information into a support description or screenshot.
        </p>
      </section>
    </section>
  );
}
