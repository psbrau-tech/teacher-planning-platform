import { createClient, type Session } from "@supabase/supabase-js";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import { AdminSubmissionPanel } from "./AdminSubmissionPanel";
import { AiPlanningPanel, type PlanningFieldKey } from "./AiPlanningPanel";
import { AiReflectionPanel } from "./AiReflectionPanel";
import { parseCurriculumRows } from "./curriculumRows";
import { ScheduleExceptionPanel } from "./ScheduleExceptionPanel";
import { StandardsAdministrationPanel } from "./StandardsAdministrationPanel";
import { StandardsCourseMappingPanel } from "./StandardsCourseMappingPanel";
import { StandardsPanel, type StandardEntry } from "./StandardsPanel";
import "./styles.css";

type View = "dashboard" | "curriculum" | "assignment" | "plan" | "validation" | "administration";
type LessonStatus = "completed" | "modified" | "missed" | "skipped";
type DocumentKind = "instructional-framework" | "week-at-a-glance" | "weekly-reflection";
type DocumentAction = "view" | "download" | "print";
type SubmissionStatus = "not_submitted" | "submitted" | "revised_after_submission";

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
  is_draft: boolean;
  submission_status: SubmissionStatus;
  submitted_at: string | null;
};

type ValidationEntry = {
  status: LessonStatus | "";
  reason: string;
  teacherNote: string;
  carryForward: boolean;
};

type FridayValidationRead = {
  revision: number;
  completed_count: number;
  modified_count: number;
  missed_count: number;
  skipped_count: number;
  carry_forward_curriculum_lesson_ids: string[];
  lessons: Array<{
    scheduled_lesson_id: string;
    status: LessonStatus;
    reason: string | null;
    teacher_note: string | null;
    carry_forward: boolean;
  }>;
};

type AdminUsage = {
  school_id: string;
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
  data_boundary: string;
};

type AdminCost = {
  school_id: string;
  usage_month: string;
  request_count: number;
  successful_requests: number;
  failed_requests: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  estimated_cost_usd: string;
  accepted_outputs: number;
  discarded_outputs: number;
};

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

