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
            closeout, surveys, administration, and Platform Owner reporting.
          </p>
        </div>
      </div>
      <div className="guidance-card">
        <strong>Data boundary</strong>
        <p>
          TPP is for educator/account information, curriculum, standards, schedules, lesson plans,
          weekly reflection, and related professional planning content. Do not enter student names,
          IDs, grades, IEP/504 information, health or discipline information, identifiable student
          work, or other student-specific information. Use class- or group-level instructional
          observations.
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
              class's normal meeting days that first week — from one lesson for a once-weekly class
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
              the next available class meeting. TPP then uses the class's saved Curriculum & Pacing,
              independent progress, schedule, school calendar, schedule exceptions, and
              teacher-selected carry-forward. Review the scheduled lessons and explicitly confirm
              the week's curriculum before continuing.
            </p>
            <p>
              <strong>3. Save authoritative standards.</strong> Confirm the governed standards
              relevant to this week's scheduled curriculum.
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
              only. TPP does not generate or rewrite reflection responses.
            </p>
            <p>
              <strong>3. Review the Completed Weekly Packet.</strong> Review the immutable packet
              containing that week's Instructional Planning Framework, Week at a Glance, and
              teacher-authored reflection. View, Download, and Print remain available.
            </p>
            <p>
              <strong>4. Continue to the following week.</strong> TPP moves to the next Monday and
              uses that class's accumulated pacing progress plus your carry-forward decisions.
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
              that class's progress cursor, so building another week must not duplicate them.
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
              teacher-authored reflection to that same week's plan. The following week's lesson
              plan appears under its own Monday-starting week and receives a completed packet only
              after that week's Friday closeout.
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
              baseline, governed standards operations, and AI cost reporting.
            </p>
            <p>
              <strong>Product usage</strong> is for product adoption, not teacher evaluation. It
              shows the authorized → authenticated → active onboarding funnel, measured curriculum
              setup pathways, weekly planning and AI usage, PDF review activity, submissions,
              closeouts, and Pilot survey response counts.
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
