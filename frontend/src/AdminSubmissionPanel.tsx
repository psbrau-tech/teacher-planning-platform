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

type Props = { accessToken: string; roles: string[]; disabled?: boolean };

function mondayFor(dateValue = new Date()): string {
  const date = new Date(dateValue); const day = date.getDay(); const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset); return date.toISOString().slice(0, 10);
}
function labelFor(status: string): string { return { submitted: "Submitted", revised_after_submission: "Revised after submission", draft: "Draft — not submitted", not_started: "Not started", no_course: "No active course" }[status] ?? status; }
function downloadBlob(blob: Blob, filename: string) { const url = URL.createObjectURL(blob); const anchor = window.document.createElement("a"); anchor.href = url; anchor.download = filename; window.document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(url); }

export function AdminSubmissionPanel({ accessToken, roles, disabled = false }: Props) {
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [schoolFilter, setSchoolFilter] = useState("");
  const [teacherFilter, setTeacherFilter] = useState("");
  const [rows, setRows] = useState<WeeklySubmission[]>([]);
  const [selectedRow, setSelectedRow] = useState<WeeklySubmission | null>(null);
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const isPlatformAdmin = roles.includes("platform_admin"); const isDistrictAdmin = roles.includes("district_admin"); const isSchoolAdmin = roles.includes("school_admin");
  const scopeLabel = isDistrictAdmin ? "District Administrator" : isSchoolAdmin ? "School Administrator" : isPlatformAdmin ? "Planning Administration" : "Administration";
  const canFilterSchools = isPlatformAdmin || isDistrictAdmin;
  const schools = useMemo(() => Array.from(new Map(rows.map((row) => [row.school_id, row.school_name])).entries()).sort((left, right) => left[1].localeCompare(right[1])), [rows]);
  const filteredRows = useMemo(() => { const search = teacherFilter.trim().toLowerCase(); return rows.filter((row) => { if (schoolFilter && row.school_id !== schoolFilter) return false; if (!search) return true; return row.teacher_name.toLowerCase().includes(search) || (row.course_name ?? "").toLowerCase().includes(search); }); }, [rows, schoolFilter, teacherFilter]);
  const summary = useMemo(() => ({ submitted: filteredRows.filter((row) => row.submission_status === "submitted").length, revised: filteredRows.filter((row) => row.submission_status === "revised_after_submission").length, pending: filteredRows.filter((row) => ["draft", "not_started"].includes(row.submission_status)).length }), [filteredRows]);

  async function responseMessage(response: Response, fallback: string): Promise<string> { try { const payload = await response.json() as { detail?: string }; return payload.detail ?? fallback; } catch { return fallback; } }
  function closePreview() { if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl); setPdfPreviewUrl(null); setSelectedRow(null); }
  async function load() { setLoading(true); setError(""); closePreview(); try { const response = await fetch(`/api/v1/administration/submissions?week_start=${encodeURIComponent(weekStart)}`, { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error(await responseMessage(response, "Weekly submission reporting could not be loaded.")); setRows(await response.json() as WeeklySubmission[]); } catch (caught) { setRows([]); setError(caught instanceof Error ? caught.message : "Weekly submission reporting could not be loaded."); } finally { setLoading(false); } }
  async function packetBlob(row: WeeklySubmission): Promise<Blob> { if (!row.assignment_id) throw new Error("Submitted plan is unavailable."); const response = await fetch(`/api/v1/administration/submissions/${encodeURIComponent(row.assignment_id)}/packet?week_start=${encodeURIComponent(row.week_start)}`, { headers: { Authorization: `Bearer ${accessToken}` } }); if (!response.ok) throw new Error(await responseMessage(response, "Submitted combined packet could not be loaded.")); return await response.blob(); }
  async function viewSubmittedPlan(row: WeeklySubmission) { setDetailLoading(true); setError(""); try { const blob = await packetBlob(row); if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl); setSelectedRow(row); setPdfPreviewUrl(URL.createObjectURL(blob)); } catch (caught) { closePreview(); setError(caught instanceof Error ? caught.message : "Submitted combined packet could not be loaded."); } finally { setDetailLoading(false); } }
  async function downloadSubmittedPlan() { if (!selectedRow) return; setDetailLoading(true); setError(""); try { const blob = await packetBlob(selectedRow); downloadBlob(blob, `submitted-planning-packet-${selectedRow.week_start}.pdf`); } catch (caught) { setError(caught instanceof Error ? caught.message : "Submitted combined packet could not be downloaded."); } finally { setDetailLoading(false); } }
  function printSubmittedPlan() { if (!pdfPreviewUrl) return; const frame = window.document.createElement("iframe"); frame.style.position = "fixed"; frame.style.width = "0"; frame.style.height = "0"; frame.style.border = "0"; frame.src = pdfPreviewUrl; frame.onload = () => window.setTimeout(() => { frame.contentWindow?.focus(); frame.contentWindow?.print(); frame.remove(); }, 500); window.document.body.appendChild(frame); }

  useEffect(() => { void load(); }, [weekStart, accessToken]);
  useEffect(() => () => { if (pdfPreviewUrl) URL.revokeObjectURL(pdfPreviewUrl); }, [pdfPreviewUrl]);

  return <section><div className="section-heading compact"><div><p className="eyebrow">{scopeLabel}</p><h2>Weekly plan submissions</h2><p className="supporting">Verify professional planning submissions by week and course, then review the exact immutable submitted revision as the Combined packet PDF.</p></div></div><div className="toolbar"><label>Week of<input type="date" value={weekStart} disabled={disabled || loading} onChange={(event) => setWeekStart(event.target.value)} /></label>{canFilterSchools && <label>School<select value={schoolFilter} onChange={(event) => setSchoolFilter(event.target.value)}><option value="">All governed schools</option>{schools.map(([schoolId, schoolName]) => <option value={schoolId} key={schoolId}>{schoolName}</option>)}</select></label>}<label>Teacher or course<input type="search" value={teacherFilter} placeholder="Filter results" onChange={(event) => setTeacherFilter(event.target.value)} /></label><button className="secondary" disabled={disabled || loading} onClick={() => void load()}>Refresh submissions</button></div>{error && <p className="error-message" role="alert">{error}</p>}<section className="summary" aria-label="Weekly submission summary"><div><strong>{summary.submitted}</strong><span>submitted</span></div><div><strong>{summary.revised}</strong><span>revised after submission</span></div><div><strong>{summary.pending}</strong><span>not submitted</span></div><div><strong>{filteredRows.length}</strong><span>teacher-course records</span></div></section>{filteredRows.length === 0 && !loading ? <div className="empty-state"><p>No governed teacher-course records match the selected week and filters.</p></div> : <div className="submission-table" role="region" aria-label="Weekly plan submission status" tabIndex={0}><table><thead><tr><th>School</th><th>Teacher</th><th>Course</th><th>Status</th><th>Submitted</th><th>Revision</th><th>Plan</th></tr></thead><tbody>{filteredRows.map((row) => <tr key={`${row.school_id}-${row.teacher_id}-${row.assignment_id ?? "none"}`}><td>{row.school_name}</td><td>{row.teacher_name}</td><td>{row.course_name ?? "—"}</td><td><span className={row.submission_status === "submitted" ? "status" : "badge"}>{labelFor(row.submission_status)}</span></td><td>{row.submitted_at ? new Date(row.submitted_at).toLocaleString() : "—"}</td><td>{row.submitted_revision ?? "—"}</td><td><button className="link-button" disabled={!row.assignment_id || !row.submitted_revision || disabled || detailLoading} onClick={() => void viewSubmittedPlan(row)}>{detailLoading ? "Preparing PDF…" : "View submitted plan"}</button></td></tr>)}</tbody></table></div>}
    {selectedRow && pdfPreviewUrl && <div className="admin-pdf-backdrop" role="dialog" aria-modal="true" aria-label="Submitted combined packet preview"><section className="admin-pdf-modal"><div className="admin-pdf-heading"><div><span className="badge">Submitted revision {selectedRow.submitted_revision}</span><h3>{selectedRow.teacher_name} · {selectedRow.course_name}</h3><p>{selectedRow.school_name} · Week of {selectedRow.week_start}</p></div><div className="button-row"><button className="secondary" disabled={detailLoading} onClick={() => void downloadSubmittedPlan()}>Download PDF</button><button className="secondary" onClick={printSubmittedPlan}>Print</button><button className="secondary" onClick={closePreview}>Close</button></div></div><iframe src={pdfPreviewUrl} title="Submitted Combined packet PDF" /></section></div>}
  </section>;
}