const emptyDraft: Record<string, string> = {
  teacher: "", course: "", grade: "", week_of: "", unit_topic: "", standards: "",
  literacy_standards: "", act_preparation: "", learning_targets: "", know: "",
  understand: "", do: "", activities: "", assessments: "", resources: "",
  monday: "", tuesday: "", wednesday: "", thursday: "", friday: "", reflection: "",
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

function submissionLabel(status: SubmissionStatus): string {
  if (status === "submitted") return "Submitted";
  if (status === "revised_after_submission") return "Revised after submission";
  return "Not submitted";
}

function reflectionComplete(value: string): boolean {
  if (!value) return false;
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return Array.from({ length: 12 }, (_item, index) => `reflect_${index + 1}`)
      .every((key) => typeof parsed[key] === "string" && (parsed[key] as string).length > 0);
  } catch {
    return false;
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

async function responseDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [adminUsage, setAdminUsage] = useState<AdminUsage | null>(null);
  const [adminCosts, setAdminCosts] = useState<AdminCost[]>([]);
  const [view, setView] = useState<View>("dashboard");
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [plan, setPlan] = useState<PlannedLesson[]>([]);
  const [draft, setDraftState] = useState<Record<string, string>>(emptyDraft);
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const [draftSubmissionStatus, setDraftSubmissionStatus] = useState<SubmissionStatus>("not_submitted");
  const [draftSubmittedAt, setDraftSubmittedAt] = useState<string | null>(null);
  const [validations, setValidations] = useState<Record<string, ValidationEntry>>({});
  const [validationFinalized, setValidationFinalized] = useState(false);
  const [validationRevision, setValidationRevision] = useState<number | null>(null);
  const [standardsMappingVersion, setStandardsMappingVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const isTeacher = identity?.roles.includes("teacher") ?? false;
  const isSchoolAdmin = identity?.roles.includes("school_admin") ?? false;
  const isDistrictAdmin = identity?.roles.includes("district_admin") ?? false;
  const isPlatformAdmin = identity?.roles.includes("platform_admin") ?? false;
  const canViewAdministration = isSchoolAdmin || isDistrictAdmin || isPlatformAdmin;

  const selectedAssignment = useMemo(
    () => assignments.find((assignment) => assignment.id === selectedAssignmentId) ?? null,
    [assignments, selectedAssignmentId],
  );
  const selectedCurriculum = useMemo(
    () => curricula.find((curriculum) => curriculum.id === selectedAssignment?.curriculum_id) ?? null,
    [curricula, selectedAssignment],
  );
  const savedForReview = Boolean(draftRevision && !draftDirty);
  const reflectionIsComplete = reflectionComplete(draft.reflection);

  function updateDraft(next: React.SetStateAction<Record<string, string>>) {
    setDraftDirty(true);
    setDraftState(next);
  }

  function clearPlanningContext(assignment: Assignment | null, nextWeek: string) {
    setPlan([]);
    setValidations({});
    setValidationFinalized(false);
    setValidationRevision(null);
    setDraftRevision(null);
    setDraftSubmissionStatus("not_submitted");
    setDraftSubmittedAt(null);
    setDraftState({
      ...emptyDraft,
      teacher: identity?.display_name ?? "",
      course: assignment?.course_name ?? "",
      grade: assignment?.grade_band ?? "",
      week_of: nextWeek,
    });
    setDraftDirty(false);
  }

  function selectPlanningAssignment(assignmentId: string) {
    const assignment = assignments.find((item) => item.id === assignmentId) ?? null;
    setSelectedAssignmentId(assignmentId);
    clearPlanningContext(assignment, weekStart);
    setError("");
    setMessage("");
  }

  function selectPlanningWeek(nextWeek: string) {
    setWeekStart(nextWeek);
    clearPlanningContext(selectedAssignment, nextWeek);
    setError("");
    setMessage("");
  }

  function openFridayCloseout(assignmentId = selectedAssignmentId) {
    const assignment = assignments.find((item) => item.id === assignmentId) ?? null;
    const currentWeek = mondayFor();
    setSelectedAssignmentId(assignmentId);
    setWeekStart(currentWeek);
    clearPlanningContext(assignment, currentWeek);
    setError("");
    setMessage("");
    setView("validation");
  }

  function openPlanningWeek(targetWeek: string, assignmentId = selectedAssignmentId) {
    const assignment = assignments.find((item) => item.id === assignmentId) ?? null;
    setSelectedAssignmentId(assignmentId);
    setWeekStart(targetWeek);
    clearPlanningContext(assignment, targetWeek);
    setError("");
    setMessage("");
    setView("plan");
  }

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      if (!nextSession) {
        setIdentity(null);
        setAssignments([]);
        setCurricula([]);
        setAdminUsage(null);
        setAdminCosts([]);
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
    setDraftState((current) => ({
      ...current,
      teacher: identity?.display_name ?? current.teacher,
      course: selectedAssignment.course_name,
      grade: selectedAssignment.grade_band ?? current.grade,
      week_of: weekStart,
    }));
  }, [identity, selectedAssignment, weekStart]);

  const resolveSelectedStandards = useCallback((selected: StandardEntry[]) => {
    const exactText = selected.map((standard) => `${standard.code} — ${standard.text}`).join("\n");
    setDraftState((current) => {
      if (current.standards === exactText) return current;
      setDraftDirty(true);
      return { ...current, standards: exactText };
    });
  }, []);

  const applyAiPlanningField = useCallback((field: PlanningFieldKey, value: string) => {
    const draftKey = field === "do_statement" ? "do" : field;
    updateDraft((current) => ({ ...current, [draftKey]: value }));
  }, []);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    if (!session?.access_token) throw new Error("Your authenticated session is unavailable.");
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${session.access_token}`);
    if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    const response = await fetch(path, { ...init, headers });
    if (!response.ok) throw new Error(await responseDetail(response, `${response.status} ${response.statusText}`));
    return await response.json() as T;
  }

  async function bootstrap(activeSession: Session) {
    setBusy(true);
    setError("");
    try {
      const headers = { Authorization: `Bearer ${activeSession.access_token}` };
      const identityResponse = await fetch("/api/v1/session", { headers });
      if (!identityResponse.ok) throw new Error(await responseDetail(identityResponse, "Pilot access could not be loaded."));
      const nextIdentity = await identityResponse.json() as Identity;
      setIdentity(nextIdentity);

      if (nextIdentity.roles.includes("teacher")) {
        const [curriculaResponse, assignmentsResponse] = await Promise.all([
          fetch("/api/v1/curricula", { headers }),
          fetch("/api/v1/teaching-assignments", { headers }),
        ]);
        for (const response of [curriculaResponse, assignmentsResponse]) {
          if (!response.ok) throw new Error(await responseDetail(response, "Teacher planning data could not be loaded."));
        }
        const nextCurricula = await curriculaResponse.json() as Curriculum[];
        const nextAssignments = await assignmentsResponse.json() as Assignment[];
        setCurricula(nextCurricula);
        setAssignments(nextAssignments);
        if (!selectedAssignmentId && nextAssignments.length > 0) setSelectedAssignmentId(nextAssignments[0].id);
      } else {
        setCurricula([]);
        setAssignments([]);
        setSelectedAssignmentId("");
      }

      if (nextIdentity.roles.some((role) => ["school_admin", "district_admin", "platform_admin"].includes(role))) {
        const usageResponse = await fetch("/api/v1/administration/usage", { headers });
        if (!usageResponse.ok) throw new Error(await responseDetail(usageResponse, "School reporting could not be loaded."));
        setAdminUsage(await usageResponse.json() as AdminUsage);
      } else setAdminUsage(null);

      if (nextIdentity.roles.includes("platform_admin")) {
        const costsResponse = await fetch("/api/v1/administration/costs", { headers });
        if (!costsResponse.ok) throw new Error(await responseDetail(costsResponse, "Cost reporting could not be loaded."));
        setAdminCosts(await costsResponse.json() as AdminCost[]);
      } else setAdminCosts([]);

      if (!nextIdentity.roles.includes("teacher")) setView("administration");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pilot access could not be loaded.");
    } finally {
      setBusy(false);
    }
  }

  async function signIn() {
    if (!supabase) return;
    setError("");
    const { error: signInError } = await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } });
    if (signInError) setError(signInError.message);
  }

  async function signOut() {
    if (!supabase) return;
    await supabase.auth.signOut();
    setView("dashboard");
  }

  async function createCurriculum(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    let rows;
    try {
      rows = parseCurriculumRows(String(form.get("lesson_rows") ?? ""));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Curriculum rows are invalid.");
      return;
    }
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
      setMessage(`${created.name} was added.`);
      formElement.reset();
      setView("assignment");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Curriculum could not be added.");
    } finally { setBusy(false); }
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
            schedule_type: String(form.get("schedule_type") ?? "period"), weekdays,
            start_time: String(form.get("start_time") ?? "08:00"), end_time: String(form.get("end_time") ?? "08:50"),
            effective_start: String(form.get("effective_start") ?? ""), effective_end: String(form.get("effective_end") ?? ""),
            rotation_label: String(form.get("rotation_label") ?? "") || null,
          }],
        }),
      });
      setAssignments((current) => [...current, created].sort((a, b) => a.course_name.localeCompare(b.course_name)));
      setSelectedAssignmentId(created.id);
      clearPlanningContext(created, weekStart);
      setMessage(`${created.course_name} was configured.`);
      setView("plan");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Class schedule setup failed.");
    } finally { setBusy(false); }
  }

  async function generatePlan() {
    if (!selectedAssignmentId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const generated = await api<PlannedLesson[]>("/api/v1/plans/generate", {
        method: "POST", body: JSON.stringify({ assignment_id: selectedAssignmentId, week_start: weekStart }),
      });
      setPlan(generated);
      setValidations(Object.fromEntries(generated.map((lesson) => [lesson.scheduled_lesson_id, { status: "", reason: "", teacherNote: "", carryForward: false }])));
      setValidationRevision(null);
      setMessage(`Built ${generated.length} scheduled lesson segment${generated.length === 1 ? "" : "s"}. Review any carry-forward changes before planning.`);
      await loadDraft(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan generation failed.");
    } finally { setBusy(false); }
  }

  async function loadExistingValidation(loadedPlan: PlannedLesson[]) {
    if (!selectedAssignmentId) return;
    try {
      const saved = await api<FridayValidationRead>(
        `/api/v1/friday-validations?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${encodeURIComponent(weekStart)}`,
      );
      const byId = new Map(saved.lessons.map((lesson) => [lesson.scheduled_lesson_id, lesson]));
      setValidations(Object.fromEntries(loadedPlan.map((lesson) => {
        const stored = byId.get(lesson.scheduled_lesson_id);
        return [lesson.scheduled_lesson_id, stored ? {
          status: stored.status,
          reason: stored.reason ?? "",
          teacherNote: stored.teacher_note ?? "",
          carryForward: stored.carry_forward,
        } : { status: "", reason: "", teacherNote: "", carryForward: false }];
      })));
      setValidationRevision(saved.revision);
      setValidationFinalized(true);
    } catch (caught) {
      const text = caught instanceof Error ? caught.message.toLowerCase() : "";
      if (!text.includes("not found")) throw caught;
      setValidationRevision(null);
      setValidationFinalized(false);
    }
  }

  async function loadPlan() {
    if (!selectedAssignmentId) return;
    setBusy(true); setError("");
    try {
      const loaded = await api<PlannedLesson[]>(`/api/v1/plans?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${weekStart}`);
      setPlan(loaded);
      setValidations(Object.fromEntries(loaded.map((lesson) => [lesson.scheduled_lesson_id, { status: "", reason: "", teacherNote: "", carryForward: false }])));
      await loadDraft(false);
      await loadExistingValidation(loaded);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan could not be loaded.");
    } finally { setBusy(false); }
  }

  async function loadDraft(showNotFound = true) {
    if (!selectedAssignmentId) return;
    try {
      const loaded = await api<WeeklyDraft>(`/api/v1/weekly-drafts?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${weekStart}`);
      setDraftState({ ...emptyDraft, ...loaded.content });
      setDraftRevision(loaded.revision);
      setDraftSubmissionStatus(loaded.submission_status);
      setDraftSubmittedAt(loaded.submitted_at);
      setDraftDirty(false);
      if (showNotFound) setMessage(`Draft revision ${loaded.revision} reopened · ${submissionLabel(loaded.submission_status)}.`);
    } catch (caught) {
      const text = caught instanceof Error ? caught.message : "Weekly draft could not be loaded.";
      if (text.toLowerCase().includes("not found")) {
        setDraftRevision(null); setDraftSubmissionStatus("not_submitted"); setDraftSubmittedAt(null);
        setDraftState({ ...emptyDraft, teacher: identity?.display_name ?? "", course: selectedAssignment?.course_name ?? "", grade: selectedAssignment?.grade_band ?? "", week_of: weekStart });
        setDraftDirty(false);
        if (showNotFound) setMessage("No saved draft exists for this week yet.");
      } else throw caught;
    }
  }

  async function saveDraft(): Promise<WeeklyDraft | null> {
    if (!selectedAssignmentId) return null;
    if (!draft.literacy_standards.trim()) {
      setError("Add or select a Literacy Standards entry before saving the weekly plan.");
      return null;
    }
    if (!draft.act_preparation.trim()) {
      setError("Complete ACT Preparation before saving the weekly plan. Enter a teacher-selected note such as N/A when no ACT focus applies this week.");
      return null;
    }
    setBusy(true); setError("");
    try {
      const saved = await api<WeeklyDraft>("/api/v1/weekly-drafts", {
        method: "PUT",
        body: JSON.stringify({ assignment_id: selectedAssignmentId, week_start: weekStart, content: draft, expected_revision: draftRevision }),
      });
      setDraftRevision(saved.revision); setDraftState(saved.content); setDraftSubmissionStatus(saved.submission_status); setDraftSubmittedAt(saved.submitted_at); setDraftDirty(false);
      setMessage(`Draft revision ${saved.revision} saved · ${submissionLabel(saved.submission_status)}.`);
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly draft save failed.");
      return null;
    } finally { setBusy(false); }
  }

  async function saveCloseoutDraft(): Promise<WeeklyDraft | null> {
    if (!selectedAssignmentId) return null;
    setBusy(true); setError("");
    try {
      const saved = await api<WeeklyDraft>("/api/v1/weekly-drafts", {
        method: "PUT",
        body: JSON.stringify({ assignment_id: selectedAssignmentId, week_start: weekStart, content: draft, expected_revision: draftRevision }),
      });
      setDraftRevision(saved.revision); setDraftState(saved.content); setDraftSubmissionStatus(saved.submission_status); setDraftSubmittedAt(saved.submitted_at); setDraftDirty(false);
      setMessage(`Friday closeout saved at revision ${saved.revision}.`);
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Friday closeout save failed.");
      return null;
    } finally { setBusy(false); }
  }

  async function submitDraft(revisionOverride?: number): Promise<WeeklyDraft | null> {
    const revision = revisionOverride ?? draftRevision;
    if (!selectedAssignmentId || !revision || (draftDirty && revisionOverride === undefined)) return null;
    setBusy(true); setError("");
    try {
      const submitted = await api<WeeklyDraft>("/api/v1/weekly-drafts/submit", {
        method: "POST",
        body: JSON.stringify({ assignment_id: selectedAssignmentId, week_start: weekStart, expected_revision: revision }),
      });
      setDraftRevision(submitted.revision); setDraftState(submitted.content); setDraftSubmissionStatus(submitted.submission_status); setDraftSubmittedAt(submitted.submitted_at); setDraftDirty(false);
      setMessage(`Weekly plan revision ${submitted.revision} submitted successfully.`);
      return submitted;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan submission failed.");
      return null;
    } finally { setBusy(false); }
  }

  async function documentBlob(document: DocumentKind | "packet"): Promise<Blob> {
    if (!session?.access_token) throw new Error("Your authenticated session is unavailable.");
    if (!draftRevision || draftDirty) throw new Error("Save the current plan before reviewing or exporting PDFs.");
    const path = document === "packet" ? "/api/v1/documents/anniston-hqi-packet" : `/api/v1/documents/anniston-hqi/${document}`;
    const response = await fetch(path, {
      method: "POST",
      headers: { Authorization: `Bearer ${session.access_token}`, "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    if (!response.ok) throw new Error(await responseDetail(response, "The planning document could not be generated."));
    return await response.blob();
  }

  async function exportDocument(document: DocumentKind | "packet", action: DocumentAction) {
    const previewWindow = action === "view" ? window.open("", "_blank") : null;
    setBusy(true); setError("");
    try {
      const blob = await documentBlob(document);
      const filename = `anniston-planning-${document}-${weekStart}.pdf`;
      if (action === "download") {
        downloadBlob(blob, filename);
      } else {
        const url = URL.createObjectURL(blob);
        if (action === "view") {
          if (!previewWindow) throw new Error("Your browser blocked the PDF preview window.");
          previewWindow.location.href = url;
          window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } else {
          const frame = window.document.createElement("iframe");
          frame.style.position = "fixed"; frame.style.width = "0"; frame.style.height = "0"; frame.style.border = "0";
          frame.src = url;
          frame.onload = () => {
            window.setTimeout(() => {
              frame.contentWindow?.focus(); frame.contentWindow?.print();
              window.setTimeout(() => { URL.revokeObjectURL(url); frame.remove(); }, 5_000);
            }, 500);
          };
          window.document.body.appendChild(frame);
        }
      }
      setMessage(`${document === "packet" ? "Combined packet" : document} ${action === "download" ? "downloaded" : action === "print" ? "opened for printing" : "opened for review"}.`);
    } catch (caught) {
      previewWindow?.close();
      setError(caught instanceof Error ? caught.message : "Document export failed.");
    } finally { setBusy(false); }
  }

  function updateValidation(id: string, patch: Partial<ValidationEntry>) {
    setValidations((current) => ({ ...current, [id]: { ...current[id], ...patch } }));
  }

  async function saveValidation(): Promise<FridayValidationRead | null> {
    if (!selectedAssignmentId) return null;
    if (plan.some((lesson) => !validations[lesson.scheduled_lesson_id]?.status)) {
      setError("Every scheduled lesson must have a Friday validation status."); return null;
    }
    if (plan.some((lesson) => {
      const entry = validations[lesson.scheduled_lesson_id];
      return entry.status === "missed" && !entry.reason.trim();
    })) {
      setError("Every missed lesson requires a reason before Friday validation is completed."); return null;
    }
    setBusy(true); setError("");
    try {
      const saved = await api<FridayValidationRead>("/api/v1/friday-validations", {
        method: "PUT",
        body: JSON.stringify({
          assignment_id: selectedAssignmentId,
          week_start: weekStart,
          expected_revision: validationRevision,
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
              carry_forward: entry.carryForward,
            };
          }),
        }),
      });
      setValidationRevision(saved.revision);
      setValidationFinalized(true);
      setMessage(`Friday validation complete. ${saved.carry_forward_curriculum_lesson_ids.length} lesson${saved.carry_forward_curriculum_lesson_ids.length === 1 ? "" : "s"} selected to carry forward. Complete the required reflection below.`);
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Friday validation failed.");
      return null;
    } finally { setBusy(false); }
  }

  async function closeWeekAndContinue() {
    if (!validationFinalized) { setError("Complete Friday validation before closing the week."); return; }
    if (!reflectionIsComplete) { setError("Complete all 12 Weekly Reflection / PLC Discussion prompts before submitting the Friday closeout."); return; }
    const saved = await saveCloseoutDraft();
    if (!saved) return;
    const submitted = await submitDraft(saved.revision);
    if (!submitted) return;
    const next = addDays(weekStart, 7);
    setWeekStart(next);
    clearPlanningContext(selectedAssignment, next);
    setView("plan");
    setMessage(`Friday closeout submitted. Review or reconcile the schedule for the week of ${next}.`);
  }

  if (!supabase) return <main className="centered-state"><div className="state-card"><p className="eyebrow">Teacher Planning Platform</p><h1>Pilot configuration required</h1><p>The Supabase public URL and anon key were not supplied to the frontend build.</p></div></main>;

  if (!session) return (
    <main className="login-shell">
      <section className="login-card">
        <p className="eyebrow">Anniston City Schools controlled pilot</p><h1>Teacher Planning Platform</h1>
        <p>Close the current week, carry forward what needs attention, and prepare next week without losing curriculum sequence.</p>
        <button className="primary large" onClick={() => void signIn()}>Continue with Google</button>
        <div className="boundary-notice">Teacher and curriculum data only. Do not enter student names, IDs, grades, IEP/504, health, discipline, identifiable student work, or other student-specific information.</div>
        {error && <p className="error-message">{error}</p>}
      </section>
    </main>
  );

  return (
    <div className="shell">
      <header className="topbar">
        <div><p className="eyebrow">Anniston City Schools Pilot</p><h1>Teacher Planning Platform</h1></div>
        <div className="identity-block"><strong>{identity?.display_name ?? session.user.email}</strong><span>{identity?.roles.join(" · ") ?? "Loading governed roles"}</span><button className="link-button" onClick={() => void signOut()}>Sign out</button></div>
      </header>

      <div className="boundary-strip"><strong>Teacher and curriculum data only.</strong> Use class- or group-level instructional observations; do not enter student-specific information.</div>

      <nav className="workflow-nav" aria-label="Planning workflow">
        <button className={view === "dashboard" ? "active" : ""} onClick={() => setView("dashboard")}>Dashboard</button>
        {isTeacher && <button className={view === "curriculum" ? "active" : ""} onClick={() => setView("curriculum")}>Curriculum</button>}
        {isTeacher && <button className={view === "assignment" ? "active" : ""} onClick={() => setView("assignment")}>Course Setup</button>}
        {isTeacher && <button className={view === "validation" ? "active" : ""} onClick={() => openFridayCloseout()}>Friday validation</button>}
        {isTeacher && <button className={view === "plan" ? "active" : ""} onClick={() => setView("plan")}>Weekly plan</button>}
        {canViewAdministration && <button className={view === "administration" ? "active" : ""} onClick={() => setView("administration")}>Administration</button>}
      </nav>

      <main>
        {(message || error) && <div className={error ? "alert error" : "alert success"} role="status">{error || message}<button aria-label="Dismiss" onClick={() => { setError(""); setMessage(""); }}>×</button></div>}
        {busy && <div className="progress-bar" aria-label="Working" />}

        {view === "dashboard" && isTeacher && (
          <>
            <section className="hero">
              <div>
                <p className="eyebrow">Weekly workflow</p>
                <h2>Close this week. Then build the next one.</h2>
                <p>Normal routine: Friday validation → required teacher reflection → reconcile carry-forward → plan → review PDFs → submit. Use Weekly plan for the first/current planning cycle, or start next week early when needed.</p>
              </div>
              <div className="hero-actions">
                <button className="primary" disabled={!selectedAssignmentId} onClick={() => openFridayCloseout()}>Complete Friday validation</button>
                <button className="secondary" disabled={!selectedAssignmentId} onClick={() => openPlanningWeek(mondayFor())}>Open weekly plan</button>
                <button className="secondary" disabled={!selectedAssignmentId} onClick={() => openPlanningWeek(addDays(mondayFor(), 7))}>Plan next week early</button>
              </div>
            </section>
            <section>
              <div className="section-heading"><div><p className="eyebrow">Course setup</p><h2>Your courses</h2></div><button className="secondary" onClick={() => setView(curricula.length ? "assignment" : "curriculum")}>Add course</button></div>
              {assignments.length === 0 ? <div className="empty-state"><h3>No courses configured yet</h3><p>Add a curriculum, then create the first class schedule.</p></div> : (
                <div className="grid">{assignments.map((assignment) => {
                  const curriculum = curricula.find((item) => item.id === assignment.curriculum_id);
                  return <article className={`card ${selectedAssignmentId === assignment.id ? "selected" : ""}`} key={assignment.id}><div className="card-row"><span className="badge">Revision {assignment.revision}</span><span className="status">Active</span></div><h3>{assignment.course_name}</h3><p>{assignment.meeting_patterns.map((pattern) => `${pattern.start_time.slice(0, 5)}–${pattern.end_time.slice(0, 5)}`).join(", ")}</p><small>{curriculum ? `${curriculum.name} · ${curriculum.version}` : assignment.curriculum_id}</small><button className="link-button" onClick={() => openFridayCloseout(assignment.id)}>Use this course</button></article>;
                })}</div>
              )}
            </section>
          </>
        )}

        {view === "dashboard" && !isTeacher && canViewAdministration && <section className="hero"><div><p className="eyebrow">Governed administration</p><h2>School and district planning operations</h2><p>Review professional teacher-planning adoption and weekly submission status.</p></div><div className="hero-actions"><button className="primary" onClick={() => setView("administration")}>Open administration</button></div></section>}

        {view === "administration" && canViewAdministration && (
          <section className="panel">
            <div className="section-heading compact"><div><p className="eyebrow">Governed reporting</p><h2>Administration</h2><p className="supporting">Professional educator planning operations only.</p></div></div>
            {adminUsage ? <><section className="summary" aria-label="School planning usage"><div><strong>{adminUsage.teachers_configured}</strong><span>teachers configured</span></div><div><strong>{adminUsage.teachers_with_assignments}</strong><span>teachers with courses</span></div><div><strong>{adminUsage.assignments_configured}</strong><span>courses configured</span></div><div><strong>{adminUsage.weekly_plans_created}</strong><span>weekly plans created</span></div></section><div className="grid"><article className="card"><h3>Weekly validation</h3><p>{adminUsage.weekly_plans_approved} submitted plans</p><p>{adminUsage.instruction_records_validated} instruction records validated</p><p>{adminUsage.lessons_carried_forward} lessons carried forward</p></article><article className="card"><h3>Document generation</h3><p>{adminUsage.documents_requested} requested</p><p>{adminUsage.documents_generated} generated</p><p>{adminUsage.document_generation_failures} failures</p></article><article className="card"><h3>Access boundary</h3><p>{identity?.roles.join(" · ")}</p><p>{adminUsage.data_boundary}</p><p>Professional educator operations only</p></article></div></> : <div className="empty-state"><p>Administration reporting is loading or unavailable.</p></div>}
            <AdminSubmissionPanel accessToken={session.access_token} roles={identity?.roles ?? []} disabled={busy} />
            {isPlatformAdmin && <><StandardsAdministrationPanel accessToken={session.access_token} disabled={busy} /><section><div className="section-heading compact"><div><p className="eyebrow">Platform Administrator</p><h2>AI cost reporting</h2><p className="supporting">Cost reporting is visible only to the Platform Administrator role.</p></div></div>{adminCosts.length === 0 ? <div className="empty-state"><p>No AI usage has been recorded.</p></div> : <div className="grid">{adminCosts.map((cost) => <article className="card" key={`${cost.school_id}-${cost.usage_month}`}><span className="badge">{cost.usage_month.slice(0, 7)}</span><h3>${cost.estimated_cost_usd}</h3><p>{cost.request_count} requests · {cost.successful_requests} successful · {cost.failed_requests} failed</p><small>{cost.input_tokens} input · {cost.output_tokens} output · {cost.cached_tokens} cached tokens</small></article>)}</div>}</section></>}
          </section>
        )}

        {view === "curriculum" && isTeacher && (
          <section className="panel">
            <div className="section-heading compact"><div><p className="eyebrow">Teacher setup</p><h2>Add a sequenced curriculum</h2><p className="supporting">One lesson per line: Unit | Lesson | Standards | Learning targets | Assessment | Optional minutes override. Leave minutes blank for normal lessons; TPP uses the course schedule.</p></div></div>
            <form className="form-grid" onSubmit={(event) => void createCurriculum(event)}>
              <label>Curriculum name<input name="name" required placeholder="Army JROTC LET 1" /></label><label>Version<input name="version" required placeholder="2026–27" /></label><label>Standards family<input name="standards_family" placeholder="Army JROTC / Alabama" /></label>
              <label className="full-width">Lesson rows<textarea name="lesson_rows" rows={12} required defaultValue={"Introduction | Course orientation and expectations | | Explain course expectations | Exit ticket\nDrill and Ceremony | Attention, Parade Rest, At Ease, Rest | | Demonstrate stationary positions | Performance check"} /></label>
              <div className="guidance-card full-width"><strong>Minutes come from the course schedule.</strong><p>Use the optional final column only when a lesson intentionally spans multiple meetings or uses a different duration.</p></div>
              <div className="form-actions full-width"><button className="primary" disabled={busy}>Add curriculum</button></div>
            </form>
          </section>
        )}

        {view === "assignment" && isTeacher && (
          <section className="panel">
            <div className="section-heading compact"><div><p className="eyebrow">Course Setup</p><h2>Create your class schedule</h2><p className="supporting">Period, block, and custom meeting patterns define normal instructional minutes.</p></div></div>
            {curricula.length === 0 ? <div className="empty-state"><p>Add at least one curriculum before creating a class schedule.</p><button className="primary" onClick={() => setView("curriculum")}>Add curriculum</button></div> : (
              <form className="form-grid" onSubmit={(event) => void createAssignment(event)}>
                <label>Course name<input name="course_name" required placeholder="Army JROTC LET 1" /></label><label>Course code<input name="course_code" placeholder="JROTC-1" /></label><label>Grade band<input name="grade_band" placeholder="9–12" /></label><label>Curriculum<select name="curriculum_id" required>{curricula.map((curriculum) => <option value={curriculum.id} key={curriculum.id}>{curriculum.name} · {curriculum.version}</option>)}</select></label>
                <label>Schedule type<select name="schedule_type"><option value="period">Period</option><option value="block">Block</option><option value="custom">Custom</option></select></label><label>Rotation label<input name="rotation_label" placeholder="Daily, A Day, B Day" /></label><label>Start time<input name="start_time" type="time" defaultValue="08:00" required /></label><label>End time<input name="end_time" type="time" defaultValue="08:50" required /></label><label>Effective start<input name="effective_start" type="date" defaultValue="2026-08-10" required /></label><label>Effective end<input name="effective_end" type="date" defaultValue="2027-05-28" required /></label>
                <fieldset className="full-width"><legend>Meeting weekdays</legend><div className="weekday-row">{[[1,"Mon"],[2,"Tue"],[3,"Wed"],[4,"Thu"],[5,"Fri"]].map(([value,label]) => <label className="check" key={value}><input type="checkbox" name="weekday" value={value} defaultChecked />{label}</label>)}</div></fieldset>
                <div className="form-actions full-width"><button className="primary" disabled={busy}>Save class schedule</button></div>
              </form>
            )}
          </section>
        )}

        {view === "validation" && isTeacher && (
          <section className="panel">
            <div className="section-heading compact"><div><p className="eyebrow">Step 1 · Close the current week</p><h2>Friday validation</h2><p className="supporting">Confirm what actually happened. You decide whether missed or modified instruction carries forward.</p></div></div>
            <div className="toolbar"><label>Course<select value={selectedAssignmentId} onChange={(event) => selectPlanningAssignment(event.target.value)}><option value="">Select a course</option>{assignments.map((assignment) => <option value={assignment.id} key={assignment.id}>{assignment.course_name}</option>)}</select></label><label>Week of<input type="date" value={weekStart} onChange={(event) => selectPlanningWeek(event.target.value)} /></label><button className="secondary" disabled={!selectedAssignmentId || busy} onClick={() => void loadPlan()}>Load this week</button></div>
            {plan.length === 0 ? <div className="empty-state"><p>Load the scheduled week before completing Friday validation.</p></div> : <div className="validation-list">{plan.map((lesson) => {
              const entry = validations[lesson.scheduled_lesson_id] ?? { status: "", reason: "", teacherNote: "", carryForward: false };
              return <article className="validation-row" key={lesson.scheduled_lesson_id}><div className="day-block"><strong>{lesson.lesson_date}</strong><span>{lesson.planned_minutes} minutes</span></div><div className="lesson-block"><small>{lesson.unit_title}</small><strong>{lesson.lesson_title}</strong><label>Status<select value={entry.status} onChange={(event) => {
                const status = event.target.value as LessonStatus | "";
                updateValidation(lesson.scheduled_lesson_id, {
                  status,
                  carryForward: status === "missed" ? true : (status === "completed" || status === "skipped") ? false : entry.carryForward,
                });
              }}><option value="">Select outcome</option><option value="completed">Completed</option><option value="modified">Modified</option><option value="missed">Missed</option><option value="skipped">Skipped / not needed</option></select></label><label>Reason or note<input value={entry.reason} required={entry.status === "missed"} placeholder={entry.status === "missed" ? "Required for a missed lesson" : "Optional"} onChange={(event) => updateValidation(lesson.scheduled_lesson_id, { reason: event.target.value })} /></label><label>Planning note<input value={entry.teacherNote} placeholder="Optional note for future planning" onChange={(event) => updateValidation(lesson.scheduled_lesson_id, { teacherNote: event.target.value })} /></label><label className="check"><input type="checkbox" checked={entry.carryForward} disabled={entry.status === "completed" || entry.status === "skipped" || !entry.status} onChange={(event) => updateValidation(lesson.scheduled_lesson_id, { carryForward: event.target.checked })} />Carry this lesson forward</label></div></article>;
            })}</div>}
            <div className="action-bar"><div><strong>{plan.filter((lesson) => !validations[lesson.scheduled_lesson_id]?.status).length} lessons still pending</strong><span>Nothing carries forward unless you select it.</span></div><button className="primary" disabled={!plan.length || plan.some((lesson) => !validations[lesson.scheduled_lesson_id]?.status) || busy} onClick={() => void saveValidation()}>{validationFinalized ? "Update Friday validation" : "Complete Friday validation"}</button></div>

            <AiReflectionPanel accessToken={session.access_token} assignmentId={selectedAssignmentId || null} weekStart={weekStart} disabled={!validationFinalized || busy} onApplyReflection={(value) => updateDraft((current) => ({ ...current, reflection: value }))} />

            {validationFinalized && <section className="review-section"><div className="section-heading compact"><div><p className="eyebrow">Step 2 · Required reflection</p><h2>Finish the weekly closeout</h2><p className="supporting">Save and submit the current week after all 12 district reflection prompts are complete. Then TPP will take you to next week for carry-forward reconciliation.</p></div></div><div className="button-row"><button className="secondary" disabled={!reflectionIsComplete || busy} onClick={() => void saveCloseoutDraft()}>Save Friday closeout</button><button className="primary" disabled={!reflectionIsComplete || busy} onClick={() => void closeWeekAndContinue()}>Submit Friday closeout & plan next week</button>{savedForReview && <><button className="secondary" onClick={() => void exportDocument("weekly-reflection", "download")}>Download reflection PDF</button><button className="secondary" onClick={() => void exportDocument("weekly-reflection", "print")}>Print reflection PDF</button></>}</div></section>}
          </section>
        )}

        {view === "plan" && isTeacher && (
          <section className="panel">
            <div className="section-heading compact"><div><p className="eyebrow">Next-week preparation</p><h2>Weekly plan</h2><p className="supporting">Build or reconcile the schedule, choose relevant authoritative standards, use the planning draft as needed, review the approved PDFs, then submit.</p></div></div>
            <div className="toolbar"><label>Course<select value={selectedAssignmentId} onChange={(event) => selectPlanningAssignment(event.target.value)}><option value="">Select a course</option>{assignments.map((assignment) => <option value={assignment.id} key={assignment.id}>{assignment.course_name}</option>)}</select></label><label>Week of<input type="date" value={weekStart} onChange={(event) => selectPlanningWeek(event.target.value)} /></label><button className="primary" disabled={!selectedAssignmentId || busy} onClick={() => void generatePlan()}>Build / reconcile week</button><button className="secondary" disabled={!selectedAssignmentId || busy} onClick={() => void loadPlan()}>Reopen saved week</button></div>
            <ScheduleExceptionPanel key={`${selectedAssignmentId}-${weekStart}`} accessToken={session.access_token} assignmentId={selectedAssignmentId} weekStart={weekStart} disabled={busy} onChanged={() => { setPlan([]); setValidations({}); setValidationRevision(null); setValidationFinalized(false); }} />
            {plan.length > 0 && <div className="plan-list">{plan.map((lesson) => <article key={lesson.scheduled_lesson_id}><div><strong>{lesson.lesson_date}</strong><span>{lesson.planned_minutes} minutes</span></div><div><small>{lesson.unit_title}</small><h3>{lesson.lesson_title}</h3></div><span className="badge">Segment {lesson.segment_number}</span></article>)}</div>}

            <StandardsCourseMappingPanel accessToken={session.access_token} assignmentId={selectedAssignmentId || null} disabled={busy} onMappingSaved={() => setStandardsMappingVersion((current) => current + 1)} />
            <StandardsPanel key={`${selectedAssignmentId}-${weekStart}-${standardsMappingVersion}`} accessToken={session.access_token} assignmentId={selectedAssignmentId || null} weekStart={weekStart} weeklyLessons={plan} onSelectionResolved={resolveSelectedStandards} />
            <AiPlanningPanel accessToken={session.access_token} assignmentId={selectedAssignmentId || null} weekStart={weekStart} currentFields={{ unit_topic: draft.unit_topic, literacy_standards: draft.literacy_standards, act_preparation: draft.act_preparation, learning_targets: draft.learning_targets, know: draft.know, understand: draft.understand, do_statement: draft.do, activities: draft.activities, assessments: draft.assessments, resources: draft.resources, monday: draft.monday, tuesday: draft.tuesday, wednesday: draft.wednesday, thursday: draft.thursday, friday: draft.friday }} onApplyField={applyAiPlanningField} />

            <details className="working-plan-review">
              <summary>Review or edit the working plan</summary>
              <p className="supporting">This is the plan that feeds the approved district PDFs. Authoritative standards remain read-only.</p>
              <div className="form-grid">
                <label>Unit / topic<input value={draft.unit_topic} onChange={(event) => updateDraft({ ...draft, unit_topic: event.target.value })} /></label>
                <label className="full-width">Selected authoritative standards<textarea rows={4} value={draft.standards} readOnly aria-readonly="true" /></label>
                <label className="full-width required-field">Literacy Standards<textarea rows={3} value={draft.literacy_standards} onChange={(event) => updateDraft({ ...draft, literacy_standards: event.target.value })} required /></label>
                <label className="full-width required-field">ACT Preparation<textarea rows={3} value={draft.act_preparation} onChange={(event) => updateDraft({ ...draft, act_preparation: event.target.value })} required /></label>
                <label className="full-width">Learning targets<textarea rows={3} value={draft.learning_targets} onChange={(event) => updateDraft({ ...draft, learning_targets: event.target.value })} /></label>
                <label>Know<textarea rows={4} value={draft.know} onChange={(event) => updateDraft({ ...draft, know: event.target.value })} /></label><label>Understand<textarea rows={4} value={draft.understand} onChange={(event) => updateDraft({ ...draft, understand: event.target.value })} /></label><label className="full-width">Do<textarea rows={3} value={draft.do} onChange={(event) => updateDraft({ ...draft, do: event.target.value })} /></label><label className="full-width">Activities<textarea rows={4} value={draft.activities} onChange={(event) => updateDraft({ ...draft, activities: event.target.value })} /></label><label>Assessments<textarea rows={4} value={draft.assessments} onChange={(event) => updateDraft({ ...draft, assessments: event.target.value })} /></label><label>Resources<textarea rows={4} value={draft.resources} onChange={(event) => updateDraft({ ...draft, resources: event.target.value })} /></label>
                {[["monday","Monday"],["tuesday","Tuesday"],["wednesday","Wednesday"],["thursday","Thursday"],["friday","Friday"]].map(([key,label]) => <label key={key}>{label}<textarea rows={3} value={draft[key]} onChange={(event) => updateDraft({ ...draft, [key]: event.target.value })} /></label>)}
              </div>
            </details>

            <section className="review-section" id="review-actions">
              <div className="section-heading compact"><div><p className="eyebrow">Review and submit</p><h2>Approved district PDFs</h2><p className="supporting">Save the working plan first. Then review, download, or print any approved PDF before submitting the weekly plan. Page counts expand automatically with teacher content.</p></div><span className="badge">Revision {draftRevision ?? 0} · {draftDirty ? "Unsaved changes" : submissionLabel(draftSubmissionStatus)}</span></div>
              {draftSubmittedAt && <p className="guidance-text">Last submitted {new Date(draftSubmittedAt).toLocaleString()}.</p>}
              <div className="button-row"><button className="primary" disabled={!selectedAssignmentId || busy} onClick={() => void saveDraft()}>Save draft</button><button className="secondary" disabled={!savedForReview || busy} onClick={() => window.document.getElementById("pdf-review")?.scrollIntoView({ behavior: "smooth" })}>Next: Review PDFs</button></div>
              <div className="pdf-review-grid" id="pdf-review">
                {([
                  ["instructional-framework", "Instructional Planning Framework"],
                  ["week-at-a-glance", "Week at a Glance"],
                  ["weekly-reflection", "Weekly Reflection / PLC Discussion"],
                  ["packet", "Combined packet"],
                ] as Array<[DocumentKind | "packet", string]>).map(([kind, title]) => <article className="card" key={kind}><h3>{title}</h3><div className="button-row"><button className="secondary" disabled={!savedForReview || busy} onClick={() => void exportDocument(kind, "view")}>View PDF</button><button className="secondary" disabled={!savedForReview || busy} onClick={() => void exportDocument(kind, "download")}>Download PDF</button><button className="secondary" disabled={!savedForReview || busy} onClick={() => void exportDocument(kind, "print")}>Print</button></div></article>)}
              </div>
              <div className="action-bar"><div><strong>{draftSubmissionStatus === "submitted" ? "Weekly plan submitted" : "Ready when you are"}</strong><span>Submission creates an immutable administrator-visible version.</span></div><button className="primary" disabled={!savedForReview || draftSubmissionStatus === "submitted" || busy} onClick={() => void submitDraft()}>{draftSubmissionStatus === "revised_after_submission" ? "Resubmit weekly plan" : "Submit weekly plan"}</button></div>
            </section>
          </section>
        )}
      </main>

      <footer>Prepared with Teacher Planning Platform · Anniston controlled pilot · Teacher and curriculum data only</footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);