import { useEffect, useMemo, useState } from "react";

type TeacherRow = { school_id: string; school_name: string; teacher_id: string; teacher_name: string };
type AdminUsage = {
  teachers_configured: number;
  teachers_with_assignments: number;
  assignments_configured: number;
  weekly_plans_created: number;
  weekly_plans_approved: number;
  instruction_records_validated: number;
  lessons_carried_forward: number;
  documents_requested: number;
  documents_generated: number;
  document_generation_failures: number;
};
type PeriodKind = "current_week" | "last_4_weeks" | "custom";
type Props = { accessToken: string };

function localIsoDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function mondayFor(date = new Date()): string {
  const copy = new Date(date);
  const day = copy.getDay();
  copy.setDate(copy.getDate() + (day === 0 ? -6 : 1 - day));
  return localIsoDate(copy);
}

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localIsoDate(date);
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    return typeof body.detail === "string" && body.detail.trim() ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

export function AdminSelectedTeacherUsageReport({ accessToken }: Props) {
  const currentMonday = mondayFor();
  const [teachers, setTeachers] = useState<TeacherRow[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [periodKind, setPeriodKind] = useState<PeriodKind>("current_week");
  const [customStart, setCustomStart] = useState(currentMonday);
  const [customEnd, setCustomEnd] = useState(addDays(currentMonday, 6));
  const [usage, setUsage] = useState<AdminUsage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const period = useMemo(() => {
    if (periodKind === "current_week") return { start: currentMonday, end: addDays(currentMonday, 6), label: "Current week" };
    if (periodKind === "last_4_weeks") return { start: addDays(currentMonday, -21), end: addDays(currentMonday, 6), label: "Last 4 weeks" };
    return { start: customStart, end: customEnd, label: "Custom dates" };
  }, [currentMonday, customEnd, customStart, periodKind]);

  const selectedIds = useMemo(() => [...selected].sort(), [selected]);
  const multipleSchools = useMemo(() => new Set(teachers.map((row) => row.school_id)).size > 1, [teachers]);

  useEffect(() => {
    let active = true;
    setError("");
    void fetch(`/api/v1/administration/submissions?week_start=${encodeURIComponent(currentMonday)}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(async (response) => {
      if (!response.ok) throw new Error(await readError(response, "Teacher reporting scope could not be loaded."));
      const rows = await response.json() as TeacherRow[];
      const deduped = Array.from(new Map(rows.map((row) => [row.teacher_id, row])).values())
        .sort((a, b) => a.school_name.localeCompare(b.school_name) || a.teacher_name.localeCompare(b.teacher_name));
      if (active) setTeachers(deduped);
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof Error ? caught.message : "Teacher reporting scope could not be loaded.");
    });
    return () => { active = false; };
  }, [accessToken, currentMonday]);

  useEffect(() => {
    if (!selectedIds.length || !period.start || !period.end || period.end < period.start) {
      setUsage(null);
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    const query = new URLSearchParams({ period_start: period.start, period_end: period.end });
    selectedIds.forEach((id) => query.append("teacher_id", id));
    void fetch(`/api/v1/administration/usage?${query.toString()}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(async (response) => {
      if (!response.ok) throw new Error(await readError(response, "Selected-teacher reporting could not be loaded."));
      if (active) setUsage(await response.json() as AdminUsage);
    }).catch((caught: unknown) => {
      if (active) {
        setUsage(null);
        setError(caught instanceof Error ? caught.message : "Selected-teacher reporting could not be loaded.");
      }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [accessToken, period.end, period.start, selectedIds]);

  function toggleTeacher(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <section className="admin-selected-usage" aria-label="Selected teacher administration report">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Selected-teacher report</p>
          <h3>Build the report from the teachers you choose</h3>
          <p className="supporting">No aggregate report is built until at least one teacher is selected. Every total below is recalculated from only the selected teachers.</p>
        </div>
      </div>

      <div className="admin-selected-scope-controls">
        <details className="teacher-multi-filter admin-report-teacher-filter">
          <summary>{selected.size ? `${selected.size} teacher${selected.size === 1 ? "" : "s"} selected` : "Select teachers"}</summary>
          <div className="teacher-filter-options">
            <div className="teacher-filter-actions">
              <button type="button" className="link-button" onClick={() => setSelected(new Set(teachers.map((row) => row.teacher_id)))}>Select all</button>
              <button type="button" className="link-button" onClick={() => setSelected(new Set())}>Clear</button>
            </div>
            {teachers.map((teacher) => (
              <label className="check" key={teacher.teacher_id}>
                <input type="checkbox" checked={selected.has(teacher.teacher_id)} onChange={() => toggleTeacher(teacher.teacher_id)} />
                <span>{teacher.teacher_name}{multipleSchools ? <small>{teacher.school_name}</small> : null}</span>
              </label>
            ))}
          </div>
        </details>
        <label>Reporting period<select value={periodKind} onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}><option value="current_week">Current week</option><option value="last_4_weeks">Last 4 weeks</option><option value="custom">Custom dates</option></select></label>
        {periodKind === "custom" ? <><label>Start<input type="date" value={customStart} onChange={(event) => setCustomStart(event.target.value)} /></label><label>End<input type="date" value={customEnd} onChange={(event) => setCustomEnd(event.target.value)} /></label></> : null}
      </div>

      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {!selected.size ? <div className="guidance-card admin-report-empty"><strong>Select one or more teachers to build the report.</strong></div> : null}
      {selected.size ? <div className="admin-report-scope-line"><strong>{period.label}</strong><span>{period.start} through {period.end}</span><span>{selected.size} selected teacher{selected.size === 1 ? "" : "s"}</span></div> : null}
      {loading ? <p className="working-status" role="status">Updating selected-teacher report…</p> : null}

      {usage && !loading ? <><section className="summary" aria-label="Selected teacher planning usage"><div><strong>{usage.teachers_configured}</strong><span>selected teachers</span></div><div><strong>{usage.teachers_with_assignments}</strong><span>selected teachers with courses</span></div><div><strong>{usage.assignments_configured}</strong><span>courses configured</span></div><div><strong>{usage.weekly_plans_created}</strong><span>weekly plans in period</span></div></section><div className="grid admin-activity-grid selected-admin-activity-grid"><article className="card"><h3>Weekly validation</h3><p>{usage.weekly_plans_approved} submitted plans</p><p>{usage.instruction_records_validated} instruction records validated</p><p>{usage.lessons_carried_forward} lessons carried forward</p></article><article className="card"><h3>Document generation</h3><p>{usage.documents_requested} requested</p><p>{usage.documents_generated} generated</p><p>{usage.document_generation_failures} failures</p></article></div></> : null}
    </section>
  );
}
