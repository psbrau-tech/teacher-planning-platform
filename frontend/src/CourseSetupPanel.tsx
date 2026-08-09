import { useMemo, useState } from "react";
import { parseCurriculumRows } from "./curriculumRows";
import { StandardsCourseMappingPanel } from "./StandardsCourseMappingPanel";

type Curriculum = {
  id: string;
  school_id: string;
  name: string;
  version: string;
  standards_family: string | null;
  is_active: boolean;
};

type MeetingPattern = {
  schedule_type: "period" | "block" | "custom";
  weekdays: number[];
  start_time: string;
  end_time: string;
  effective_start: string;
  effective_end: string;
  rotation_label: string | null;
};

type Assignment = {
  id: string;
  teacher_id: string;
  school_id: string;
  course_name: string;
  course_code: string | null;
  curriculum_id: string;
  grade_band: string | null;
  meeting_patterns: MeetingPattern[];
  revision: number;
  updated_at: string;
};

type Props = {
  accessToken: string;
  schoolId: string;
  assignments: Assignment[];
  curricula: Curriculum[];
  selectedAssignmentId: string;
  disabled?: boolean;
  onSelectAssignment: (assignmentId: string) => void;
  onAssignmentsChanged: (assignments: Assignment[]) => void;
  onCurriculaChanged: (curricula: Curriculum[]) => void;
  onMessage: (message: string) => void;
  onError: (message: string) => void;
  onStandardsMappingSaved: () => void;
};

