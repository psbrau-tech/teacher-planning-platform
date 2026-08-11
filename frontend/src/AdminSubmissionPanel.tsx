import { useEffect, useMemo, useRef, useState } from "react";
import "./AdminSubmissionPanel.css";

type ReviewMode = "lesson_plan" | "completed_packet";
type WeeklySubmission = {
  school_id: string;
  school_name: string;
  teacher_id: string;
  teacher_name: string;
  assignment_id: string | null;
  course_name: string | null;
  week_start: string;
  revision: number | null;
  lesson_plan_revision: number | null;
  lesson_plan_submitted_at: string | null;
  completed_packet_revision: number | null;
  completed_packet_submitted_at: string | null;
};

type Props = { accessToken: string; roles: string[]; disabled?: boolean };

function mondayFor(dateValue = new Date()): string {
  const date = new Date(dateValue);
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function mondayForIso(value: string): string {
  return value ? mondayFor(new Date(`${value}T12:00:00`)) : mondayFor();
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function rowKey(row: WeeklySubmission): string {
  return `${row.assignment_id ?? "none"}:${row.week_start}`;
}

function modeLabel(mode: ReviewMode): string {
  return mode === "lesson_plan" ? "lesson plan" : "completed packet";
}

function revisionFor(row: WeeklySubmission, mode: ReviewMode): number | null {
  return mode === "lesson_plan" ? row.lesson_plan_revision : row.completed_packet_revision;
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

export function AdminSubmissionPanel({ accessToken, roles, disabled = false }: Props) {
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [schoolFilter, setSchoolFilter] = useState("");
  const [selectedTeacherIds, setSelectedTeacherIds] = useState<Set<string>>(new Set());
  const [courseFilter, setCourseFilter] = useState("");
  const [reviewMode, setReviewMode] = useState<ReviewMode>("lesson_plan");
  const [selectedPlanKeys, setSelectedPlanKeys] = useState<Set<string>>(new Set());
  const [rows, setRows] = useState<WeeklySubmission[]>([]);
  const [selectedRow, setSelectedRow] = useState<WeeklySubmission | null>(null);
  const [selectedPreviewMode, setSelectedPreviewMode] = useState<ReviewMode>("lesson_plan");
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [pdfPreviewBlob, setPdfPreviewBlob] = useState<Blob | null>(null);
  const [pdfPreviewTitle, setPdfPreviewTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const teacherFilterRef = useRef<HTMLDetailsElement>(null);

  const isPlatformAdmin = roles.includes("platform_admin");
  const isDistrictAdmin = roles.includes("district_admin");
  const isSchoolAdmin = roles.includes("school_admin");
  const scopeLabel = isDistrictAdmin
    ? "District Administrator"
    : isSchoolAdmin
      ? "School Administrator"
      : isPlatformAdmin
        ? "Planning Administration"
        : "Administration";
  const canFilterSchools = isPlatformAdmin || isDistrictAdmin;

  const schools = useMemo(
    () => Array.from(new Map(rows.map((row) => [row.school_id, row.school_name])).entries())
      .sort((left, right) => left[1].localeCompare(right[1])),
    [rows],
  );
  const teachers = useMemo(
    () => Array.from(
      new Map(
        rows
          .filter((row) => !schoolFilter || row.school_id === schoolFilter)
          .map((row) => [row.teacher_id, row.teacher_name]),
      ).entries(),
    ).sort((left, right) => left[1].localeCompare(right[1])),
    [rows, schoolFilter],
  );
  const filteredRows = useMemo(() => {
    const courseSearch = courseFilter.trim().toLowerCase();
    return rows.filter((row) => {
      if (schoolFilter && row.school_id !== schoolFilter) return false;
      if (selectedTeacherIds.size && !selectedTeacherIds.has(row.teacher_id)) return false;
      if (courseSearch && !(row.course_name ?? "").toLowerCase().includes(courseSearch)) return false;
      return true;
    });
  }, [rows, schoolFilter, selectedTeacherIds, courseFilter]);
  const selectableFilteredRows = useMemo(
    () => filteredRows.filter((row) => Boolean(row.assignment_id && revisionFor(row, reviewMode))),
    [filteredRows, reviewMode],
  );
  const selectedRows = useMemo(
    () => rows.filter((row) => (
      selectedPlanKeys.has(rowKey(row))
      && row.assignment_id
      && revisionFor(row, reviewMode)
    )),
    [rows, selectedPlanKeys, reviewMode],
  );
  const allFilteredSelected = selectableFilteredRows.length > 0
    && selectableFilteredRows.every((row) => selectedPlanKeys.has(rowKey(row)));
  const summary = useMemo(() => ({
    plans: filteredRows.filter((row) => Boolean(row.lesson_plan_revision)).length,
    completed: filteredRows.filter((row) => Boolean(row.completed_packet_revision)).length,
    pendingPlans: filteredRows.filter((row) => row.assignment_id && !row.lesson_plan_revision).length,
    pendingCloseout: filteredRows.filter(
      (row) => row.lesson_plan_revision && !row.completed_packet_revision,
    ).length,
  }), [filteredRows]);

  async function responseMessage(response: Response, fallback: string): Promise<string> {
    try {
      const payload = await response.json() as { detail?: string };
      return payload.detail ?? fallback;
    } catch {
      return fallback;
    }
  }

  function closePreview() {
    if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
    setPdfPreviewUrl(null);
    setPdfPreviewBlob(null);
    setPdfPreviewTitle("");
    setSelectedRow(null);
  }

  function setPreview(
    blob: Blob,
    title: string,
    mode: ReviewMode,
    row: WeeklySubmission | null = null,
  ) {
    if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl);
    setPdfPreviewBlob(blob);
    setPdfPreviewUrl(URL.createObjectURL(blob));
    setPdfPreviewTitle(title);
    setSelectedPreviewMode(mode);
    setSelectedRow(row);
  }

  function selectWeek(value: string) {
    setWeekStart(mondayForIso(value));
  }

  function toggleTeacher(teacherId: string) {
    setSelectedTeacherIds((current) => {
      const next = new Set(current);
      if (next.has(teacherId)) next.delete(teacherId);
      else next.add(teacherId);
      return next;
    });
  }

  function togglePlan(row: WeeklySubmission) {
    const key = rowKey(row);
    setSelectedPlanKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function toggleAllFiltered() {
    setSelectedPlanKeys((current) => {
      const next = new Set(current);
      if (allFilteredSelected) {
        selectableFilteredRows.forEach((row) => next.delete(rowKey(row)));
      } else {
        selectableFilteredRows.forEach((row) => next.add(rowKey(row)));
      }
      return next;
    });
  }

  function changeReviewMode(mode: ReviewMode) {
    setReviewMode(mode);
    setSelectedPlanKeys(new Set());
    closePreview();
  }

  async function load() {
    setLoading(true);
    setError("");
    closePreview();
    setSelectedPlanKeys(new Set());
    try {
      const response = await fetch(
        `/api/v1/administration/submissions?week_start=${encodeURIComponent(weekStart)}`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!response.ok) {
        throw new Error(await responseMessage(
          response,
          "Weekly submission reporting could not be loaded.",
        ));
      }
      setRows(await response.json() as WeeklySubmission[]);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof Error ? caught.message : "Weekly submission reporting could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function packetBlob(row: WeeklySubmission, mode: ReviewMode): Promise<Blob> {
    if (!row.assignment_id) throw new Error("Submitted plan is unavailable.");
    const suffix = mode === "lesson_plan" ? "lesson-plan-packet" : "completed-packet";
    const response = await fetch(
      `/api/v1/administration/submissions/${encodeURIComponent(row.assignment_id)}/${suffix}?week_start=${encodeURIComponent(row.week_start)}`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    if (!response.ok) {
      throw new Error(await responseMessage(
        response,
        `Submitted ${modeLabel(mode)} could not be loaded.`,
      ));
    }
    return await response.blob();
  }

  async function batchPacketBlob(): Promise<Blob> {
    if (!selectedRows.length) {
      throw new Error(`Select at least one submitted ${modeLabel(reviewMode)}.`);
    }
    const response = await fetch("/api/v1/administration/submissions/batch-packet", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        submission_kind: reviewMode,
        items: selectedRows.map((row) => ({
          assignment_id: row.assignment_id,
          week_start: row.week_start,
        })),
      }),
    });
    if (!response.ok) {
      throw new Error(await responseMessage(
        response,
        `Selected ${modeLabel(reviewMode)}s could not be prepared.`,
      ));
    }
    return await response.blob();
  }

  async function viewSubmittedPlan(row: WeeklySubmission, mode: ReviewMode) {
    setDetailLoading(true);
    setError("");
    try {
      const blob = await packetBlob(row, mode);
      const label = mode === "lesson_plan" ? "Upcoming lesson plan" : "Completed weekly packet";
      setPreview(blob, `${row.teacher_name} · ${row.course_name ?? modeLabel(mode)} · ${label}`, mode, row);
    } catch (caught) {
      closePreview();
      setError(caught instanceof Error ? caught.message : `Submitted ${modeLabel(mode)} could not be loaded.`);
    } finally {
      setDetailLoading(false);
    }
  }

  async function reviewSelectedPlans() {
    setDetailLoading(true);
    setError("");
    try {
      const blob = await batchPacketBlob();
      setPreview(
        blob,
        `${selectedRows.length} selected ${modeLabel(reviewMode)}${selectedRows.length === 1 ? "" : "s"}`,
        reviewMode,
      );
    } catch (caught) {
      closePreview();
      setError(caught instanceof Error ? caught.message : `Selected ${modeLabel(reviewMode)}s could not be prepared.`);
    } finally {
      setDetailLoading(false);
    }
  }

  async function downloadSelectedPlans() {
    setDetailLoading(true);
    setError("");
    try {
      const blob = await batchPacketBlob();
      downloadBlob(
        blob,
        `submitted-${reviewMode === "lesson_plan" ? "lesson-plans" : "completed-packets"}-${weekStart}.pdf`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Selected ${modeLabel(reviewMode)}s could not be downloaded.`);
    } finally {
      setDetailLoading(false);
    }
  }

  function downloadPreview() {
    if (!pdfPreviewBlob) return;
    const label = selectedPreviewMode === "lesson_plan" ? "lesson-plan" : "completed-packet";
    downloadBlob(
      pdfPreviewBlob,
      selectedRow
        ? `submitted-${label}-${selectedRow.week_start}.pdf`
        : `submitted-${label}-batch-${weekStart}.pdf`,
    );
  }

  function printPreview() {
    if (!pdfPreviewUrl) return;
    const frame = window.document.createElement("iframe");
    frame.style.position = "fixed";
    frame.style.width = "0";
    frame.style.height = "0";
    frame.style.border = "0";
    frame.src = pdfPreviewUrl;
    frame.onload = () => window.setTimeout(() => {
      frame.contentWindow?.focus();
      frame.contentWindow?.print();
      frame.remove();
    }, 500);
    window.document.body.appendChild(frame);
  }

  useEffect(() => { void load(); }, [weekStart, accessToken]);
  useEffect(() => {
    setSelectedTeacherIds((current) => new Set(
      [...current].filter((id) => teachers.some(([teacherId]) => teacherId === id)),
    ));
  }, [teachers]);
  useEffect(() => {
    function closeTeacherFilterOnOutsidePointer(event: PointerEvent) {
      const filter = teacherFilterRef.current;
      if (!filter?.open) return;
      if (event.target instanceof Node && !filter.contains(event.target)) filter.open = false;
    }
    window.document.addEventListener("pointerdown", closeTeacherFilterOnOutsidePointer);
    return () => window.document.removeEventListener("pointerdown", closeTeacherFilterOnOutsidePointer);
  }, []);
  useEffect(() => () => { if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl); }, [pdfPreviewUrl]);

  return (
    <section>
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">{scopeLabel}</p>
          <h2>Weekly submissions</h2>
          <p className="supporting">Each Monday-starting week has two administrative records: the lesson plan submitted before instruction and the completed packet after Friday reflection.</p>
        </div>
      </div>

      <div className="toolbar admin-submission-filters">
        <div className="week-selector admin-week-selector">
          <button type="button" className="secondary" disabled={disabled || loading} onClick={() => selectWeek(addDays(weekStart, -7))}>← Previous week</button>
          <label>Week of (Monday)<input type="date" value={weekStart} disabled={disabled || loading} onChange={(event) => selectWeek(event.target.value)} /></label>
          <button type="button" className="secondary" disabled={disabled || loading} onClick={() => selectWeek(addDays(weekStart, 7))}>Next week →</button>
        </div>
        {canFilterSchools && <label>School<select value={schoolFilter} onChange={(event) => { setSchoolFilter(event.target.value); setSelectedTeacherIds(new Set()); }}><option value="">All governed schools</option>{schools.map(([schoolId, schoolName]) => <option value={schoolId} key={schoolId}>{schoolName}</option>)}</select></label>}
        <details ref={teacherFilterRef} className="teacher-multi-filter"><summary>{selectedTeacherIds.size ? `${selectedTeacherIds.size} teacher${selectedTeacherIds.size === 1 ? "" : "s"} selected` : "All teachers"}</summary><div className="teacher-filter-options"><div className="teacher-filter-actions"><button type="button" className="link-button" onClick={() => setSelectedTeacherIds(new Set(teachers.map(([id]) => id)))}>Select all</button><button type="button" className="link-button" onClick={() => setSelectedTeacherIds(new Set())}>Clear</button></div>{teachers.map(([teacherId, teacherName]) => <label className="check" key={teacherId}><input type="checkbox" checked={selectedTeacherIds.has(teacherId)} onChange={() => toggleTeacher(teacherId)} />{teacherName}</label>)}</div></details>
        <label>Course search<input type="search" value={courseFilter} placeholder="Filter courses" onChange={(event) => setCourseFilter(event.target.value)} /></label>
        <button className="secondary" disabled={disabled || loading} onClick={() => void load()}>Refresh submissions</button>
      </div>

      {error && <p className="error-message" role="alert">{error}</p>}
      <section className="summary" aria-label="Weekly submission summary"><div><strong>{summary.plans}</strong><span>lesson plans submitted</span></div><div><strong>{summary.completed}</strong><span>completed packets</span></div><div><strong>{summary.pendingPlans}</strong><span>lesson plans pending</span></div><div><strong>{summary.pendingCloseout}</strong><span>Friday closeouts pending</span></div></section>
      <div className="submission-mode-bar"><strong>Bulk review:</strong><div className="button-row"><button className={reviewMode === "lesson_plan" ? "primary" : "secondary"} onClick={() => changeReviewMode("lesson_plan")}>Upcoming lesson plans</button><button className={reviewMode === "completed_packet" ? "primary" : "secondary"} onClick={() => changeReviewMode("completed_packet")}>Completed weekly packets</button></div><span>Select individual rows below or select all filtered records for this review type.</span></div>
      {selectedRows.length > 0 && <div className="bulk-review-bar" role="region" aria-label="Selected submissions"><strong>{selectedRows.length} {modeLabel(reviewMode)}{selectedRows.length === 1 ? "" : "s"} selected</strong><div className="button-row"><button className="secondary" disabled={disabled || detailLoading} onClick={() => void reviewSelectedPlans()}>{detailLoading ? "Preparing selected PDFs…" : "Review selected PDFs"}</button><button className="secondary" disabled={disabled || detailLoading} onClick={() => void downloadSelectedPlans()}>Download selected PDF</button><button className="link-button" onClick={() => setSelectedPlanKeys(new Set())}>Clear selection</button></div></div>}

      {filteredRows.length === 0 && !loading ? (
        <div className="empty-state"><p>No governed teacher-course records match the selected week and filters.</p></div>
      ) : (
        <div className="submission-table" role="region" aria-label="Weekly submission status" tabIndex={0}>
          <table>
            <thead><tr><th className="selection-column"><label className="sr-only" htmlFor="select-all-submitted">Select all filtered {modeLabel(reviewMode)}s</label><input id="select-all-submitted" type="checkbox" checked={allFilteredSelected} disabled={!selectableFilteredRows.length} onChange={toggleAllFiltered} /></th><th>School</th><th>Teacher</th><th>Course</th><th>Upcoming lesson plan</th><th>Completed weekly packet</th></tr></thead>
            <tbody>{filteredRows.map((row) => {
              const selectable = Boolean(row.assignment_id && revisionFor(row, reviewMode));
              return <tr key={`${row.school_id}-${row.teacher_id}-${row.assignment_id ?? "none"}`}><td className="selection-column"><input type="checkbox" aria-label={`Select ${row.teacher_name} ${row.course_name ?? "submission"} for ${modeLabel(reviewMode)} review`} checked={selectedPlanKeys.has(rowKey(row))} disabled={!selectable} onChange={() => togglePlan(row)} /></td><td>{row.school_name}</td><td>{row.teacher_name}</td><td>{row.course_name ?? "—"}</td><td>{row.lesson_plan_revision ? <div className="submission-artifact"><span className="status">Submitted · Rev {row.lesson_plan_revision}</span><small>{row.lesson_plan_submitted_at ? new Date(row.lesson_plan_submitted_at).toLocaleString() : ""}</small><button className="link-button" disabled={disabled || detailLoading} onClick={() => void viewSubmittedPlan(row, "lesson_plan")}>View lesson plan</button></div> : <span className="badge">Not submitted</span>}</td><td>{row.completed_packet_revision ? <div className="submission-artifact"><span className="status">Completed · Rev {row.completed_packet_revision}</span><small>{row.completed_packet_submitted_at ? new Date(row.completed_packet_submitted_at).toLocaleString() : ""}</small><button className="link-button" disabled={disabled || detailLoading} onClick={() => void viewSubmittedPlan(row, "completed_packet")}>View completed packet</button></div> : <span className="badge">Awaiting Friday closeout</span>}</td></tr>;
            })}</tbody>
          </table>
        </div>
      )}

      {pdfPreviewUrl && <div className="submission-preview-backdrop" role="dialog" aria-modal="true" aria-label={`${pdfPreviewTitle} preview`}><section className="submission-preview"><div className="submission-preview-heading"><div><p className="eyebrow">Immutable submitted record</p><h2>{pdfPreviewTitle}</h2></div><div className="button-row"><button className="secondary" onClick={downloadPreview}>Download PDF</button><button className="secondary" onClick={printPreview}>Print</button><button className="secondary" onClick={closePreview}>Close</button></div></div><iframe src={pdfPreviewUrl} title={`${pdfPreviewTitle} PDF`} /></section></div>}
    </section>
  );
}
