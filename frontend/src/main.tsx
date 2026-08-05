import { createClient, type Session } from "@supabase/supabase-js";
import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type View = "dashboard" | "curriculum" | "assignment" | "plan" | "validation";
type LessonStatus = "completed" | "modified" | "missed" | "skipped";

type Identity = {
  id: string;
  email: string;
  display_name: string;
  school_id: string;
  roles: string[];
  data_boundary: string;
};

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

type PlannedLesson = {
  scheduled_lesson_id: string;
  curriculum_lesson_id: string;
  unit_title: string;
  lesson_title: string;
  lesson_date: string;
  sequence: number;
  planned_minutes: number;
  segment_number: number;
  status: string;
};

type WeeklyDraft = {
  id: string;
  teacher_id: string;
  assignment_id: string;
  week_start: string;
  content: Record<string, string>;
  revision: number;
  updated_at: string;
};

type ValidationEntry = {
  status: LessonStatus | "";
  reason: string;
  teacherNote: string;
  carryForward: boolean;
};

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;

const emptyDraft: Record<string, string> = {
  teacher: "",
  course: "",
  grade: "",
  week_of: "",
  unit_topic: "",
  standards: "",
  literacy_standards: "",
  act_preparation: "",
  learning_targets: "",
  know: "",
  understand: "",
  do: "",
  activities: "",
  assessments: "",
  resources: "",
  monday: "",
  tuesday: "",
  wednesday: "",
  thursday: "",
  friday: "",
  reflection: "",
};

