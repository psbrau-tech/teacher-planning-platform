import { useEffect, useMemo, useState } from "react";
import { parseCurriculumRows } from "./curriculumRows";
import { PacingSequenceEditor, type PacingInitialRow } from "./PacingSequenceEditor";
import { downloadPacingTemplate } from "./pacingTemplate";
import { StandardsCourseMappingPanel } from "./StandardsCourseMappingPanel";

type Curriculum = {
  id: string;
  school_id: string;
  name: string;
  version: string;
  standards_family: string | null;
  is_active: boolean;
};

type CurriculumLessonDetail = {
  sequence: number;
  unit_title: string;
  lesson_title: string;
  estimated_minutes: number | null;
  standards: string[];
  learning_targets: string[];
  assessment: string;
  can_split: boolean;
};

type CurriculumDetail = Curriculum & {
  lessons: CurriculumLessonDetail[];
  active_class_count: number;
  locked_through_sequence: number;
};

type CurriculumRevisionRead = {
  curriculum: CurriculumDetail;
  replaced_curriculum_id: string;
  active_classes_updated: number;
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
  curriculum_id: string | null;
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
  onOpenWeeklyPlan?: (assignmentId: string) => void;
};

type PacingMode = "upload" | "build" | "reuse" | null;

function academicVersion(pattern?: MeetingPattern): string {
  if (!pattern?.effective_start || !pattern.effective_end) return "Current year";
  const start = Number(pattern.effective_start.slice(0, 4));
  const end = Number(pattern.effective_end.slice(0, 4));
  return Number.isFinite(start) && Number.isFinite(end)
    ? `${start}-${String(end).slice(-2)}`
    : "Current year";
}

function weekdayLabel(weekdays: number[]): string {
  const labels = ["Mon", "Tue", "Wed", "Thu", "Fri"];
  return weekdays.map((value) => labels[value - 1]).filter(Boolean).join(", ");
}

function classPeriodMinutes(startTime: string, endTime: string): number | null {
  const parseMinutes = (value: string): number | null => {
    const match = /^(\d{2}):(\d{2})/.exec(value);
    if (!match) return null;
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    if (hours > 23 || minutes > 59) return null;
    return (hours * 60) + minutes;
  };
  const start = parseMinutes(startTime);
  const end = parseMinutes(endTime);
  if (start === null || end === null || end <= start) return null;
  return end - start;
}

