import { useEffect, useMemo, useState } from "react";
import "./AdminSubmissionPanel.css";

type WeeklySubmission = {
  school_id: string;
  school_name: string;
  teacher_id: string;
  teacher_name: string;
  assignment_id: string | null;
  course_name: string | null;
  week_start: string;
  revision: number | null;
  submitted_revision: number | null;
  submission_status: string;
  submitted_at: string | null;
};

type SubmittedPlan = {
  school_id: string;
  school_name: string;
  teacher_id: string;
  teacher_name: string;
  assignment_id: string;
  course_name: string;
  week_start: string;
  submitted_revision: number;
  submitted_at: string;
  source_data: Record<string, string>;
};

type Props = {
  accessToken: string;
  roles: string[];
  disabled?: boolean;
};

function mondayFor(dateValue = new Date()): string {
  const date = new Date(dateValue);
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function labelFor(status: string): string {
  return {
    submitted: "Submitted",
    revised_after_submission: "Revised after submission",
    draft: "Draft — not submitted",
    not_started: "Not started",
    no_course: "No active course",
  }[status] ?? status;
}

function fieldLabel(key: string): string {
  return key
    .split("_")
    .map((part) => part ? part[0].toUpperCase() + part.slice(1) : part)
    .join(" ");
}

export function AdminSubmissionPanel({ accessToken, roles, disabled = false }: Props) {
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [schoolFilter, setSchoolFilter] = useState("");
  const [teacherFilter, setTeacherFilter] = useState("");
  const [rows, setRows] = useState<WeeklySubmission[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<SubmittedPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  const isPlatformAdmin = roles.includes("platform_admin");
  const isDistrictAdmin = roles.includes("district_admin");
  const isSchoolAdmin = roles.includes("school_admin");
  const scopeLabel = isDistrictAdmin ? "District Administrator" : isSchoolAdmin ? "School Administrator" : isPlatformAdmin ? "Planning Administration" : "Administration";
  const canFilterSchools = isPlatformAdmin || isDistrictAdmin;

  const schools = useMemo(
    () => Array.from(new Map(rows.map((row) => [row.school_id, row.school_name])).entries()).sort((left, right) => left[1].localeCompare(right[1])),
    [rows],
  );

  const filteredRows = useMemo(() => {
    const search = teacherFilter.trim().toLowerCase();
    return rows.filter((row) => {
      if (schoolFilter && row.school_id !== schoolFilter) return false;
      if (!search) return true;
      return row.teacher_name.toLowerCase().includes(search) || (row.course_name ?? "").toLowerCase().includes(search);
    });
  }, [rows, schoolFilter, teacherFilter]);

  const summary = useMemo(() => ({
    submitted: filteredRows.filter((row) => row.submission_status === "submitted").length,
    revised: filteredRows.filter((row) => row.submission_status === "revised_after_submission").length,
    pending: filteredRows.filter((row) => ["draft", "not_started"].includes(row.submission_status)).length,
  }), [filteredRows]);

  async function responseMessage(response: Response, fallback: string): Promise<string> {
    try {
      const payload = await response.json() as { detail?: string };
      return payload.detail ?? fallback;
    } catch {
      return fallback;
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    setSelectedPlan(null);
    try {
      const response = await fetch(`/api/v1/administration/submissions?week_start=${encodeURIComponent(weekStart)}`, { headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error(await responseMessage(response, "Weekly submission reporting could not be loaded."));
      setRows(await response.json() as WeeklySubmission[]);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof Error ? caught.message : "Weekly submission reporting could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function loadSubmittedPlan(assignmentId: string) {
    setDetailLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/v1/administration/submissions/${encodeURIComponent(assignmentId)}?week_start=${encodeURIComponent(weekStart)}`, { headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error(await responseMessage(response, "Submitted weekly plan could not be loaded."));
      setSelectedPlan(await response.json() as SubmittedPlan);
    } catch (caught) {
      setSelectedPlan(null);
      setError(caught instanceof Error ? caught.message : "Submitted weekly plan could not be loaded.");
    } finally {
      setDetailLoading(false);
    }
  }

  useEffect(() => { void load(); }, [weekStart, accessToken]);

  return (
    <section>
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">{scopeLabel}</p>
          <h2>Weekly plan submissions</h2>
          <p className="supporting">Verify professional planning submissions by week and course, then inspect the exact immutable submitted revision.</p>
        </div>
      </div>
      <div className="toolbar">
        <label>Week of<input type="date" value={weekStart} disabled={disabled || loading} onChange={(event) => setWeekStart(event.target.value)} /></label>
        {canFilterSchools && <label>School<select value={schoolFilter} onChange={(event) => setSchoolFilter(event.target.value)}><option value="">All governed schools</option>{schools.map(([schoolId, schoolName]) => <option value={schoolId} key={schoolId}>{schoolName}</option>)}</select></label>}
        <label>Teacher or course<input type="search" value={teacherFilter} placeholder="Filter results" onChange={(event) => setTeacherFilter(event.target.value)} /></label>
        <button className="secondary" disabled={disabled || loading} onClick={() => void load()}>Refresh submissions</button>
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      <section className="summary" aria-label="Weekly submission summary"><div><strong>{summary.submitted}</strong><span>submitted</span></div><div><strong>{summary.revised}</strong><span>revised after submission</span></div><div><strong>{summary.pending}</strong><span>not submitted</span></div><div><strong>{filteredRows.length}</strong><span>teacher-course records</span></div></section>
      {filteredRows.length === 0 && !loading ? <div className="empty-state"><p>No governed teacher-course records match the selected week and filters.</p></div> : (
        <div className="submission-table" role="region" aria-label="Weekly plan submission status" tabIndex={0}>
          <table><thead><tr><th>School</th><th>Teacher</th><th>Course</th><th>Status</th><th>Submitted</th><th>Revision</th><th>Plan</th></tr></thead><tbody>{filteredRows.map((row) => <tr key={`${row.school_id}-${row.teacher_id}-${row.assignment_id ?? "none"}`}><td>{row.school_name}</td><td>{row.teacher_name}</td><td>{row.course_name ?? "—"}</td><td><span className={row.submission_status === "submitted" ? "status" : "badge"}>{labelFor(row.submission_status)}</span></td><td>{row.submitted_at ? new Date(row.submitted_at).toLocaleString() : "—"}</td><td>{row.submitted_revision ?? "—"}</td><td><button className="link-button" disabled={!row.assignment_id || !row.submitted_revision || disabled || detailLoading} onClick={() => row.assignment_id && void loadSubmittedPlan(row.assignment_id)}>View submitted plan</button></td></tr>)}</tbody></table>
        </div>
      )}
      {selectedPlan && <article className="card submitted-plan-detail" aria-label="Submitted weekly plan detail"><div className="card-row"><div><span className="badge">Submitted revision {selectedPlan.submitted_revision}</span><h3>{selectedPlan.teacher_name} · {selectedPlan.course_name}</h3><p>{selectedPlan.school_name} · Week of {selectedPlan.week_start}</p><small>Submitted {new Date(selectedPlan.submitted_at).toLocaleString()}</small></div><button className="link-button" onClick={() => setSelectedPlan(null)}>Close</button></div><dl className="submitted-plan-fields">{Object.entries(selectedPlan.source_data).filter(([, value]) => value.trim()).map(([key, value]) => <div key={key}><dt>{fieldLabel(key)}</dt><dd>{value}</dd></div>)}</dl></article>}
    </section>
  );
}