function mondayFor(dateValue = new Date()): string {
  const date = new Date(dateValue);
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [view, setView] = useState<View>("dashboard");
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [plan, setPlan] = useState<PlannedLesson[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>(emptyDraft);
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const [validations, setValidations] = useState<Record<string, ValidationEntry>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedAssignment = useMemo(
    () => assignments.find((assignment) => assignment.id === selectedAssignmentId) ?? null,
    [assignments, selectedAssignmentId],
  );
  const selectedCurriculum = useMemo(
    () => curricula.find((curriculum) => curriculum.id === selectedAssignment?.curriculum_id) ?? null,
    [curricula, selectedAssignment],
  );

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      if (!nextSession) {
        setIdentity(null);
        setAssignments([]);
        setCurricula([]);
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) return;
    void bootstrap(session);
  }, [session]);

  useEffect(() => {
    if (!selectedAssignment) return;
    setDraft((current) => ({
      ...current,
      teacher: identity?.display_name ?? current.teacher,
      course: selectedAssignment.course_name,
      grade: selectedAssignment.grade_band ?? current.grade,
      week_of: weekStart,
    }));
  }, [identity, selectedAssignment, weekStart]);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    if (!session?.access_token) throw new Error("Your authenticated session is unavailable.");
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${session.access_token}`);
    if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(path, { ...init, headers });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const payload = await response.json() as { detail?: string };
        if (payload.detail) detail = payload.detail;
      } catch {
        // Preserve the HTTP status when the response has no JSON body.
      }
      throw new Error(detail);
    }
    return await response.json() as T;
  }

  async function bootstrap(activeSession: Session) {
    setBusy(true);
    setError("");
    try {
      const authHeader = { Authorization: `Bearer ${activeSession.access_token}` };
      const [identityResponse, curriculaResponse, assignmentResponse] = await Promise.all([
        fetch("/api/v1/session", { headers: authHeader }),
        fetch("/api/v1/curricula", { headers: authHeader }),
        fetch("/api/v1/teaching-assignments", { headers: authHeader }),
      ]);
      for (const response of [identityResponse, curriculaResponse, assignmentResponse]) {
        if (!response.ok) {
          const payload = await response.json() as { detail?: string };
          throw new Error(payload.detail ?? "Pilot access could not be loaded.");
        }
      }
      const nextIdentity = await identityResponse.json() as Identity;
      const nextCurricula = await curriculaResponse.json() as Curriculum[];
      const nextAssignments = await assignmentResponse.json() as Assignment[];
      setIdentity(nextIdentity);
      setCurricula(nextCurricula);
      setAssignments(nextAssignments);
      if (!selectedAssignmentId && nextAssignments.length > 0) {
        setSelectedAssignmentId(nextAssignments[0].id);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pilot access could not be loaded.");
    } finally {
      setBusy(false);
    }
  }

  async function signIn() {
    if (!supabase) return;
    setError("");
    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
    if (signInError) setError(signInError.message);
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setView("dashboard");
  }

  async function createCurriculum(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const rows = String(form.get("lesson_rows") ?? "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line, index) => {
        const [unit, lesson, minutes, standards = "", targets = "", assessment = ""] = line
          .split("|")
          .map((value) => value.trim());
        const estimatedMinutes = Number(minutes);
        if (!unit || !lesson || !Number.isInteger(estimatedMinutes) || estimatedMinutes < 1) {
          throw new Error(`Curriculum row ${index + 1} must include unit, lesson, and minutes.`);
        }
        return {
          sequence: index + 1,
          unit_title: unit,
          lesson_title: lesson,
          estimated_minutes: estimatedMinutes,
          standards: standards ? standards.split(";").map((value) => value.trim()).filter(Boolean) : [],
          learning_targets: targets ? targets.split(";").map((value) => value.trim()).filter(Boolean) : [],
          assessment,
          can_split: true,
        };
      });
    setBusy(true);
    setError("");
    try {
      const created = await api<Curriculum>("/api/v1/curricula", {
        method: "POST",
        body: JSON.stringify({
          name: String(form.get("name") ?? ""),
          version: String(form.get("version") ?? ""),
          standards_family: String(form.get("standards_family") ?? "") || null,
          lessons: rows,
        }),
      });
      setCurricula((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)));
      setMessage(`${created.name} was imported.`);
      event.currentTarget.reset();
      setView("assignment");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Curriculum import failed.");
    } finally {
      setBusy(false);
    }
  }

  async function createAssignment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!identity) return;
    const form = new FormData(event.currentTarget);
    const weekdays = form.getAll("weekday").map((value) => Number(value));
    setBusy(true);
    setError("");
    try {
      const created = await api<Assignment>("/api/v1/teaching-assignments", {
        method: "POST",
        body: JSON.stringify({
          school_id: identity.school_id,
          course_name: String(form.get("course_name") ?? ""),
          course_code: String(form.get("course_code") ?? "") || null,
          curriculum_id: String(form.get("curriculum_id") ?? ""),
          grade_band: String(form.get("grade_band") ?? "") || null,
          meeting_patterns: [{
            schedule_type: String(form.get("schedule_type") ?? "period"),
            weekdays,
            start_time: String(form.get("start_time") ?? "08:00"),
            end_time: String(form.get("end_time") ?? "08:50"),
            effective_start: String(form.get("effective_start") ?? ""),
            effective_end: String(form.get("effective_end") ?? ""),
            rotation_label: String(form.get("rotation_label") ?? "") || null,
          }],
        }),
      });
      setAssignments((current) => [...current, created].sort((a, b) => a.course_name.localeCompare(b.course_name)));
      setSelectedAssignmentId(created.id);
      setMessage(`${created.course_name} was configured.`);
      setView("plan");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Teaching assignment setup failed.");
    } finally {
      setBusy(false);
    }
  }

  async function generatePlan() {
    if (!selectedAssignmentId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const generated = await api<PlannedLesson[]>("/api/v1/plans/generate", {
        method: "POST",
        body: JSON.stringify({ assignment_id: selectedAssignmentId, week_start: weekStart }),
      });
      setPlan(generated);
      setValidations(Object.fromEntries(generated.map((lesson) => [
        lesson.scheduled_lesson_id,
        { status: "", reason: "", teacherNote: "", carryForward: false },
      ])));
      setMessage(`Generated ${generated.length} scheduled lesson segment${generated.length === 1 ? "" : "s"}.`);
      await loadDraft(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function loadPlan() {
    if (!selectedAssignmentId) return;
    setBusy(true);
    setError("");
    try {
      const loaded = await api<PlannedLesson[]>(
        `/api/v1/plans?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${weekStart}`,
      );
      setPlan(loaded);
      setValidations(Object.fromEntries(loaded.map((lesson) => [
        lesson.scheduled_lesson_id,
        { status: "", reason: "", teacherNote: "", carryForward: false },
      ])));
      await loadDraft(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan could not be loaded.");
    } finally {
      setBusy(false);
    }
  }

  async function loadDraft(showNotFound = true) {
    if (!selectedAssignmentId) return;
    try {
      const loaded = await api<WeeklyDraft>(
        `/api/v1/weekly-drafts?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${weekStart}`,
      );
      setDraft({ ...emptyDraft, ...loaded.content });
      setDraftRevision(loaded.revision);
      setMessage(`Draft revision ${loaded.revision} reopened.`);
    } catch (caught) {
      const text = caught instanceof Error ? caught.message : "Weekly draft could not be loaded.";
      if (text.toLowerCase().includes("not found")) {
        setDraftRevision(null);
        setDraft((current) => ({
          ...emptyDraft,
          teacher: identity?.display_name ?? "",
          course: selectedAssignment?.course_name ?? "",
          grade: selectedAssignment?.grade_band ?? "",
          week_of: weekStart,
          unit_topic: current.unit_topic,
        }));
        if (showNotFound) setMessage("No saved draft exists for this week yet.");
      } else {
        throw caught;
      }
    }
  }

  async function saveDraft() {
    if (!selectedAssignmentId) return;
    setBusy(true);
    setError("");
    try {
      const saved = await api<WeeklyDraft>("/api/v1/weekly-drafts", {
        method: "PUT",
        body: JSON.stringify({
          assignment_id: selectedAssignmentId,
          week_start: weekStart,
          content: draft,
          expected_revision: draftRevision,
        }),
      });
      setDraftRevision(saved.revision);
      setDraft(saved.content);
      setMessage(`Draft revision ${saved.revision} saved.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly draft save failed.");
    } finally {
      setBusy(false);
    }
  }

  async function exportPacket() {
    setBusy(true);
    setError("");
    try {
      if (!session?.access_token) throw new Error("Your authenticated session is unavailable.");
      const response = await fetch("/api/v1/documents/anniston-hqi-packet", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(draft),
      });
      if (!response.ok) {
        const payload = await response.json() as { detail?: string };
        throw new Error(payload.detail ?? "The planning packet could not be generated.");
      }
      downloadBlob(await response.blob(), `anniston-hqi-${weekStart}.pdf`);
      setMessage("The Anniston HQI combined packet was generated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Document export failed.");
    } finally {
      setBusy(false);
    }
  }

  function updateValidation(id: string, patch: Partial<ValidationEntry>) {
    setValidations((current) => ({
      ...current,
      [id]: { ...current[id], ...patch },
    }));
  }

  async function saveValidation() {
    if (!selectedAssignmentId) return;
    const incomplete = plan.some((lesson) => !validations[lesson.scheduled_lesson_id]?.status);
    if (incomplete) {
      setError("Every scheduled lesson must have a Friday validation status.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/api/v1/friday-validations", {
        method: "PUT",
        body: JSON.stringify({
          assignment_id: selectedAssignmentId,
          week_start: weekStart,
          lessons: plan.map((lesson) => {
            const entry = validations[lesson.scheduled_lesson_id];
            return {
              scheduled_lesson_id: lesson.scheduled_lesson_id,
              curriculum_lesson_id: lesson.curriculum_lesson_id,
              lesson_date: lesson.lesson_date,
              sequence: lesson.sequence,
              status: entry.status,
              reason: entry.reason || null,
              teacher_note: entry.teacherNote || null,
              carry_forward: entry.status === "missed" ? true : entry.carryForward,
            };
          }),
        }),
      });
      setMessage(`Friday validation saved. ${addDays(weekStart, 7)} is ready to generate.`);
      setView("dashboard");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Friday validation failed.");
    } finally {
      setBusy(false);
    }
  }

  if (!supabase) {
    return (
      <main className="centered-state">
        <div className="state-card">
          <p className="eyebrow">Teacher Planning Platform</p>
          <h1>Pilot configuration required</h1>
          <p>The Supabase public URL and anon key were not supplied to the frontend build.</p>
        </div>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="login-shell">
        <section className="login-card">
          <p className="eyebrow">Anniston City Schools controlled pilot</p>
          <h1>Teacher Planning Platform</h1>
          <p>
            Build next week&apos;s plan, confirm what actually happened, and carry missed instruction
            forward without losing curriculum sequence.
          </p>
          <button className="primary large" onClick={() => void signIn()}>Continue with Google</button>
          <div className="boundary-notice">
            Teacher and curriculum data only. Do not enter student names, IDs, grades, IEP data,
            accommodations tied to named students, or other student-specific information.
          </div>
          {error && <p className="error-message">{error}</p>}
        </section>
      </main>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Anniston City Schools Pilot</p>
          <h1>Teacher Planning Platform</h1>
        </div>
        <div className="identity-block">
          <strong>{identity?.display_name ?? session.user.email}</strong>
          <span>{identity?.roles.join(" · ") ?? "Loading governed roles"}</span>
          <button className="link-button" onClick={() => void signOut()}>Sign out</button>
        </div>
      </header>

      <div className="boundary-strip">
        <strong>Teacher and curriculum data only.</strong> Do not enter student-specific information.
      </div>

      <nav className="workflow-nav" aria-label="Planning workflow">
        <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>Dashboard</button>
        <button className={view === "curriculum" ? "active" : ""} onClick={() => setView("curriculum")}>Curriculum</button>
        <button className={view === "assignment" ? "active" : ""} onClick={() => setView("assignment")}>Courses</button>
        <button className={view === "plan" ? "active" : ""} onClick={() => setView("plan")}>Weekly plan</button>
        <button className={view === "validation" ? "active" : ""} onClick={() => setView("validation")}>Friday validation</button>
      </nav>

      <main>
        {(message || error) && (
          <div className={error ? "alert error" : "alert success"} role="status">
            {error || message}
            <button aria-label="Dismiss" onClick={() => { setError(""); setMessage(""); }}>×</button>
          </div>
        )}

        {busy && <div className="progress-bar" aria-label="Working" />}

        {view === "dashboard" && (
          <>
            <section className="hero">
              <div>
                <p className="eyebrow">Week of {weekStart}</p>
                <h2>Validate this week. Prepare the next one.</h2>
                <p>
                  Your courses remain independent. Missed instruction leads the next curriculum
                  queue only after you confirm the Friday outcome.
                </p>
              </div>
              <div className="hero-actions">
                <button className="primary" disabled={!selectedAssignmentId} onClick={() => setView("plan")}>Open weekly plan</button>
                <button className="secondary" disabled={!selectedAssignmentId} onClick={() => setView("validation")}>Friday validation</button>
              </div>
            </section>

            <section>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Teaching assignments</p>
                  <h2>Your courses</h2>
                </div>
                <button className="secondary" onClick={() => setView(curricula.length ? "assignment" : "curriculum")}>Add course</button>
              </div>
              {assignments.length === 0 ? (
                <div className="empty-state">
                  <h3>No courses configured yet</h3>
                  <p>Import a curriculum, then create the teacher&apos;s first course and meeting pattern.</p>
                </div>
              ) : (
                <div className="grid">
                  {assignments.map((assignment) => {
                    const curriculum = curricula.find((item) => item.id === assignment.curriculum_id);
                    return (
                      <article className={`card ${selectedAssignmentId === assignment.id ? "selected" : ""}`} key={assignment.id}>
                        <div className="card-row">
                          <span className="badge">Revision {assignment.revision}</span>
                          <span className="status">Active</span>
                        </div>
                        <h3>{assignment.course_name}</h3>
                        <p>{assignment.meeting_patterns.map((pattern) => `${pattern.start_time.slice(0, 5)}–${pattern.end_time.slice(0, 5)}`).join(", ")}</p>
                        <small>{curriculum ? `${curriculum.name} · ${curriculum.version}` : assignment.curriculum_id}</small>
                        <button className="link-button" onClick={() => { setSelectedAssignmentId(assignment.id); setView("plan"); }}>Select course</button>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="summary" aria-label="Pilot summary">
              <div><strong>{assignments.length}</strong><span>courses configured</span></div>
              <div><strong>{curricula.length}</strong><span>curricula available</span></div>
              <div><strong>{identity?.roles.length ?? 0}</strong><span>concurrent roles</span></div>
              <div><strong>0</strong><span>student records</span></div>
            </section>
          </>
        )}

        {view === "curriculum" && (
          <section className="panel">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Teacher setup</p>
                <h2>Import a sequenced curriculum</h2>
                <p className="supporting">One lesson per line: Unit | Lesson | Minutes | Standards | Learning targets | Assessment</p>
              </div>
            </div>
            <form className="form-grid" onSubmit={(event) => void createCurriculum(event)}>
              <label>Curriculum name<input name="name" required placeholder="Army JROTC LET 1" /></label>
              <label>Version<input name="version" required placeholder="2026–27" /></label>
              <label>Standards family<input name="standards_family" placeholder="Army JROTC / Alabama" /></label>
              <label className="full-width">Lesson rows<textarea name="lesson_rows" rows={12} required defaultValue={"Introduction | Course orientation and expectations | 50 | | Explain course expectations | Exit ticket\nDrill and Ceremony | Attention, Parade Rest, At Ease, Rest | 50 | | Demonstrate stationary positions | Performance check"} /></label>
              <div className="form-actions full-width"><button className="primary" disabled={busy}>Import curriculum</button></div>
            </form>
          </section>
        )}

        {view === "assignment" && (
          <section className="panel">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Course configuration</p>
                <h2>Create a teaching assignment</h2>
                <p className="supporting">Period, block, and custom meeting patterns use their actual instructional minutes.</p>
              </div>
            </div>
            {curricula.length === 0 ? (
              <div className="empty-state"><p>Import at least one curriculum before creating a course.</p><button className="primary" onClick={() => setView("curriculum")}>Import curriculum</button></div>
            ) : (
              <form className="form-grid" onSubmit={(event) => void createAssignment(event)}>
                <label>Course name<input name="course_name" required placeholder="Army JROTC LET 1" /></label>
                <label>Course code<input name="course_code" placeholder="JROTC-1" /></label>
                <label>Grade band<input name="grade_band" placeholder="9–12" /></label>
                <label>Curriculum<select name="curriculum_id" required>{curricula.map((curriculum) => <option value={curriculum.id} key={curriculum.id}>{curriculum.name} · {curriculum.version}</option>)}</select></label>
                <label>Schedule type<select name="schedule_type"><option value="period">Period</option><option value="block">Block</option><option value="custom">Custom</option></select></label>
                <label>Rotation label<input name="rotation_label" placeholder="Daily, A Day, B Day" /></label>
                <label>Start time<input name="start_time" type="time" defaultValue="08:00" required /></label>
                <label>End time<input name="end_time" type="time" defaultValue="08:50" required /></label>
                <label>Effective start<input name="effective_start" type="date" defaultValue="2026-08-10" required /></label>
                <label>Effective end<input name="effective_end" type="date" defaultValue="2027-05-28" required /></label>
                <fieldset className="full-width"><legend>Meeting weekdays</legend><div className="weekday-row">{[[1,"Mon"],[2,"Tue"],[3,"Wed"],[4,"Thu"],[5,"Fri"]].map(([value,label]) => <label className="check" key={value}><input type="checkbox" name="weekday" value={value} defaultChecked />{label}</label>)}</div></fieldset>
                <div className="form-actions full-width"><button className="primary" disabled={busy}>Create course</button></div>
              </form>
            )}
          </section>
        )}

        {view === "plan" && (
          <section className="panel">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Next-week preparation</p>
                <h2>Weekly plan</h2>
                <p className="supporting">Generate the schedule, then complete the required instructional-planning fields.</p>
              </div>
            </div>
            <div className="toolbar">
              <label>Course<select value={selectedAssignmentId} onChange={(event) => setSelectedAssignmentId(event.target.value)}><option value="">Select a course</option>{assignments.map((assignment) => <option value={assignment.id} key={assignment.id}>{assignment.course_name}</option>)}</select></label>
              <label>Week of<input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label>
              <button className="primary" disabled={!selectedAssignmentId || busy} onClick={() => void generatePlan()}>Generate week</button>
              <button className="secondary" disabled={!selectedAssignmentId || busy} onClick={() => void loadPlan()}>Reopen week</button>
            </div>

            {plan.length > 0 && (
              <div className="plan-list">
                {plan.map((lesson) => <article key={lesson.scheduled_lesson_id}><div><strong>{lesson.lesson_date}</strong><span>{lesson.planned_minutes} minutes</span></div><div><small>{lesson.unit_title}</small><h3>{lesson.lesson_title}</h3></div><span className="badge">Segment {lesson.segment_number}</span></article>)}
              </div>
            )}

            <div className="section-heading compact draft-heading"><div><p className="eyebrow">Anniston HQI fields</p><h2>Planning narrative</h2><p className="supporting">Literacy Standards and ACT Preparation are required for every teacher.</p></div><span className="badge">Draft revision {draftRevision ?? 0}</span></div>
            <div className="form-grid">
              <label>Unit / topic<input value={draft.unit_topic} onChange={(event) => setDraft({ ...draft, unit_topic: event.target.value })} /></label>
              <label>Standards<input value={draft.standards} onChange={(event) => setDraft({ ...draft, standards: event.target.value })} /></label>
              <label className="full-width required-field">Literacy Standards<textarea rows={3} value={draft.literacy_standards} onChange={(event) => setDraft({ ...draft, literacy_standards: event.target.value })} required /></label>
              <label className="full-width required-field">ACT Preparation<textarea rows={3} value={draft.act_preparation} onChange={(event) => setDraft({ ...draft, act_preparation: event.target.value })} required /></label>
              <label className="full-width">Learning targets<textarea rows={3} value={draft.learning_targets} onChange={(event) => setDraft({ ...draft, learning_targets: event.target.value })} /></label>
              <label>Know<textarea rows={4} value={draft.know} onChange={(event) => setDraft({ ...draft, know: event.target.value })} /></label>
              <label>Understand<textarea rows={4} value={draft.understand} onChange={(event) => setDraft({ ...draft, understand: event.target.value })} /></label>
              <label className="full-width">Do<textarea rows={3} value={draft.do} onChange={(event) => setDraft({ ...draft, do: event.target.value })} /></label>
              <label className="full-width">Activities<textarea rows={4} value={draft.activities} onChange={(event) => setDraft({ ...draft, activities: event.target.value })} /></label>
              <label>Assessments<textarea rows={4} value={draft.assessments} onChange={(event) => setDraft({ ...draft, assessments: event.target.value })} /></label>
              <label>Resources<textarea rows={4} value={draft.resources} onChange={(event) => setDraft({ ...draft, resources: event.target.value })} /></label>
              {[["monday","Monday"],["tuesday","Tuesday"],["wednesday","Wednesday"],["thursday","Thursday"],["friday","Friday"]].map(([key,label]) => <label key={key}>{label}<textarea rows={3} value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></label>)}
            </div>
            <div className="action-bar"><div><strong>{selectedAssignment?.course_name ?? "Select a course"}</strong><span>{selectedCurriculum ? `${selectedCurriculum.name} · ${selectedCurriculum.version}` : "No curriculum selected"}</span></div><div className="button-group"><button className="secondary" disabled={!selectedAssignmentId || busy} onClick={() => void loadDraft()}>Reopen draft</button><button className="primary" disabled={!selectedAssignmentId || !draft.literacy_standards.trim() || !draft.act_preparation.trim() || busy} onClick={() => void saveDraft()}>Save draft</button><button className="secondary" disabled={!draftRevision || busy} onClick={() => void exportPacket()}>Export HQI packet</button></div></div>
          </section>
        )}

        {view === "validation" && (
          <section className="panel">
            <div className="section-heading compact"><div><p className="eyebrow">Friday validation</p><h2>Confirm what actually happened</h2><p className="supporting">Every scheduled lesson needs an outcome before the next week is generated.</p></div></div>
            <div className="toolbar"><label>Course<select value={selectedAssignmentId} onChange={(event) => setSelectedAssignmentId(event.target.value)}><option value="">Select a course</option>{assignments.map((assignment) => <option value={assignment.id} key={assignment.id}>{assignment.course_name}</option>)}</select></label><label>Week of<input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} /></label><button className="secondary" disabled={!selectedAssignmentId || busy} onClick={() => void loadPlan()}>Load scheduled lessons</button></div>
            {plan.length === 0 ? <div className="empty-state"><p>Load or generate the week before completing Friday validation.</p></div> : <div className="validation-list">{plan.map((lesson) => { const entry = validations[lesson.scheduled_lesson_id] ?? { status: "", reason: "", teacherNote: "", carryForward: false }; return <article className="validation-row" key={lesson.scheduled_lesson_id}><div className="day-block"><strong>{lesson.lesson_date}</strong><span>{lesson.planned_minutes} minutes</span></div><div className="lesson-block"><small>{lesson.unit_title}</small><strong>{lesson.lesson_title}</strong><label>Status<select value={entry.status} onChange={(event) => { const status = event.target.value as LessonStatus | ""; updateValidation(lesson.scheduled_lesson_id, { status, carryForward: status === "missed" }); }}><option value="">Select outcome</option><option value="completed">Completed</option><option value="modified">Modified</option><option value="missed">Missed</option><option value="skipped">Skipped / not needed</option></select></label><label>Reason or note<input value={entry.reason} required={entry.status === "missed"} placeholder={entry.status === "missed" ? "Required for a missed lesson" : "Optional"} onChange={(event) => updateValidation(lesson.scheduled_lesson_id, { reason: event.target.value })} /></label><label>Teacher reflection<input value={entry.teacherNote} placeholder="What should change next time?" onChange={(event) => updateValidation(lesson.scheduled_lesson_id, { teacherNote: event.target.value })} /></label><label className="check"><input type="checkbox" checked={entry.carryForward || entry.status === "missed"} disabled={entry.status === "completed" || entry.status === "skipped" || entry.status === "missed"} onChange={(event) => updateValidation(lesson.scheduled_lesson_id, { carryForward: event.target.checked })} />Carry this lesson forward</label></div></article>; })}</div>}
            <div className="action-bar"><div><strong>{plan.filter((lesson) => !validations[lesson.scheduled_lesson_id]?.status).length} lessons still pending</strong><span>Missed lessons automatically lead next week&apos;s queue.</span></div><button className="primary" disabled={!plan.length || plan.some((lesson) => !validations[lesson.scheduled_lesson_id]?.status) || busy} onClick={() => void saveValidation()}>Complete Friday validation</button></div>
          </section>
        )}
      </main>

      <footer>Prepared with Teacher Planning Platform · Anniston controlled pilot · Teacher and curriculum data only</footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