function classScheduleLabel(pattern: MeetingPattern): string {
  const start = pattern.start_time.slice(0, 5);
  const end = pattern.end_time.slice(0, 5);
  const minutes = classPeriodMinutes(pattern.start_time, pattern.end_time);
  const duration = minutes === null ? "" : ` · ${minutes} minute${minutes === 1 ? "" : "s"}`;
  return `${weekdayLabel(pattern.weekdays)} · ${start}–${end}${duration}`;
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    return typeof body.detail === "string" && body.detail.trim() ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  window.document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function StepMarker({
  number,
  title,
  complete,
  active,
}: {
  number: number;
  title: string;
  complete: boolean;
  active: boolean;
}) {
  return (
    <div className={`setup-step-marker ${complete ? "complete" : ""} ${active ? "active" : ""}`}>
      <span className="step-number" aria-hidden="true">{complete ? "✓" : number}</span>
      <span><strong>Step {number}</strong><small>{title}</small></span>
    </div>
  );
}

function detailRows(detail: CurriculumDetail): PacingInitialRow[] {
  return detail.lessons.map((lesson) => ({
    unit: lesson.unit_title,
    lesson: lesson.lesson_title,
    targets: lesson.learning_targets.join("; "),
    assessment: lesson.assessment,
  }));
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
  onOpenWeeklyPlan,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [working, setWorking] = useState(false);
  const [pacingMode, setPacingMode] = useState<PacingMode>(null);
  const [reuseCurriculumId, setReuseCurriculumId] = useState("");
  const [standardsMapped, setStandardsMapped] = useState(false);
  const [standardsEditing, setStandardsEditing] = useState(false);
  const [curriculumDetail, setCurriculumDetail] = useState<CurriculumDetail | null>(null);
  const [sharedEditConfirmed, setSharedEditConfirmed] = useState(false);
  const [copyVersionOpen, setCopyVersionOpen] = useState(false);

  const selectedAssignment = assignments.find((item) => item.id === selectedAssignmentId) ?? null;
  const editing = assignments.find((item) => item.id === editingId) ?? null;
  const pattern = editing?.meeting_patterns[0];
  const currentPacing = selectedAssignment?.curriculum_id
    ? curricula.find((item) => item.id === selectedAssignment.curriculum_id) ?? null
    : null;
  const sortedAssignments = useMemo(
    () => [...assignments].sort((a, b) => {
      const aTime = a.meeting_patterns[0]?.start_time ?? "";
      const bTime = b.meeting_patterns[0]?.start_time ?? "";
      return aTime.localeCompare(bTime) || a.course_name.localeCompare(b.course_name);
    }),
    [assignments],
  );
  const authHeaders = {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };
  const step1Complete = Boolean(selectedAssignment);
  const step2Complete = Boolean(selectedAssignment?.curriculum_id && currentPacing);
  const step3Complete = step2Complete && standardsMapped;
  const curriculumManagerOpen = curriculumDetail !== null || copyVersionOpen;
  const firstWeekMeetings = Math.max(
    1,
    selectedAssignment?.meeting_patterns[0]?.weekdays.length ?? 1,
  );

  useEffect(() => {
    setStandardsMapped(false);
    setStandardsEditing(false);
    setPacingMode(null);
    setReuseCurriculumId("");
    setCurriculumDetail(null);
    setSharedEditConfirmed(false);
    setCopyVersionOpen(false);
  }, [selectedAssignmentId]);

  async function refreshTeacherData() {
    const [curriculaResponse, assignmentsResponse] = await Promise.all([
      fetch("/api/v1/curricula", { headers: { Authorization: `Bearer ${accessToken}` } }),
      fetch("/api/v1/teaching-assignments", {
        headers: { Authorization: `Bearer ${accessToken}` },
      }),
    ]);
    if (!curriculaResponse.ok || !assignmentsResponse.ok) {
      throw new Error("Teacher planning data could not be refreshed after the curriculum change.");
    }
    onCurriculaChanged(await curriculaResponse.json() as Curriculum[]);
    onAssignmentsChanged(await assignmentsResponse.json() as Assignment[]);
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
      const payload = {
        school_id: schoolId,
        course_name: courseName,
        course_code: String(form.get("course_code") ?? "") || null,
        curriculum_id: editing?.curriculum_id ?? null,
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
        editing
          ? `/api/v1/teaching-assignments/${encodeURIComponent(editing.id)}`
          : "/api/v1/teaching-assignments",
        {
          method: editing ? "PUT" : "POST",
          headers: authHeaders,
          body: JSON.stringify(payload),
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Class schedule could not be saved."));
      }
      const saved = await response.json() as Assignment;
      const next = editing
        ? assignments.map((item) => item.id === saved.id ? saved : item)
        : [...assignments, saved];
      onAssignmentsChanged(next);
      onSelectAssignment(saved.id);
      setEditingId(null);
      setPacingMode(null);
      onMessage(`${saved.course_name} saved. Step 1 complete — add Curriculum & Pacing next.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Class schedule could not be saved.");
    } finally {
      setWorking(false);
    }
  }

  async function removeClass(assignment: Assignment) {
    if (!window.confirm(
      `Remove ${assignment.course_name} from active planning?\n\nExisting planning, submitted packets, and reusable curricula will be preserved.`,
    )) return;
    setWorking(true);
    onError("");
    try {
      const response = await fetch(
        `/api/v1/teaching-assignments/${encodeURIComponent(assignment.id)}`,
        { method: "DELETE", headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Class could not be removed."));
      }
      const next = assignments.filter((item) => item.id !== assignment.id);
      onAssignmentsChanged(next);
      if (selectedAssignmentId === assignment.id) onSelectAssignment(next[0]?.id ?? "");
      onMessage(
        `${assignment.course_name} removed from active planning. Its planning history is preserved.`,
      );
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Class could not be removed.");
    } finally {
      setWorking(false);
    }
  }

  async function attachCurriculum(assignment: Assignment, curriculumId: string) {
    if (!assignment.meeting_patterns[0]) {
      throw new Error("This class schedule has no meeting pattern.");
    }
    const response = await fetch(
      `/api/v1/teaching-assignments/${encodeURIComponent(assignment.id)}`,
      {
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
      },
    );
    if (!response.ok) {
      throw new Error(await readError(response, "Curriculum & Pacing could not be attached."));
    }
    const updated = await response.json() as Assignment;
    onAssignmentsChanged(assignments.map((item) => item.id === updated.id ? updated : item));
    return updated;
  }

  async function useExistingCurriculum() {
    if (!selectedAssignment || !reuseCurriculumId) return;
    setWorking(true);
    onError("");
    try {
      const updated = await attachCurriculum(selectedAssignment, reuseCurriculumId);
      setPacingMode(null);
      setReuseCurriculumId("");
      onMessage(`Curriculum & Pacing attached to ${updated.course_name}. Step 2 complete.`);
    } catch (caught) {
      onError(
        caught instanceof Error
          ? caught.message
          : "Curriculum & Pacing could not be attached.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function retireCurriculum(curriculum: Curriculum) {
    if (!window.confirm(
      `Remove ${curriculum.name} · ${curriculum.version} from your active curriculum list?\n\nThis does not delete historical planning records.`,
    )) return;
    setWorking(true);
    onError("");
    try {
      const response = await fetch(`/api/v1/curricula/${encodeURIComponent(curriculum.id)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) {
        throw new Error(await readError(response, "Curriculum could not be removed."));
      }
      onCurriculaChanged(curricula.filter((item) => item.id !== curriculum.id));
      if (reuseCurriculumId === curriculum.id) setReuseCurriculumId("");
      onMessage(`${curriculum.name} removed from your active curriculum list.`);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum could not be removed.");
    } finally {
      setWorking(false);
    }
  }

  async function savePacing(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedAssignment) return;
    const form = new FormData(event.currentTarget);
    let rows;
    try {
      rows = parseCurriculumRows(String(form.get("lesson_rows") ?? ""));
      if (!rows.length) throw new Error("Add at least one pacing lesson before saving.");
    } catch (caught) {
      onError(
        caught instanceof Error ? caught.message : "Curriculum & Pacing rows are invalid.",
      );
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
          standards_family: currentPacing?.standards_family ?? null,
          lessons: rows,
        }),
      });
      if (!response.ok) {
        throw new Error(await readError(response, "Curriculum & Pacing could not be saved."));
      }
      const curriculum = await response.json() as Curriculum;
      onCurriculaChanged(
        [...curricula, curriculum].sort((a, b) => a.name.localeCompare(b.name)),
      );
      const updated = await attachCurriculum(selectedAssignment, curriculum.id);
      setPacingMode(null);
      onMessage(
        `${rows.length} pacing lesson${rows.length === 1 ? "" : "s"} saved and attached to ${updated.course_name}. Step 2 complete.`,
      );
    } catch (caught) {
      onError(
        caught instanceof Error
          ? caught.message
          : "Curriculum & Pacing could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  async function loadCurriculumDetail() {
    if (!currentPacing) return;
    setWorking(true);
    onError("");
    try {
      const response = await fetch(`/api/v1/curricula/${encodeURIComponent(currentPacing.id)}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) {
        throw new Error(await readError(response, "Curriculum could not be opened."));
      }
      const detail = await response.json() as CurriculumDetail;
      setCurriculumDetail(detail);
      setSharedEditConfirmed(detail.active_class_count <= 1);
      setCopyVersionOpen(false);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum could not be opened.");
    } finally {
      setWorking(false);
    }
  }

  async function downloadCurriculum() {
    if (!currentPacing) return;
    setWorking(true);
    onError("");
    try {
      const response = await fetch(
        `/api/v1/curricula/${encodeURIComponent(currentPacing.id)}/export.xlsx`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Curriculum download failed."));
      }
      const blob = await response.blob();
      const safe = `${currentPacing.name}-${currentPacing.version}`.replace(/[^A-Za-z0-9._-]+/g, "-");
      downloadBlob(blob, `${safe || "curriculum"}.xlsx`);
      onMessage("Current Curriculum & Pacing downloaded as Excel.");
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum download failed.");
    } finally {
      setWorking(false);
    }
  }

  async function createCurriculumCopy(
    source: Curriculum,
    name: string,
    version: string,
  ): Promise<Curriculum> {
    const response = await fetch(`/api/v1/curricula/${encodeURIComponent(source.id)}/copy`, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({ name, version }),
    });
    if (!response.ok) {
      throw new Error(await readError(response, "Curriculum copy could not be created."));
    }
    return await response.json() as Curriculum;
  }

  async function createSeparateCopyForClass() {
    if (!selectedAssignment || !currentPacing) return;
    setWorking(true);
    onError("");
    try {
      const copied = await createCurriculumCopy(
        currentPacing,
        `${currentPacing.name} — ${selectedAssignment.course_name}`,
        currentPacing.version,
      );
      const updated = await attachCurriculum(selectedAssignment, copied.id);
      await refreshTeacherData();
      const detailResponse = await fetch(`/api/v1/curricula/${encodeURIComponent(copied.id)}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!detailResponse.ok) {
        throw new Error(await readError(detailResponse, "Copied curriculum could not be opened."));
      }
      setCurriculumDetail(await detailResponse.json() as CurriculumDetail);
      setSharedEditConfirmed(true);
      setPacingMode(null);
      onMessage(
        `${updated.course_name} now has its own curriculum copy. Edit its future pacing below; other classes remain unchanged.`,
      );
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Class-specific copy could not be created.");
    } finally {
      setWorking(false);
    }
  }

  async function createNextVersion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!currentPacing) return;
    const form = new FormData(event.currentTarget);
    setWorking(true);
    onError("");
    try {
      const copied = await createCurriculumCopy(
        currentPacing,
        String(form.get("copy_name") ?? currentPacing.name),
        String(form.get("copy_version") ?? "Next year"),
      );
      await refreshTeacherData();
      setCopyVersionOpen(false);
      onMessage(
        `${copied.name} · ${copied.version} created from the current saved curriculum. It is available under Reuse mine and has no class progress attached.`,
      );
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "New curriculum version could not be created.");
    } finally {
      setWorking(false);
    }
  }

  async function saveCurriculumRevision(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!curriculumDetail) return;
    const form = new FormData(event.currentTarget);
    let rows;
    try {
      rows = parseCurriculumRows(String(form.get("lesson_rows") ?? ""));
      if (!rows.length) throw new Error("The curriculum must contain at least one lesson.");
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Curriculum pacing rows are invalid.");
      return;
    }
    setWorking(true);
    onError("");
    try {
      const response = await fetch(
        `/api/v1/curricula/${encodeURIComponent(curriculumDetail.id)}/pacing`,
        {
          method: "PUT",
          headers: authHeaders,
          body: JSON.stringify({
            name: String(form.get("name") ?? curriculumDetail.name),
            version: String(form.get("version") ?? curriculumDetail.version),
            lessons: rows,
          }),
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Current-year curriculum changes could not be saved."));
      }
      const result = await response.json() as CurriculumRevisionRead;
      await refreshTeacherData();
      setCurriculumDetail(null);
      setSharedEditConfirmed(false);
      onMessage(
        `Curriculum & Pacing updated for ${result.active_classes_updated} active class${result.active_classes_updated === 1 ? "" : "es"}. Historical weekly records were preserved.`,
      );
    } catch (caught) {
      onError(
        caught instanceof Error
          ? caught.message
          : "Current-year curriculum changes could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  }

  function renderPacingChoices() {
    return (
      <div className="choice-grid" aria-label="Curriculum and pacing method">
        <button
          type="button"
          className={`choice-card ${pacingMode === "upload" ? "selected" : ""}`}
          onClick={() => setPacingMode("upload")}
        >
          <strong>Upload Excel</strong>
          <span>I already have a year or semester pacing plan.</span>
        </button>
        <button
          type="button"
          className={`choice-card ${pacingMode === "build" ? "selected" : ""}`}
          onClick={() => setPacingMode("build")}
        >
          <strong>Build in TPP</strong>
          <span>I want to enter units and lessons here.</span>
        </button>
        <button
          type="button"
          className={`choice-card ${pacingMode === "reuse" ? "selected" : ""}`}
          onClick={() => setPacingMode("reuse")}
        >
          <strong>Reuse mine</strong>
          <span>I already created this curriculum for another class.</span>
        </button>
      </div>
    );
  }

  function renderPacingMode() {
    if (!selectedAssignment || !pacingMode) return null;
    if (pacingMode === "reuse") {
      return (
        <div className="pacing-mode-panel">
          {curricula.length === 0 ? (
            <div className="empty-state">
              <p>You do not have a saved curriculum to reuse yet. Choose Upload Excel or Build in TPP.</p>
            </div>
          ) : <>
            <label>
              My Curriculum & Pacing
              <select
                value={reuseCurriculumId}
                onChange={(event) => setReuseCurriculumId(event.target.value)}
              >
                <option value="">Choose one of your saved sequences</option>
                {curricula
                  .filter((item) => item.id !== selectedAssignment.curriculum_id)
                  .map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name} · {item.version}
                    </option>
                  ))}
              </select>
            </label>
            <div className="button-row">
              <button
                type="button"
                className="primary"
                disabled={!reuseCurriculumId || working}
                onClick={() => void useExistingCurriculum()}
              >
                Use this curriculum & continue
              </button>
            </div>
            <details className="curriculum-cleanup">
              <summary>Manage my saved curricula</summary>
              <p className="supporting">
                Unused demo or outdated curricula can be retired here. TPP will not remove a
                curriculum that is still attached to an active class.
              </p>
              {curricula.map((item) => (
                <div className="curriculum-cleanup-row" key={item.id}>
                  <span>{item.name} · {item.version}</span>
                  <button
                    type="button"
                    className="link-button danger-link"
                    disabled={working}
                    onClick={() => void retireCurriculum(item)}
                  >
                    Remove from my list
                  </button>
                </div>
              ))}
            </details>
          </>}
        </div>
      );
    }
    return (
      <div className="pacing-mode-panel">
        {pacingMode === "upload" && (
          <div className="guidance-card">
            <strong>Upload, review, then save.</strong>
            <p>
              Loading an Excel workbook reads it into the lesson editor. Nothing is saved until
              you select <strong>Save Curriculum & Pacing & Continue</strong>.
            </p>
            <button type="button" className="secondary" onClick={downloadPacingTemplate}>
              Download current Excel template
            </button>
          </div>
        )}
        {pacingMode === "build" && (
          <div className="guidance-card">
            <strong>Start with a complete first instructional week.</strong>
            <p>
              Enter enough lessons to cover every normal meeting in the first week before you
              begin weekly planning. Based on this class schedule, that is normally
              <strong> {firstWeekMeetings} lesson{firstWeekMeetings === 1 ? "" : "s"}</strong>.
              You can add the rest of the semester or year now or extend future pacing later.
            </p>
          </div>
        )}
        <form className="form-grid" onSubmit={(event) => void savePacing(event)}>
          <label>
            Curriculum name
            <input
              name="name"
              required
              defaultValue={`${selectedAssignment.course_name} Curriculum & Pacing`}
            />
          </label>
          <label>
            Version
            <input
              name="version"
              required
              defaultValue={academicVersion(selectedAssignment.meeting_patterns[0])}
            />
          </label>
          <PacingSequenceEditor disabled={disabled || working} />
          <div className="guidance-card full-width">
            <strong>Each pacing lesson equals one day of class.</strong>
            <p>
              Add one lesson row for every day the class should meet. TPP uses the saved class
              schedule for that day&apos;s instructional minutes and does not split one row across
              multiple days.
            </p>
          </div>
          <div className="form-actions full-width">
            <button className="primary" disabled={disabled || working}>
              {working ? "Saving…" : "Save Curriculum & Pacing & Continue"}
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <section className="panel course-setup-panel">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Course Setup</p>
          <h2>Set up one class at a time</h2>
          <p className="supporting">
            TPP reveals each setup step after the previous step is saved. Class and schedule come
            first; Curriculum & Pacing and standards are separate steps.
          </p>
        </div>
        <button
          type="button"
          className="secondary"
          onClick={() => {
            setEditingId(null);
            onSelectAssignment("");
          }}
        >
          Add another class
        </button>
      </div>

      <div className="setup-stepper" aria-label="Course setup progress">
        <StepMarker number={1} title="Class & Schedule" complete={step1Complete} active={!step1Complete || editing !== null} />
        <StepMarker number={2} title="Curriculum & Pacing" complete={step2Complete} active={step1Complete && (!step2Complete || pacingMode !== null || curriculumManagerOpen)} />
        <StepMarker number={3} title="Standards" complete={step3Complete} active={step2Complete && pacingMode === null && !curriculumManagerOpen && (!step3Complete || standardsEditing)} />
        <StepMarker number={4} title="Ready" complete={step3Complete} active={step3Complete && pacingMode === null && !curriculumManagerOpen && !standardsEditing} />
      </div>

      {working && (
        <p className="working-status" role="status" aria-live="polite">
          <span className="button-spinner" aria-hidden="true" />
          Updating Course Setup…
        </p>
      )}

      {assignments.length > 0 && (
        <section className="setup-class-picker">
          <div className="section-heading compact">
            <div><p className="eyebrow">Your classes</p><h3>Select a class to view or edit setup</h3></div>
          </div>
          <div className="grid course-management-grid">
            {sortedAssignments.map((assignment) => {
              const coursePattern = assignment.meeting_patterns[0];
              const curriculum = assignment.curriculum_id
                ? curricula.find((item) => item.id === assignment.curriculum_id)
                : null;
              return (
                <article className={`card ${selectedAssignmentId === assignment.id ? "selected" : ""}`} key={assignment.id}>
                  <div className="card-row">
                    <span className="badge">Revision {assignment.revision}</span>
                    <span className="status">{curriculum ? "Pacing added" : "Setup in progress"}</span>
                  </div>
                  <h3>{assignment.course_name}</h3>
                  <p>{coursePattern ? classScheduleLabel(coursePattern) : "Schedule not set"}</p>
                  <small>{curriculum ? `${curriculum.name} · ${curriculum.version}` : "Curriculum & Pacing not added yet"}</small>
                  <div className="button-row">
                    <button type="button" className="secondary" onClick={() => onSelectAssignment(assignment.id)}>
                      {selectedAssignmentId === assignment.id ? "Selected" : "Select class"}
                    </button>
                    <button type="button" className="link-button" onClick={() => { setEditingId(assignment.id); onSelectAssignment(assignment.id); }}>
                      Edit class
                    </button>
                    <button type="button" className="link-button danger-link" onClick={() => void removeClass(assignment)}>Remove</button>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      {(!selectedAssignment || editing !== null) && (
        <section className="setup-step-card active-step" aria-labelledby="course-step-1">
          <div className="step-heading">
            <span className="step-number">1</span>
            <div><p className="eyebrow">Step 1</p><h2 id="course-step-1">Class & Schedule</h2><p className="supporting">Enter only the class you teach and when you teach it. Curriculum comes next.</p></div>
          </div>
          <form className="form-grid" key={editing?.id ?? "new-class"} onSubmit={(event) => void saveClass(event)}>
            <label>Course name<input name="course_name" required defaultValue={editing?.course_name ?? ""} placeholder="Army JROTC LET 1" /></label>
            <label>Course code<input name="course_code" defaultValue={editing?.course_code ?? ""} placeholder="JROTC-1" /></label>
            <label>Grade(s)<input name="grade_band" defaultValue={editing?.grade_band ?? ""} placeholder="9–12" /></label>
            <label>Schedule type<select name="schedule_type" defaultValue={pattern?.schedule_type ?? "period"}><option value="period">Period</option><option value="block">Block</option><option value="custom">Custom</option></select></label>
            <label>Rotation label<input name="rotation_label" defaultValue={pattern?.rotation_label ?? ""} placeholder="Daily, A Day, B Day" /></label>
            <label>Start time<input name="start_time" type="time" defaultValue={pattern?.start_time.slice(0, 5) ?? "08:00"} required /></label>
            <label>End time<input name="end_time" type="time" defaultValue={pattern?.end_time.slice(0, 5) ?? "08:50"} required /></label>
            <label>Effective start<input name="effective_start" type="date" defaultValue={pattern?.effective_start ?? "2026-08-10"} required /></label>
            <label>Effective end<input name="effective_end" type="date" defaultValue={pattern?.effective_end ?? "2027-05-28"} required /></label>
            <fieldset className="full-width"><legend>Meeting weekdays</legend><div className="weekday-row">
              {[[1, "Mon"], [2, "Tue"], [3, "Wed"], [4, "Thu"], [5, "Fri"]].map(([value, label]) => (
                <label className="check" key={value}><input type="checkbox" name="weekday" value={value} defaultChecked={!pattern || pattern.weekdays.includes(Number(value))} />{label}</label>
              ))}
            </div></fieldset>
            <div className="form-actions full-width">
              <button className="primary" disabled={disabled || working}>{working ? "Saving…" : editing ? "Save class changes" : "Save class & continue"}</button>
              {editing && <button type="button" className="secondary" onClick={() => setEditingId(null)}>Cancel edit</button>}
            </div>
          </form>
        </section>
      )}

      {selectedAssignment && editing === null && (
        <section className="setup-step-summary complete-summary">
          <div className="step-heading"><span className="step-number">✓</span><div><p className="eyebrow">Step 1 complete</p><h2>{selectedAssignment.course_name}</h2><p>{selectedAssignment.meeting_patterns[0] ? `${weekdayLabel(selectedAssignment.meeting_patterns[0].weekdays)} · ${selectedAssignment.meeting_patterns[0].start_time.slice(0, 5)}–${selectedAssignment.meeting_patterns[0].end_time.slice(0, 5)}` : "Schedule saved"}</p></div></div>
          <button type="button" className="secondary" onClick={() => setEditingId(selectedAssignment.id)}>Edit Class & Schedule</button>
        </section>
      )}

      {selectedAssignment && !step2Complete && editing === null && (
        <section className="setup-step-card active-step" aria-labelledby="course-step-2">
          <div className="step-heading"><span className="step-number">2</span><div><p className="eyebrow">Step 2</p><h2 id="course-step-2">Curriculum & Pacing</h2><p className="supporting">Choose how this class should move through the year. Only curricula you created appear here.</p></div></div>
          {renderPacingChoices()}{renderPacingMode()}
        </section>
      )}

      {selectedAssignment && step2Complete && (
        <section className="setup-step-summary complete-summary">
          <div className="step-heading"><span className="step-number">✓</span><div><p className="eyebrow">Step 2 complete</p><h2>Curriculum & Pacing</h2><p>{currentPacing?.name} · {currentPacing?.version}</p><p className="supporting">If this curriculum is used by one active class, Edit current curriculum opens the future pacing editor directly. If multiple active classes reuse it, TPP first asks whether to update their shared future pacing or create a separate copy for this class.</p></div></div>
          <div className="button-row">
            <button type="button" className="secondary" disabled={working} onClick={() => void loadCurriculumDetail()}>Edit current curriculum</button>
            <button type="button" className="secondary" disabled={working} onClick={() => void downloadCurriculum()}>Download Excel</button>
            <button type="button" className="secondary" disabled={working} onClick={() => { setCopyVersionOpen(true); setCurriculumDetail(null); setPacingMode(null); }}>Create new version / copy</button>
            <button type="button" className="secondary" disabled={working} onClick={() => { setPacingMode((current) => current ? null : "reuse"); setCurriculumDetail(null); setCopyVersionOpen(false); }}>
              {pacingMode ? "Cancel curriculum change" : "Change / reuse curriculum"}
            </button>
          </div>
        </section>
      )}

      {selectedAssignment && step2Complete && pacingMode && !curriculumManagerOpen && (
        <section className="setup-step-card active-step">
          <div className="step-heading"><span className="step-number">2</span><div><p className="eyebrow">Change Step 2</p><h2>Use a different Curriculum & Pacing</h2><p className="supporting">Create a new sequence or attach one of your existing saved curricula. The current saved curriculum remains available unless you explicitly retire it.</p></div></div>
          {renderPacingChoices()}{renderPacingMode()}
        </section>
      )}

      {selectedAssignment && step2Complete && copyVersionOpen && currentPacing && (
        <section className="setup-step-card active-step">
          <div className="step-heading"><span className="step-number">2</span><div><p className="eyebrow">Curriculum copy</p><h2>Create a reusable new version</h2><p className="supporting">This copies the latest saved curriculum without carrying any class progress. Use it next year or attach it to another class through Reuse mine.</p></div></div>
          <form className="form-grid" onSubmit={(event) => void createNextVersion(event)}>
            <label>Curriculum name<input name="copy_name" required defaultValue={currentPacing.name} /></label>
            <label>Version<input name="copy_version" required defaultValue="2027-28" /></label>
            <div className="form-actions full-width"><button className="primary" disabled={working}>Create version / copy</button><button type="button" className="secondary" onClick={() => setCopyVersionOpen(false)}>Cancel</button></div>
          </form>
        </section>
      )}

      {selectedAssignment && step2Complete && curriculumDetail && currentPacing && !sharedEditConfirmed && (
        <section className="setup-step-card active-step">
          <div className="step-heading"><span className="step-number">2</span><div><p className="eyebrow">Shared curriculum</p><h2>Choose how this change should apply</h2><p className="supporting">This curriculum is currently used by {curriculumDetail.active_class_count} active classes. Their progress is independent, but they share the future curriculum sequence.</p></div></div>
          <div className="choice-grid">
            <button type="button" className="choice-card" onClick={() => setSharedEditConfirmed(true)}><strong>Update shared future pacing</strong><span>Apply future unscheduled changes to every class using this curriculum. Lessons already scheduled by any attached class remain locked.</span></button>
            <button type="button" className="choice-card" disabled={working} onClick={() => void createSeparateCopyForClass()}><strong>Create a separate copy for this class</strong><span>Keep other classes on the current curriculum and give {selectedAssignment.course_name} its own future pacing path.</span></button>
          </div>
          <button type="button" className="secondary" onClick={() => setCurriculumDetail(null)}>Cancel</button>
        </section>
      )}

      {selectedAssignment && step2Complete && curriculumDetail && sharedEditConfirmed && (
        <section className="setup-step-card active-step">
          <div className="step-heading"><span className="step-number">2</span><div><p className="eyebrow">Edit current year</p><h2>Curriculum & Pacing</h2><p className="supporting">The current-year curriculum is a living pacing document. Already scheduled or submitted instruction is preserved; add or change only future pacing after the preserved point.</p></div></div>
          <form className="form-grid" onSubmit={(event) => void saveCurriculumRevision(event)}>
            <label>Curriculum name<input name="name" required defaultValue={curriculumDetail.name} /></label>
            <label>Version<input name="version" required defaultValue={curriculumDetail.version} /></label>
            <PacingSequenceEditor key={curriculumDetail.id} disabled={disabled || working} initialRows={detailRows(curriculumDetail)} lockedThroughSequence={curriculumDetail.locked_through_sequence} allowExcelImport={false} />
            <div className="guidance-card full-width"><strong>Download always reflects the latest saved curriculum.</strong><p>After you save these changes, Download Excel exports the revised current sequence. Submitted weekly plans and completed packets remain unchanged.</p></div>
            <div className="form-actions full-width"><button className="primary" disabled={working}>Save current-year curriculum changes</button><button type="button" className="secondary" onClick={() => { setCurriculumDetail(null); setSharedEditConfirmed(false); }}>Cancel</button></div>
          </form>
        </section>
      )}

      {selectedAssignment && step2Complete && pacingMode === null && !curriculumManagerOpen && (!step3Complete || standardsEditing) && (
        <section className="setup-step-card active-step" aria-labelledby="course-step-3">
          <div className="step-heading"><span className="step-number">3</span><div><p className="eyebrow">{step3Complete ? "Edit Step 3" : "Step 3"}</p><h2 id="course-step-3">Authoritative Standards</h2><p className="supporting">Map this class once to the governed standards course used during weekly planning.</p></div></div>
          <StandardsCourseMappingPanel accessToken={accessToken} assignmentId={selectedAssignment.id} disabled={disabled || working} onMappingStatus={setStandardsMapped} onMappingSaved={() => { onStandardsMappingSaved(); setStandardsMapped(true); setStandardsEditing(false); onMessage("Standards mapping saved. Step 3 complete."); }} />
          {standardsEditing && step3Complete && <div className="button-row"><button type="button" className="secondary" onClick={() => setStandardsEditing(false)}>Cancel standards changes</button></div>}
        </section>
      )}

      {selectedAssignment && step2Complete && pacingMode === null && !curriculumManagerOpen && step3Complete && !standardsEditing && (
        <section className="setup-step-summary complete-summary">
          <div className="step-heading"><span className="step-number">✓</span><div><p className="eyebrow">Step 3 complete</p><h2>Authoritative Standards</h2><p>Governed standards course mapping saved.</p></div></div>
          <button type="button" className="secondary" onClick={() => setStandardsEditing(true)}>Edit standards mapping</button>
        </section>
      )}

      {selectedAssignment && step3Complete && pacingMode === null && !curriculumManagerOpen && !standardsEditing && (
        <section className="setup-ready-card" aria-labelledby="course-step-4">
          <div className="step-heading"><span className="step-number">✓</span><div><p className="eyebrow">Step 4 · Ready</p><h2 id="course-step-4">{selectedAssignment.course_name} is ready for weekly planning</h2><p className="supporting">Class schedule, Curriculum & Pacing, and authoritative standards mapping are configured.</p></div></div>
          <div className="ready-summary-grid">
            <div><strong>Class & Schedule</strong><span>{selectedAssignment.meeting_patterns[0] ? `${weekdayLabel(selectedAssignment.meeting_patterns[0].weekdays)} · ${selectedAssignment.meeting_patterns[0].start_time.slice(0, 5)}–${selectedAssignment.meeting_patterns[0].end_time.slice(0, 5)}` : "Saved"}</span></div>
            <div><strong>Curriculum & Pacing</strong><span>{currentPacing?.name} · {currentPacing?.version}</span></div>
            <div><strong>Standards</strong><span>Governed course mapping saved</span></div>
          </div>
          {onOpenWeeklyPlan && <div className="button-row"><button type="button" className="primary" onClick={() => onOpenWeeklyPlan(selectedAssignment.id)}>Go to Weekly Plan</button></div>}
        </section>
      )}
    </section>
  );
}