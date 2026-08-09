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
  submission_status: string;
  submitted_at: string | null;
  generated_document_count: number;
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

function statusClass(status: string): string {
  return status === "submitted" ? "status" : "badge";
}

export function AdminSubmissionPanel({ accessToken, roles, disabled = false }: Props) {
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [rows, setRows] = useState<WeeklySubmission[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isDistrictAdmin = roles.includes("district_admin");
  const scopeLabel = isDistrictAdmin ? "District" : "School";

  const summary = useMemo(() => ({
    submitted: rows.filter((row) => row.submission_status === "submitted").length,
    revised: rows.filter((row) => row.submission_status === "revised_after_submission").length,
    pending: rows.filter((row) => ["draft", "not_started"].includes(row.submission_status)).length,
  }), [rows]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `/api/v1/administration/submissions?week_start=${encodeURIComponent(weekStart)}`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) {
        let detail = "Weekly submission reporting could not be loaded.";
        try {
          const payload = await response.json() as { detail?: string };
          detail = payload.detail ?? detail;
        } catch {
          // Use bounded fallback message.
        }
        throw new Error(detail);
      }
      setRows(await response.json() as WeeklySubmission[]);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof Error ? caught.message : "Weekly submission reporting could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [weekStart, accessToken]);

  return (
    <section>
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">{scopeLabel} Administrator</p>
          <h2>Weekly plan submissions</h2>
          <p className="supporting">
            Verify teacher professional planning submissions by week and course. No student data is used.
          </p>
        </div>
      </div>
      <div className="toolbar">
        <label>
          Week of
          <input
            type="date"
            value={weekStart}
            disabled={disabled || loading}
            onChange={(event) => setWeekStart(event.target.value)}
          />
        </label>
        <button className="secondary" disabled={disabled || loading} onClick={() => void load()}>
          Refresh submissions
        </button>
      </div>
      {error && <p className="error-message" role="alert">{error}</p>}
      <section className="summary" aria-label="Weekly submission summary">
        <div><strong>{summary.submitted}</strong><span>submitted</span></div>
        <div><strong>{summary.revised}</strong><span>revised after submission</span></div>
        <div><strong>{summary.pending}</strong><span>not submitted</span></div>
        <div><strong>{rows.length}</strong><span>teacher-course records</span></div>
      </section>
      {rows.length === 0 && !loading ? (
        <div className="empty-state"><p>No governed teacher-course records were found for this week.</p></div>
      ) : (
        <div className="submission-table" role="region" aria-label="Weekly plan submission status" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th>School</th>
                <th>Teacher</th>
                <th>Course</th>
                <th>Status</th>
                <th>Submitted</th>
                <th>Documents</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.school_id}-${row.teacher_id}-${row.assignment_id ?? "none"}`}>
                  <td>{row.school_name}</td>
                  <td>{row.teacher_name}</td>
                  <td>{row.course_name ?? "—"}</td>
                  <td><span className={statusClass(row.submission_status)}>{labelFor(row.submission_status)}</span></td>
                  <td>{row.submitted_at ? new Date(row.submitted_at).toLocaleString() : "—"}</td>
                  <td>{row.generated_document_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