function academicVersion(pattern?: MeetingPattern): string {
  if (!pattern?.effective_start || !pattern.effective_end) return "Current year";
  const start = Number(pattern.effective_start.slice(0, 4));
  const end = Number(pattern.effective_end.slice(0, 4));
  return Number.isFinite(start) && Number.isFinite(end)
    ? `${start}-${String(end).slice(-2)}`
    : "Current year";
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    return typeof body.detail === "string" && body.detail.trim() ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

function downloadPacingTemplate() {
  const content = [
    "# TPP Curriculum & Pacing template",
    "# One lesson per line:",
    "# Unit | Lesson | Standards | Learning targets | Assessment | Optional minutes override",
    "Introduction | Course orientation and expectations | | Explain course expectations | Exit ticket |",
    "Drill and Ceremony | Attention, Parade Rest, At Ease, Rest | | Demonstrate stationary positions | Performance check |",
  ].join("\n");
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = url;
  anchor.download = "tpp-curriculum-pacing-template.txt";
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function CourseSetupPanel({
  accessToken,
  schoolId,
  assignments,
  curricula,
  selectedAssignmentId,
  disabled = false,
  onSelectAssignment,
  onAssignmentsChanged,
  onCurriculaChanged,
  onMessage,
  onError,
  onStandardsMappingSaved,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [pacingAssignmentId, setPacingAssignmentId] = useState(selectedAssignmentId);
  const [reuseCurriculumId, setReuseCurriculumId] = useState("");
  const editing = assignments.find((item) => item.id === editingId) ?? null;
  const pacingAssignment = assignments.find((item) => item.id === pacingAssignmentId)
    ?? assignments.find((item) => item.id === selectedAssignmentId)
    ?? assignments[0]
    ?? null;
  const pattern = editing?.meeting_patterns[0];
  const currentPacing = curricula.find((item) => item.id === pacingAssignment?.curriculum_id) ?? null;
  const sortedAssignments = useMemo(
    () => [...assignments].sort((a, b) => {
      const aTime = a.meeting_patterns[0]?.start_time ?? "";
      const bTime = b.meeting_patterns[0]?.start_time ?? "";
      return aTime.localeCompare(bTime) || a.course_name.localeCompare(b.course_name);
    }),
    [assignments],
  );

  const authHeaders = { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" };

  async function createPlaceholderCurriculum(courseName: string, version: string): Promise<Curriculum> {
    const response = await fetch("/api/v1/curricula", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        name: `${courseName} Curriculum & Pacing`,
        version,
        standards_family: null,
        lessons: [],
      }),
    });
    if (!response.ok) throw new Error(await readError(response, "Course pacing placeholder could not be created."));
    const created = await response.json() as Curriculum;
    onCurriculaChanged([...curricula, created].sort((a, b) => a.name.localeCompare(b.name)));
    return created;
  }

  async function saveClass(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const weekdays = form.getAll("weekday").map((value) => Number(value));
    const courseName = String(form.get("course_name") ?? "").trim();
    const start = String(form.get("effective_start") ?? "");
    const end = String(form.get("effective_end") ?? "");
    setWorking(true);
    onError("");
    try {
      let curriculumId = String(form.get("curriculum_id") ?? "");
      if (!curriculumId) {
        const version = start && end ? `${start.slice(0, 4)}-${end.slice(2, 4)}` : "Current year";
        curriculumId = (await createPlaceholderCurriculum(courseName, version)).id;
      }
      const payload = {
        school_id: schoolId,
        course_name: courseName,
        course_code: String(form.get("course_code") ?? "") || null,
        curriculum_id: curriculumId,
        grade_band: String(form.get("grade_band") ?? "") || null,
        meeting_patterns: [{
          schedule_type: String(form.get("schedule_type") ?? "period"),
          weekdays,
          start_time: String(form.get("start_time") ?? "08:00"),
          end_time: String(form.get("end_time") ?? "08:50"),
          effective_start: start,
          effective_end: end,
          rotation_label: String(form.get("rotation_label") ?? "") || null,
        }],
        expected_revision: editing?.revision ?? null,
      };
      const response = await fetch(
        editing ? `/api/v1/teaching-assignments/${encodeURIComponent(editing.id)}` : "/api/v1/teaching-assignments",
        { method: editing ? "PUT" : "POST", headers: authHeaders, body: JSON.stringify(payload) },
      );
      if (!response.ok) throw new Error(await readError(response, "Class schedule could not be saved."));
      const saved = await response.json() as Assignment;
      const next = editing
        ? assignments.map((item) => item.id === saved.id ? saved : item)
        : [...assignments, saved];
      onAssignmentsChanged(next);
      onSelectAssignment(saved.id);
      setPacingAssignmentId(saved.id);
      setEditingId(null);
      onMessage(`${saved.course_name} class schedule saved.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Class schedule could not be saved.");
    } finally {
      setWorking(false);
    }
  }

  async function removeClass(assignment: Assignment) {
    const confirmed = window.confirm(
      `Remove ${assignment.course_name} from active planning?\n\nExisting planning and submission history will be preserved.`,
    );
    if (!confirmed) return;
    setWorking(true);
    onError("");
    try {
      const response = await fetch(`/api/v1/teaching-assignments/${encodeURIComponent(assignment.id)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error(await readError(response, "Course could not be removed."));
      const next = assignments.filter((item) => item.id !== assignment.id);
      onAssignmentsChanged(next);
      if (selectedAssignmentId === assignment.id) onSelectAssignment(next[0]?.id ?? "");
      if (pacingAssignmentId === assignment.id) setPacingAssignmentId(next[0]?.id ?? "");
      onMessage(`${assignment.course_name} removed from active planning.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Course could not be removed.");
    } finally {
      setWorking(false);
    }
  }

  async function attachCurriculum(assignment: Assignment, curriculumId: string) {
    const basePattern = assignment.meeting_patterns[0];
    if (!basePattern) throw new Error("This class schedule has no meeting pattern.");
    const response = await fetch(`/api/v1/teaching-assignments/${encodeURIComponent(assignment.id)}`, {
      method: "PUT",
      headers: authHeaders,
      body: JSON.stringify({
        school_id: assignment.school_id,
        course_name: assignment.course_name,
        course_code: assignment.course_code,
        curriculum_id: curriculumId,
        grade_band: assignment.grade_band,
        meeting_patterns: assignment.meeting_patterns,
        expected_revision: assignment.revision,
      }),
    });
    if (!response.ok) throw new Error(await readError(response, "Curriculum & Pacing could not be attached."));
    const updated = await response.json() as Assignment;
    onAssignmentsChanged(assignments.map((item) => item.id === updated.id ? updated : item));
    return updated;
  }

  async function useExistingCurriculum() {
    if (!pacingAssignment || !reuseCurriculumId) return;
    setWorking(true);
    onError("");
    try {
      const updated = await attachCurriculum(pacingAssignment, reuseCurriculumId);
      onMessage(`Curriculum & Pacing updated for ${updated.course_name}.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum & Pacing could not be attached.");
    } finally {
      setWorking(false);
    }
  }

  async function savePacing(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!pacingAssignment) return;
    const form = new FormData(event.currentTarget);
    let rows;
    try {
      rows = parseCurriculumRows(String(form.get("lesson_rows") ?? ""));
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum & Pacing rows are invalid.");
      return;
    }
    setWorking(true);
    onError("");
    try {
      const response = await fetch("/api/v1/curricula", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          name: String(form.get("name") ?? ""),
          version: String(form.get("version") ?? ""),
          standards_family: String(form.get("standards_family") ?? "") || null,
          lessons: rows,
        }),
      });
      if (!response.ok) throw new Error(await readError(response, "Curriculum & Pacing could not be saved."));
      const curriculum = await response.json() as Curriculum;
      onCurriculaChanged([...curricula, curriculum].sort((a, b) => a.name.localeCompare(b.name)));
      const updated = await attachCurriculum(pacingAssignment, curriculum.id);
      onMessage(`Curriculum & Pacing saved and attached to ${updated.course_name}.`);
      event.currentTarget.reset();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum & Pacing could not be saved.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section className="panel course-setup-panel">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Course Setup</p>
          <h2>Your class schedules</h2>
          <p className="supporting">Create the classes you actually teach first. Curriculum & Pacing can be added, reused, or changed afterward.</p>
        </div>
      </div>

      {assignments.length > 0 && (
        <div className="grid course-management-grid">
          {sortedAssignments.map((assignment) => {
            const coursePattern = assignment.meeting_patterns[0];
            const curriculum = curricula.find((item) => item.id === assignment.curriculum_id);
            return (
              <article className={`card ${selectedAssignmentId === assignment.id ? "selected" : ""}`} key={assignment.id}>
                <div className="card-row"><span className="badge">Revision {assignment.revision}</span><span className="status">Active</span></div>
                <h3>{assignment.course_name}</h3>
                <p>{coursePattern ? `${coursePattern.start_time.slice(0, 5)}–${coursePattern.end_time.slice(0, 5)}` : "Schedule not set"}</p>
                <small>{curriculum ? `${curriculum.name} · ${curriculum.version}` : "Curriculum & Pacing not added"}</small>
                <div className="button-row">
                  <button type="button" className="secondary" onClick={() => { setEditingId(assignment.id); onSelectAssignment(assignment.id); }}>Edit class</button>
                  <button type="button" className="link-button" onClick={() => { onSelectAssignment(assignment.id); setPacingAssignmentId(assignment.id); }}>Curriculum & Pacing</button>
                  <button type="button" className="link-button danger-link" onClick={() => void removeClass(assignment)}>Remove</button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <details className="setup-section" open={assignments.length === 0 || editing !== null}>
        <summary>{editing ? `Edit ${editing.course_name}` : "Add a class schedule"}</summary>
        <form className="form-grid" key={editing?.id ?? "new-class"} onSubmit={(event) => void saveClass(event)}>
          <label>Course name<input name="course_name" required defaultValue={editing?.course_name ?? ""} placeholder="Army JROTC LET 1" /></label>
          <label>Course code<input name="course_code" defaultValue={editing?.course_code ?? ""} placeholder="JROTC-1" /></label>
          <label>Grade(s)<input name="grade_band" defaultValue={editing?.grade_band ?? ""} placeholder="9–12" /></label>
          <label>Curriculum & Pacing
            <select name="curriculum_id" defaultValue={editing?.curriculum_id ?? ""}>
              <option value="">Add after class setup</option>
              {curricula.map((curriculum) => <option value={curriculum.id} key={curriculum.id}>{curriculum.name} · {curriculum.version}</option>)}
            </select>
          </label>
          <label>Schedule type<select name="schedule_type" defaultValue={pattern?.schedule_type ?? "period"}><option value="period">Period</option><option value="block">Block</option><option value="custom">Custom</option></select></label>
          <label>Rotation label<input name="rotation_label" defaultValue={pattern?.rotation_label ?? ""} placeholder="Daily, A Day, B Day" /></label>
          <label>Start time<input name="start_time" type="time" defaultValue={pattern?.start_time.slice(0, 5) ?? "08:00"} required /></label>
          <label>End time<input name="end_time" type="time" defaultValue={pattern?.end_time.slice(0, 5) ?? "08:50"} required /></label>
          <label>Effective start<input name="effective_start" type="date" defaultValue={pattern?.effective_start ?? "2026-08-10"} required /></label>
          <label>Effective end<input name="effective_end" type="date" defaultValue={pattern?.effective_end ?? "2027-05-28"} required /></label>
          <fieldset className="full-width"><legend>Meeting weekdays</legend><div className="weekday-row">{[[1,"Mon"],[2,"Tue"],[3,"Wed"],[4,"Thu"],[5,"Fri"]].map(([value,label]) => <label className="check" key={value}><input type="checkbox" name="weekday" value={value} defaultChecked={!pattern || pattern.weekdays.includes(Number(value))} />{label}</label>)}</div></fieldset>
          <div className="form-actions full-width">
            <button className="primary" disabled={disabled || working}>{working ? "Saving…" : editing ? "Save class changes" : "Save class schedule"}</button>
            {editing && <button type="button" className="secondary" onClick={() => setEditingId(null)}>Cancel edit</button>}
          </div>
        </form>
      </details>

      {assignments.length > 0 && (
        <section className="setup-section pacing-setup" id="curriculum-pacing">
          <div className="section-heading compact">
            <div>
              <p className="eyebrow">Curriculum & Pacing</p>
              <h2>Set the instructional sequence</h2>
              <p className="supporting">TPP uses this longer-term sequence to build each week, then Friday validation keeps the section's pacing position current when instruction is completed, moved, skipped, or carried forward.</p>
            </div>
            <button type="button" className="secondary" onClick={downloadPacingTemplate}>Download pacing template</button>
          </div>
          <div className="toolbar">
            <label>Class<select value={pacingAssignment?.id ?? ""} onChange={(event) => { setPacingAssignmentId(event.target.value); onSelectAssignment(event.target.value); }}>
              {sortedAssignments.map((assignment) => <option value={assignment.id} key={assignment.id}>{assignment.course_name} · {assignment.meeting_patterns[0]?.start_time.slice(0, 5) ?? ""}</option>)}
            </select></label>
            <div className="guidance-card compact-guidance"><strong>Current pacing source</strong><p>{currentPacing ? `${currentPacing.name} · ${currentPacing.version}` : "Not added yet"}</p></div>
          </div>

          {pacingAssignment && curricula.length > 1 && (
            <div className="toolbar reuse-pacing">
              <label>Reuse an existing curriculum<select value={reuseCurriculumId} onChange={(event) => setReuseCurriculumId(event.target.value)}><option value="">Choose an existing sequence</option>{curricula.filter((item) => item.id !== pacingAssignment.curriculum_id).map((item) => <option value={item.id} key={item.id}>{item.name} · {item.version}</option>)}</select></label>
              <button type="button" className="secondary" disabled={!reuseCurriculumId || working} onClick={() => void useExistingCurriculum()}>Use this curriculum</button>
            </div>
          )}

          <details>
            <summary>Add or replace this class's pacing sequence</summary>
            <p className="supporting">Use the TPP template for predictable import. File-upload support for additional document formats can be added after the pilot without changing the pacing model.</p>
            <form className="form-grid" onSubmit={(event) => void savePacing(event)}>
              <label>Curriculum name<input name="name" required defaultValue={pacingAssignment ? `${pacingAssignment.course_name} Curriculum & Pacing` : ""} /></label>
              <label>Version<input name="version" required defaultValue={academicVersion(pacingAssignment?.meeting_patterns[0])} /></label>
              <label>Standards family<input name="standards_family" placeholder="Army JROTC / Alabama" /></label>
              <label className="full-width">Pacing sequence<textarea name="lesson_rows" rows={12} required placeholder="Unit | Lesson | Standards | Learning targets | Assessment | Optional minutes override" /></label>
              <div className="guidance-card full-width"><strong>Normal lesson minutes come from the class schedule.</strong><p>Use the optional final column only when a lesson intentionally spans multiple meetings or uses a different duration.</p></div>
              <div className="form-actions full-width"><button className="primary" disabled={disabled || working}>{working ? "Saving…" : "Save Curriculum & Pacing"}</button></div>
            </form>
          </details>
        </section>
      )}

      {selectedAssignmentId && (
        <section className="setup-section standards-setup">
          <div className="section-heading compact"><div><p className="eyebrow">Standards setup</p><h2>Authoritative standards mapping</h2><p className="supporting">Set the primary standards course once here. Weekly Plan will use this mapping without asking you to repeat it each week.</p></div></div>
          <StandardsCourseMappingPanel accessToken={accessToken} assignmentId={selectedAssignmentId} disabled={disabled || working} onMappingSaved={onStandardsMappingSaved} />
          <p className="muted-text">Some classes may legitimately use supplemental standards from another course. Multi-source standards mapping is retained as a post-demo enhancement; TPP will not fabricate standards outside the selected approved source.</p>
        </section>
      )}
    </section>
  );
}