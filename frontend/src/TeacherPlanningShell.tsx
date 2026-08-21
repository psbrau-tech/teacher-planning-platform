import { createClient, type Session } from "@supabase/supabase-js";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AdministrationOverview } from "./AdministrationOverview";
import { AiPlanningPanel, type PlanningFieldKey } from "./AiPlanningPanel";
import { AiReflectionPanel } from "./AiReflectionPanel";
import { CourseSetupPanel } from "./CourseSetupPanel";
import { HelpPage } from "./HelpPage";
import { PlanningPdfFieldsPanel } from "./PlanningPdfFieldsPanel";
import { ScheduleExceptionPanel, type ScheduleException } from "./ScheduleExceptionPanel";
import { StandardsPanel, type StandardEntry } from "./StandardsPanel";
import "./styles.css";

type View = "dashboard" | "assignment" | "plan" | "validation" | "administration" | "help";
type LessonStatus = "completed" | "modified" | "missed" | "skipped";
type DocumentKind =
  | "instructional-framework"
  | "week-at-a-glance"
  | "weekly-reflection"
  | "lesson-plan"
  | "completed-packet";
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
  curriculum_id: string | null;
  grade_band: string | null;
  meeting_patterns: MeetingPattern[];
  revision: number;
  updated_at: string;
};
type PlannedLesson = {
  scheduled_lesson_id: string;
  curriculum_lesson_id: string | null;
  unit_title: string;
  lesson_title: string;
  lesson_date: string;
  sequence: number;
  planned_minutes: number;
  segment_number: number;
  status: string;
  source_type: "curriculum" | "manual";
  manual_learning_targets: string[];
  manual_assessment: string | null;
  replaced_curriculum_lesson_id: string | null;
  replacement_disposition: "skip" | "postpone" | null;
};
type LessonReplacementDraft = {
  scheduledLessonId: string;
  mode: "next" | "manual";
  unitTitle: string;
  lessonTitle: string;
  learningTargets: string;
  assessment: string;
  originalDisposition: "skip" | "postpone";
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

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const supabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
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

function mondayForIso(isoDate: string): string {
  if (!isoDate) return mondayFor();
  return mondayFor(new Date(`${isoDate}T12:00:00`));
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function dashboardScheduleLabel(pattern: MeetingPattern): string {
  const parseMinutes = (value: string): number | null => {
    const match = /^(\d{2}):(\d{2})/.exec(value);
    if (!match) return null;
    const hours = Number(match[1]);
    const minutes = Number(match[2]);
    if (hours > 23 || minutes > 59) return null;
    return (hours * 60) + minutes;
  };
  const start = parseMinutes(pattern.start_time);
  const end = parseMinutes(pattern.end_time);
  const duration = start !== null && end !== null && end > start ? end - start : null;
  const durationLabel = duration === null
    ? ""
    : ` · ${duration} minute${duration === 1 ? "" : "s"}`;
  return `${pattern.start_time.slice(0, 5)}–${pattern.end_time.slice(0, 5)}${durationLabel}`;
}

function submissionLabel(status: SubmissionStatus): string {
  return status === "submitted"
    ? "Submitted"
    : status === "revised_after_submission"
      ? "Revised after submission"
      : "Not submitted";
}

function reflectionComplete(value: string): boolean {
  if (!value) return false;
  try {
    const parsed = JSON.parse(value) as Record<string, unknown>;
    return Array.from({ length: 12 }, (_item, index) => `reflect_${index + 1}`).every(
      (key) => typeof parsed[key] === "string" && (parsed[key] as string).trim().length > 0,
    );
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

function sortPlan(plan: PlannedLesson[]): PlannedLesson[] {
  return [...plan].sort(
    (a, b) => a.lesson_date.localeCompare(b.lesson_date)
      || a.sequence - b.sequence
      || a.segment_number - b.segment_number,
  );
}

function documentTitle(document: DocumentKind): string {
  return document === "instructional-framework"
    ? "Instructional Planning Framework"
    : document === "week-at-a-glance"
      ? "Week at a Glance"
      : document === "weekly-reflection"
        ? "Weekly Reflection / PLC Discussion"
        : document === "completed-packet"
          ? "Completed Weekly Packet"
          : "Weekly Lesson Plan";
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

function WeekSelector({
  value,
  disabled,
  onChange,
}: {
  value: string;
  disabled?: boolean;
  onChange: (week: string) => void;
}) {
  return (
    <div className="week-selector">
      <button
        type="button"
        className="secondary"
        disabled={disabled}
        onClick={() => onChange(addDays(value, -7))}
      >
        ← Previous week
      </button>
      <label>
        Week of (Monday)
        <input
          type="date"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(mondayForIso(event.target.value))}
        />
      </label>
      <button
        type="button"
        className="secondary"
        disabled={disabled}
        onClick={() => onChange(addDays(value, 7))}
      >
        Next week →
      </button>
    </div>
  );
}

export function TeacherPlanningShell() {
  const initialView: View = window.location.pathname.replace(/\/+$/, "") === "/help"
    ? "help"
    : "dashboard";
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [curricula, setCurricula] = useState<Curriculum[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [view, setView] = useState<View>(initialView);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [plan, setPlan] = useState<PlannedLesson[]>([]);
  const [weekCurriculumConfirmed, setWeekCurriculumConfirmed] = useState(false);
  const [carryForwardLessonIds, setCarryForwardLessonIds] = useState<string[]>([]);
  const [scheduleExceptions, setScheduleExceptions] = useState<ScheduleException[]>([]);
  const [savedStandardsCount, setSavedStandardsCount] = useState(0);
  const [weekStandardsEditing, setWeekStandardsEditing] = useState(false);
  const [planningAssistComplete, setPlanningAssistComplete] = useState(false);
  const [planningAssistEditing, setPlanningAssistEditing] = useState(false);
  const [planReviewOpen, setPlanReviewOpen] = useState(true);
  const [pdfReviewed, setPdfReviewed] = useState(false);
  const [completedPacketSubmitted, setCompletedPacketSubmitted] = useState(false);
  const [completedPacketReviewed, setCompletedPacketReviewed] = useState(false);
  const [draft, setDraftState] = useState<Record<string, string>>(emptyDraft);
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const [draftSubmissionStatus, setDraftSubmissionStatus] = useState<SubmissionStatus>("not_submitted");
  const [draftSubmittedAt, setDraftSubmittedAt] = useState<string | null>(null);
  const [validations, setValidations] = useState<Record<string, ValidationEntry>>({});
  const [validationFinalized, setValidationFinalized] = useState(false);
  const [validationRevision, setValidationRevision] = useState<number | null>(null);
  const [standardsMappingVersion, setStandardsMappingVersion] = useState(0);
  const [documentWorking, setDocumentWorking] = useState<DocumentKind | null>(null);
  const [pdfPreview, setPdfPreview] = useState<{ url: string; title: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [lessonReplacement, setLessonReplacement] = useState<LessonReplacementDraft | null>(null);

  const isTeacher = identity?.roles.includes("teacher") ?? false;
  const isSchoolAdmin = identity?.roles.includes("school_admin") ?? false;
  const isDistrictAdmin = identity?.roles.includes("district_admin") ?? false;
  const isPlatformAdmin = identity?.roles.includes("platform_admin") ?? false;
  const canViewAdministration = isSchoolAdmin || isDistrictAdmin || isPlatformAdmin;
  const selectedAssignment = useMemo(
    () => assignments.find((assignment) => assignment.id === selectedAssignmentId) ?? null,
    [assignments, selectedAssignmentId],
  );
  const dashboardAssignments = useMemo(
    () => [...assignments].sort((a, b) => {
      const aTime = a.meeting_patterns[0]?.start_time ?? "";
      const bTime = b.meeting_patterns[0]?.start_time ?? "";
      if (!aTime && bTime) return 1;
      if (aTime && !bTime) return -1;
      return aTime.localeCompare(bTime) || a.course_name.localeCompare(b.course_name);
    }),
    [assignments],
  );
  const selectedAssignmentReady = Boolean(selectedAssignment?.curriculum_id);
  const savedForReview = Boolean(draftRevision && !draftDirty);
  const reflectionIsComplete = reflectionComplete(draft.reflection);

  function updateDraft(next: React.SetStateAction<Record<string, string>>) {
    setDraftDirty(true);
    setPdfReviewed(false);
    setPlanReviewOpen(true);
    setDraftState(next);
  }

  function clearPlanningContext(assignment: Assignment | null, nextWeek: string) {
    setPlan([]);
    setWeekCurriculumConfirmed(false);
    setCarryForwardLessonIds([]);
    setScheduleExceptions([]);
    setSavedStandardsCount(0);
    setWeekStandardsEditing(false);
    setPlanningAssistComplete(false);
    setPlanningAssistEditing(false);
    setPlanReviewOpen(true);
    setPdfReviewed(false);
    setCompletedPacketSubmitted(false);
    setCompletedPacketReviewed(false);
    setValidations({});
    setValidationFinalized(false);
    setValidationRevision(null);
    setLessonReplacement(null);
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
    const monday = mondayForIso(nextWeek);
    setWeekStart(monday);
    clearPlanningContext(selectedAssignment, monday);
    setError("");
    setMessage(nextWeek !== monday ? `Planning weeks always begin Monday. Week set to ${monday}.` : "");
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
    const monday = mondayForIso(targetWeek);
    setSelectedAssignmentId(assignmentId);
    setWeekStart(monday);
    clearPlanningContext(assignment, monday);
    setError("");
    setMessage("");
    setView("plan");
  }

  function closePdfPreview() {
    if (pdfPreview) URL.revokeObjectURL(pdfPreview.url);
    setPdfPreview(null);
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
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (session) void bootstrap(session);
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

  useEffect(() => () => {
    if (pdfPreview) URL.revokeObjectURL(pdfPreview.url);
  }, [pdfPreview]);

  useEffect(() => {
    if (
      view !== "validation"
      || !session?.access_token
      || !selectedAssignmentId
    ) return;
    let cancelled = false;
    void (async () => {
      const response = await fetch(
        `/api/v1/teacher-submissions/${encodeURIComponent(selectedAssignmentId)}/completed-packet?week_start=${encodeURIComponent(weekStart)}`,
        { headers: { Authorization: `Bearer ${session.access_token}` } },
      );
      if (cancelled) return;
      if (response.ok) {
        setCompletedPacketSubmitted(true);
        setCompletedPacketReviewed(false);
        setValidationFinalized(true);
        setMessage(
          "This Friday closeout was already submitted. Review the completed weekly packet to continue.",
        );
        return;
      }
      if (response.status === 404) {
        setCompletedPacketSubmitted(false);
        return;
      }
      setError(await responseDetail(response, "Friday closeout status could not be restored."));
    })();
    return () => {
      cancelled = true;
    };
  }, [session?.access_token, selectedAssignmentId, view, weekStart]);

  const resolveSelectedStandards = useCallback((selected: StandardEntry[]) => {
    const exactText = selected
      .map((standard) => `${standard.code} — ${standard.text}`)
      .join("\n");
    setDraftState((current) => {
      if (current.standards === exactText) return current;
      setDraftDirty(true);
      setPdfReviewed(false);
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
    if (!response.ok) {
      throw new Error(await responseDetail(response, `${response.status} ${response.statusText}`));
    }
    return await response.json() as T;
  }

  async function bootstrap(activeSession: Session) {
    setBusy(true);
    setError("");
    try {
      const headers = { Authorization: `Bearer ${activeSession.access_token}` };
      const identityResponse = await fetch("/api/v1/session", { headers });
      if (!identityResponse.ok) {
        throw new Error(await responseDetail(identityResponse, "Pilot access could not be loaded."));
      }
      const nextIdentity = await identityResponse.json() as Identity;
      setIdentity(nextIdentity);
      if (nextIdentity.roles.includes("teacher")) {
        const [curriculaResponse, assignmentsResponse] = await Promise.all([
          fetch("/api/v1/curricula", { headers }),
          fetch("/api/v1/teaching-assignments", { headers }),
        ]);
        for (const response of [curriculaResponse, assignmentsResponse]) {
          if (!response.ok) {
            throw new Error(await responseDetail(response, "Teacher planning data could not be loaded."));
          }
        }
        const nextCurricula = await curriculaResponse.json() as Curriculum[];
        const nextAssignments = await assignmentsResponse.json() as Assignment[];
        setCurricula(nextCurricula);
        setAssignments(nextAssignments);
        if (!selectedAssignmentId && nextAssignments.length > 0) {
          setSelectedAssignmentId(nextAssignments[0].id);
        }
      } else {
        setCurricula([]);
        setAssignments([]);
        setSelectedAssignmentId("");
      }
      if (!nextIdentity.roles.includes("teacher") && view !== "help") {
        setView("administration");
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

  async function loadCarryForwardContext(targetWeek = weekStart) {
    if (!selectedAssignmentId) return;
    try {
      const previous = addDays(targetWeek, -7);
      const saved = await api<FridayValidationRead>(
        `/api/v1/friday-validations?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${encodeURIComponent(previous)}`,
      );
      setCarryForwardLessonIds(saved.carry_forward_curriculum_lesson_ids);
    } catch (caught) {
      const text = caught instanceof Error ? caught.message.toLowerCase() : "";
      if (text.includes("not found")) setCarryForwardLessonIds([]);
      else throw caught;
    }
  }

  async function generatePlan() {
    if (!selectedAssignmentId) return;
    if (!selectedAssignment?.curriculum_id) {
      setError("Finish Course Setup Step 2 by adding Curriculum & Pacing before building this week.");
      return;
    }
    setBusy(true);
    setError("");
    setMessage("");
    setWeekCurriculumConfirmed(false);
    setSavedStandardsCount(0);
    setWeekStandardsEditing(false);
    setPlanningAssistComplete(false);
    setPlanningAssistEditing(false);
    setPdfReviewed(false);
    try {
      const generated = await api<PlannedLesson[]>("/api/v1/plans/generate", {
        method: "POST",
        body: JSON.stringify({ assignment_id: selectedAssignmentId, week_start: weekStart }),
      });
      setPlan(sortPlan(generated));
      setValidations(Object.fromEntries(
        generated.map((lesson) => [
          lesson.scheduled_lesson_id,
          { status: "", reason: "", teacherNote: "", carryForward: false },
        ]),
      ));
      setValidationRevision(null);
      await loadCarryForwardContext();
      await loadDraft(false);
      await loadExistingValidation(generated);
      setMessage(
        generated.length
          ? `Built ${generated.length} scheduled lesson${generated.length === 1 ? "" : "s"}. Review this week's curriculum and confirm Step 1 before continuing.`
          : "No curriculum lessons were available for this week. Review Curriculum & Pacing in Course Setup, then build the week again.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function loadExistingValidation(loadedPlan: PlannedLesson[]) {
    if (!selectedAssignmentId) return;
    try {
      const saved = await api<FridayValidationRead>(
        `/api/v1/friday-validations?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${encodeURIComponent(weekStart)}`,
      );
      const byId = new Map(saved.lessons.map((lesson) => [lesson.scheduled_lesson_id, lesson]));
      setValidations(Object.fromEntries(
        loadedPlan.map((lesson) => {
          const stored = byId.get(lesson.scheduled_lesson_id);
          return [
            lesson.scheduled_lesson_id,
            stored
              ? {
                  status: stored.status,
                  reason: stored.reason ?? "",
                  teacherNote: stored.teacher_note ?? "",
                  carryForward: stored.carry_forward,
                }
              : { status: "", reason: "", teacherNote: "", carryForward: false },
          ];
        }),
      ));
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
    if (!selectedAssignment?.curriculum_id) {
      setError("Finish Course Setup Step 2 by adding Curriculum & Pacing before reopening a week.");
      return;
    }
    setBusy(true);
    setError("");
    setWeekCurriculumConfirmed(false);
    try {
      const loaded = await api<PlannedLesson[]>(
        `/api/v1/plans?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${weekStart}`,
      );
      setPlan(sortPlan(loaded));
      setValidations(Object.fromEntries(
        loaded.map((lesson) => [
          lesson.scheduled_lesson_id,
          { status: "", reason: "", teacherNote: "", carryForward: false },
        ]),
      ));
      await loadCarryForwardContext();
      await loadDraft(false);
      await loadExistingValidation(loaded);
      setMessage(
        loaded.length
          ? `Reopened ${loaded.length} scheduled lesson${loaded.length === 1 ? "" : "s"}. Review and confirm this week's curriculum before continuing.`
          : "No saved week was found for this Monday-starting week.",
      );
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
      setDraftState({ ...emptyDraft, ...loaded.content });
      setDraftRevision(loaded.revision);
      setDraftSubmissionStatus(loaded.submission_status);
      setDraftSubmittedAt(loaded.submitted_at);
      setDraftDirty(false);
      setPlanningAssistComplete(true);
      setPlanningAssistEditing(false);
      setPlanReviewOpen(false);
      if (showNotFound) {
        setMessage(
          `Draft revision ${loaded.revision} reopened · ${submissionLabel(loaded.submission_status)}.`,
        );
      }
    } catch (caught) {
      const text = caught instanceof Error ? caught.message : "Weekly draft could not be loaded.";
      if (text.toLowerCase().includes("not found")) {
        setDraftRevision(null);
        setDraftSubmissionStatus("not_submitted");
        setDraftSubmittedAt(null);
        setDraftState({
          ...emptyDraft,
          teacher: identity?.display_name ?? "",
          course: selectedAssignment?.course_name ?? "",
          grade: selectedAssignment?.grade_band ?? "",
          week_of: weekStart,
        });
        setDraftDirty(false);
        setPlanningAssistComplete(false);
        setPlanningAssistEditing(false);
        setPlanReviewOpen(true);
        if (showNotFound) setMessage("No saved draft exists for this week yet.");
      } else {
        throw caught;
      }
    }
  }

  async function saveDraft(): Promise<WeeklyDraft | null> {
    if (!selectedAssignmentId) return null;
    if (!draft.literacy_standards.trim()) {
      setError("Add or select a Literacy Standards entry before saving the weekly plan.");
      return null;
    }
    if (!draft.act_preparation.trim()) {
      setError(
        "Complete ACT Preparation before saving the weekly plan. Enter a teacher-selected note such as N/A when no ACT focus applies this week.",
      );
      return null;
    }
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
      setDraftState(saved.content);
      setDraftSubmissionStatus(saved.submission_status);
      setDraftSubmittedAt(saved.submitted_at);
      setDraftDirty(false);
      setPlanReviewOpen(false);
      setPdfReviewed(false);
      setMessage(
        `Draft revision ${saved.revision} saved · ${submissionLabel(saved.submission_status)}. Step 4 complete — review the PDF next.`,
      );
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly draft save failed.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function saveCloseoutDraft(): Promise<WeeklyDraft | null> {
    if (!selectedAssignmentId) return null;
    setBusy(true);
    setError("");
    try {
      const saved = await api<WeeklyDraft>("/api/v1/weekly-drafts/closeout", {
        method: "PUT",
        body: JSON.stringify({
          assignment_id: selectedAssignmentId,
          week_start: weekStart,
          content: draft,
          expected_revision: draftRevision,
        }),
      });
      setDraftRevision(saved.revision);
      setDraftState(saved.content);
      setDraftSubmissionStatus(saved.submission_status);
      setDraftSubmittedAt(saved.submitted_at);
      setDraftDirty(false);
      setMessage(`Friday closeout saved at revision ${saved.revision}.`);
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Friday closeout save failed.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitDraft(revisionOverride?: number): Promise<WeeklyDraft | null> {
    const revision = revisionOverride ?? draftRevision;
    if (!selectedAssignmentId || !revision || (draftDirty && revisionOverride === undefined)) {
      return null;
    }
    setBusy(true);
    setError("");
    try {
      const submitted = await api<WeeklyDraft>("/api/v1/weekly-drafts/submit", {
        method: "POST",
        body: JSON.stringify({
          assignment_id: selectedAssignmentId,
          week_start: weekStart,
          expected_revision: revision,
        }),
      });
      setDraftRevision(submitted.revision);
      setDraftState(submitted.content);
      setDraftSubmissionStatus(submitted.submission_status);
      setDraftSubmittedAt(submitted.submitted_at);
      setDraftDirty(false);
      setMessage(`Weekly plan revision ${submitted.revision} submitted successfully.`);
      return submitted;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly plan submission failed.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function documentBlob(
    document: Exclude<DocumentKind, "completed-packet">,
  ): Promise<Blob> {
    if (!session?.access_token) throw new Error("Your authenticated session is unavailable.");
    if (!draftRevision || draftDirty) {
      throw new Error("Save the current plan before reviewing or exporting PDFs.");
    }
    const path = document === "lesson-plan"
      ? "/api/v1/documents/anniston-lesson-plan-packet"
      : `/api/v1/documents/anniston-hqi/${document}`;
    const response = await fetch(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(draft),
    });
    if (!response.ok) {
      throw new Error(await responseDetail(response, "The planning document could not be generated."));
    }
    return await response.blob();
  }

  async function completedPacketBlob(): Promise<Blob> {
    if (!session?.access_token || !selectedAssignmentId) {
      throw new Error("Your authenticated session is unavailable.");
    }
    const response = await fetch(
      `/api/v1/teacher-submissions/${encodeURIComponent(selectedAssignmentId)}/completed-packet?week_start=${encodeURIComponent(weekStart)}`,
      { headers: { Authorization: `Bearer ${session.access_token}` } },
    );
    if (!response.ok) {
      throw new Error(
        await responseDetail(response, "The completed weekly packet could not be loaded."),
      );
    }
    return await response.blob();
  }

  function presentPdf(
    blob: Blob,
    title: string,
    filename: string,
    action: DocumentAction,
  ) {
    if (action === "download") {
      downloadBlob(blob, filename);
      return;
    }
    const url = URL.createObjectURL(blob);
    if (action === "view") {
      closePdfPreview();
      setPdfPreview({ url, title });
      return;
    }
    const frame = window.document.createElement("iframe");
    frame.style.position = "fixed";
    frame.style.width = "0";
    frame.style.height = "0";
    frame.style.border = "0";
    frame.src = url;
    frame.onload = () => {
      window.setTimeout(() => {
        frame.contentWindow?.focus();
        frame.contentWindow?.print();
        window.setTimeout(() => {
          URL.revokeObjectURL(url);
          frame.remove();
        }, 5_000);
      }, 500);
    };
    window.document.body.appendChild(frame);
  }

  async function exportDocument(
    document: Exclude<DocumentKind, "completed-packet">,
    action: DocumentAction,
  ) {
    setDocumentWorking(document);
    setBusy(true);
    setError("");
    setMessage(
      document === "lesson-plan"
        ? "Building the weekly lesson plan PDF…"
        : `Preparing ${documentTitle(document)}…`,
    );
    try {
      const blob = await documentBlob(document);
      presentPdf(blob, documentTitle(document), `anniston-${document}-${weekStart}.pdf`, action);
      if (document === "lesson-plan" && action === "view") setPdfReviewed(true);
      setMessage(
        `${documentTitle(document)} ${
          action === "download"
            ? "downloaded"
            : action === "print"
              ? "opened for printing"
              : "ready for review"
        }.${document === "lesson-plan" && action === "view" ? " Viewing the PDF does not submit the weekly plan; submission remains a separate Step 6 action." : ""}`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Document export failed.");
    } finally {
      setDocumentWorking(null);
      setBusy(false);
    }
  }

  async function exportCompletedPacket(action: DocumentAction) {
    setDocumentWorking("completed-packet");
    setBusy(true);
    setError("");
    setMessage("Preparing completed weekly packet…");
    try {
      const blob = await completedPacketBlob();
      presentPdf(
        blob,
        "Completed Weekly Packet",
        `completed-weekly-packet-${weekStart}.pdf`,
        action,
      );
      setCompletedPacketReviewed(true);
      setMessage(
        `Completed Weekly Packet ${
          action === "download"
            ? "downloaded"
            : action === "print"
              ? "opened for printing"
              : "ready for review"
        }.`,
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Completed weekly packet could not be opened.",
      );
    } finally {
      setDocumentWorking(null);
      setBusy(false);
    }
  }

  function updateValidation(id: string, patch: Partial<ValidationEntry>) {
    setValidations((current) => ({
      ...current,
      [id]: { ...current[id], ...patch },
    }));
  }

  async function saveValidation(): Promise<FridayValidationRead | null> {
    if (!selectedAssignmentId) return null;
    if (plan.some((lesson) => !validations[lesson.scheduled_lesson_id]?.status)) {
      setError("Every scheduled lesson must have a Friday validation status.");
      return null;
    }
    if (plan.some((lesson) => {
      const entry = validations[lesson.scheduled_lesson_id];
      return entry.status === "missed" && !entry.reason.trim();
    })) {
      setError("Every missed lesson requires a reason before Friday validation is completed.");
      return null;
    }
    setBusy(true);
    setError("");
    try {
      let expectedRevision = validationRevision;
      if (expectedRevision === null) {
        try {
          const existing = await api<FridayValidationRead>(
            `/api/v1/friday-validations?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${encodeURIComponent(weekStart)}`,
          );
          expectedRevision = existing.revision;
          setValidationRevision(existing.revision);
        } catch (caught) {
          const text = caught instanceof Error ? caught.message.toLowerCase() : "";
          if (!text.includes("not found")) throw caught;
        }
      }
      const saved = await api<FridayValidationRead>("/api/v1/friday-validations", {
        method: "PUT",
        body: JSON.stringify({
          assignment_id: selectedAssignmentId,
          week_start: weekStart,
          expected_revision: expectedRevision,
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
      setMessage(
        `Friday validation complete. ${saved.carry_forward_curriculum_lesson_ids.length} lesson${saved.carry_forward_curriculum_lesson_ids.length === 1 ? "" : "s"} selected to carry forward. Step 1 complete — finish the teacher reflection next.`,
      );
      return saved;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Friday validation failed.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitFridayCloseout() {
    if (!validationFinalized) {
      setError("Complete Friday validation before closing the week.");
      return;
    }
    if (!reflectionIsComplete) {
      setError(
        "Complete all 12 Weekly Reflection / PLC Discussion prompts before submitting the Friday closeout.",
      );
      return;
    }
    const saved = await saveCloseoutDraft();
    if (!saved) return;
    const submitted = await submitDraft(saved.revision);
    if (!submitted) return;
    setCompletedPacketSubmitted(true);
    setCompletedPacketReviewed(false);
    setMessage(
      "Friday closeout submitted. Step 2 complete — review the completed weekly packet before continuing to next week.",
    );
  }

  function continueToNextWeek() {
    if (!completedPacketSubmitted || !completedPacketReviewed) {
      setError("Review the completed weekly packet before continuing to next week.");
      return;
    }
    const next = addDays(weekStart, 7);
    setWeekStart(next);
    clearPlanningContext(selectedAssignment, next);
    setView("plan");
    setMessage(`Friday closeout complete. Build or reconcile the week of ${next}.`);
  }

  const meetingDates = useMemo(() => {
    if (!selectedAssignment) return [];
    const unavailable = new Set(
      scheduleExceptions
        .filter((exception) => !exception.is_available)
        .map((exception) => exception.exception_date),
    );
    return Array.from({ length: 5 }, (_item, index) => addDays(weekStart, index)).filter(
      (iso) => {
        const date = new Date(`${iso}T12:00:00`);
        const weekday = date.getDay() === 0 ? 7 : date.getDay();
        return !unavailable.has(iso)
          && selectedAssignment.meeting_patterns.some(
            (pattern) => pattern.weekdays.includes(weekday)
              && iso >= pattern.effective_start
              && iso <= pattern.effective_end,
          );
      },
    );
  }, [scheduleExceptions, selectedAssignment, weekStart]);

  async function movePlannedLesson(lesson: PlannedLesson, nextDate: string) {
    if (nextDate === lesson.lesson_date) return;
    setBusy(true);
    setError("");
    try {
      await api<unknown>(
        `/api/v1/plans/lessons/${encodeURIComponent(lesson.scheduled_lesson_id)}`,
        { method: "PATCH", body: JSON.stringify({ lesson_date: nextDate }) },
      );
      setPlan((current) => sortPlan(
        current.map((item) => (
          item.scheduled_lesson_id === lesson.scheduled_lesson_id
            ? { ...item, lesson_date: nextDate }
            : item
        )),
      ));
      setWeekCurriculumConfirmed(false);
      setSavedStandardsCount(0);
      setWeekStandardsEditing(false);
      setPlanningAssistComplete(false);
      setPlanningAssistEditing(false);
      setPdfReviewed(false);
      setMessage(
        `${lesson.lesson_title} moved to ${nextDate}. Confirm this week's curriculum again, then review standards and planning assistance.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Lesson day could not be changed.");
    } finally {
      setBusy(false);
    }
  }

  function resetPlanningAfterScheduleChange() {
    setWeekCurriculumConfirmed(false);
    setSavedStandardsCount(0);
    setWeekStandardsEditing(false);
    setPlanningAssistComplete(false);
    setPlanningAssistEditing(false);
    setPdfReviewed(false);
  }

  async function replacePlannedLesson() {
    if (!lessonReplacement) return;
    setBusy(true);
    setError("");
    try {
      await api<{ status: string }>(
        `/api/v1/plans/lessons/${encodeURIComponent(lessonReplacement.scheduledLessonId)}/replace`,
        {
          method: "POST",
          body: JSON.stringify({
            replacement_kind: lessonReplacement.mode,
            manual_unit_title: lessonReplacement.mode === "manual" ? lessonReplacement.unitTitle : null,
            manual_lesson_title: lessonReplacement.mode === "manual" ? lessonReplacement.lessonTitle : null,
            manual_learning_targets: lessonReplacement.mode === "manual"
              ? lessonReplacement.learningTargets.split("\n").map((value) => value.trim()).filter(Boolean)
              : [],
            manual_assessment: lessonReplacement.mode === "manual" ? lessonReplacement.assessment : null,
            original_disposition: lessonReplacement.mode === "manual"
              ? lessonReplacement.originalDisposition
              : null,
          }),
        },
      );
      const refreshed = await api<PlannedLesson[]>(
        `/api/v1/plans?assignment_id=${encodeURIComponent(selectedAssignmentId)}&week_start=${weekStart}`,
      );
      setPlan(sortPlan(refreshed));
      setLessonReplacement(null);
      resetPlanningAfterScheduleChange();
      setDraftDirty(draftRevision !== null);
      setMessage(
        lessonReplacement.mode === "next"
          ? "The lesson was skipped and the remaining pacing sequence moved forward one instructional day. Review and confirm the week again."
          : `Manual class added. The original curriculum lesson will be ${lessonReplacement.originalDisposition === "postpone" ? "returned to the pacing queue" : "skipped"}. Review and confirm the week again.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The scheduled lesson could not be replaced.");
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
            Close the current week, carry forward what needs attention, and prepare next week
            without losing curriculum sequence.
          </p>
          <button className="primary large" onClick={() => void signIn()}>
            Continue with Google
          </button>
          <div className="boundary-notice">
            Teacher and curriculum data only. Do not enter student names, IDs, grades, IEP/504,
            health, discipline, identifiable student work, or other student-specific information.
          </div>
          {error && <p className="error-message">{error}</p>}
        </section>
      </main>
    );
  }

  const weekStep1 = plan.length > 0 && weekCurriculumConfirmed;
  const weekStep2 = weekStep1 && savedStandardsCount > 0;
  const weekStep3 = weekStep2 && planningAssistComplete;
  const weekStep4 = weekStep3 && savedForReview;
  const weekStep5 = weekStep4 && pdfReviewed;
  const weekStep6 = weekStep5 && draftSubmissionStatus === "submitted" && !draftDirty;

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
        <strong>
          Teacher and curriculum data only. Use class- or group-level instructional observations;
          do not enter student-specific information.
        </strong>
      </div>
      <nav className="workflow-nav" aria-label="Planning workflow">
        <button
          className={view === "dashboard" ? "active" : ""}
          onClick={() => setView("dashboard")}
        >
          Dashboard
        </button>
        {isTeacher && (
          <button
            className={view === "assignment" ? "active" : ""}
            onClick={() => setView("assignment")}
          >
            Course Setup
          </button>
        )}
        {isTeacher && (
          <button
            className={view === "validation" ? "active" : ""}
            onClick={() => openFridayCloseout()}
          >
            Friday validation
          </button>
        )}
        {isTeacher && (
          <button
            className={view === "plan" ? "active" : ""}
            onClick={() => setView("plan")}
          >
            Weekly plan
          </button>
        )}
        {canViewAdministration && (
          <button
            className={view === "administration" ? "active" : ""}
            onClick={() => setView("administration")}
          >
            Administration
          </button>
        )}
        <button
          className={view === "help" ? "active" : ""}
          onClick={() => setView("help")}
        >
          Help
        </button>
      </nav>

      <main>
        {(message || error) && (
          <div
            className={error ? "alert error toast-alert" : "alert success toast-alert"}
            role={error ? "alert" : "status"}
            aria-live={error ? "assertive" : "polite"}
          >
            {error || message}
            <button
              aria-label="Dismiss"
              onClick={() => {
                setError("");
                setMessage("");
              }}
            >
              ×
            </button>
          </div>
        )}
        {busy && <div className="progress-bar" aria-label="Working" />}

        {view === "dashboard" && isTeacher && (
          <>
            <section className="hero">
              <div>
                <p className="eyebrow">Weekly workflow</p>
                <h2>Close this week. Then build the next one.</h2>
                <p>
                  Normal routine: Friday validation → teacher reflection → review completed packet
                  → reconcile carry-forward → plan → review PDF → submit.
                </p>
              </div>
              <div className="hero-actions">
                <button
                  className="primary"
                  disabled={!selectedAssignmentId}
                  onClick={() => openFridayCloseout()}
                >
                  Complete Friday validation
                </button>
                <button
                  className="secondary"
                  disabled={!selectedAssignmentId}
                  onClick={() => openPlanningWeek(mondayFor())}
                >
                  Open weekly plan
                </button>
                <button
                  className="secondary"
                  disabled={!selectedAssignmentId}
                  onClick={() => openPlanningWeek(addDays(mondayFor(), 7))}
                >
                  Plan next week early
                </button>
              </div>
            </section>
            <section>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Course setup</p>
                  <h2>Your classes</h2>
                  <p className="supporting">
                    Each card is a separate teaching section. Finish Course Setup before weekly
                    planning.
                  </p>
                </div>
                <button className="secondary" onClick={() => setView("assignment")}>Add class</button>
              </div>
              {assignments.length === 0 ? (
                <div className="empty-state">
                  <h3>No classes configured yet</h3>
                  <p>Create your first Class & Schedule. Curriculum & Pacing is Step 2.</p>
                  <button className="primary" onClick={() => setView("assignment")}>
                    Create class
                  </button>
                </div>
              ) : (
                <div className="grid">
                  {dashboardAssignments.map((assignment) => {
                    const curriculum = assignment.curriculum_id
                      ? curricula.find((item) => item.id === assignment.curriculum_id)
                      : null;
                    return (
                      <article
                        className={`card ${selectedAssignmentId === assignment.id ? "selected" : ""}`}
                        key={assignment.id}
                      >
                        <div className="card-row">
                          <span className="badge">Revision {assignment.revision}</span>
                          <span className="status">
                            {curriculum ? "Pacing added" : "Setup in progress"}
                          </span>
                        </div>
                        <h3>{assignment.course_name}</h3>
                        <p>
                          {assignment.meeting_patterns
                            .map((pattern) => dashboardScheduleLabel(pattern))
                            .join(", ")}
                        </p>
                        <small>
                          {curriculum
                            ? `${curriculum.name} · ${curriculum.version}`
                            : "Curriculum & Pacing not added"}
                        </small>
                        <div className="button-row">
                          {curriculum ? (
                            <button
                              className="link-button"
                              onClick={() => openPlanningWeek(mondayFor(), assignment.id)}
                            >
                              Open weekly plan
                            </button>
                          ) : (
                            <button
                              className="link-button"
                              onClick={() => {
                                setSelectedAssignmentId(assignment.id);
                                setView("assignment");
                              }}
                            >
                              Finish setup
                            </button>
                          )}
                          <button
                            className="link-button"
                            onClick={() => {
                              setSelectedAssignmentId(assignment.id);
                              setView("assignment");
                            }}
                          >
                            Manage class
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </>
        )}

        {view === "dashboard" && !isTeacher && canViewAdministration && (
          <section className="hero">
            <div>
              <p className="eyebrow">Governed administration</p>
              <h2>School and district planning operations</h2>
              <p>Review professional teacher-planning adoption and weekly submission status.</p>
            </div>
            <div className="hero-actions">
              <button className="primary" onClick={() => setView("administration")}>
                Open administration
              </button>
            </div>
          </section>
        )}

        {view === "assignment" && isTeacher && identity && (
          <CourseSetupPanel
            accessToken={session.access_token}
            schoolId={identity.school_id}
            assignments={assignments}
            curricula={curricula}
            selectedAssignmentId={selectedAssignmentId}
            disabled={busy}
            onSelectAssignment={selectPlanningAssignment}
            onAssignmentsChanged={setAssignments}
            onCurriculaChanged={setCurricula}
            onMessage={setMessage}
            onError={setError}
            onStandardsMappingSaved={() => {
              setStandardsMappingVersion((current) => current + 1);
            }}
            onOpenWeeklyPlan={(assignmentId) => openPlanningWeek(mondayFor(), assignmentId)}
          />
        )}
        {view === "administration" && canViewAdministration && (
          <AdministrationOverview
            accessToken={session.access_token}
            roles={identity?.roles ?? []}
            disabled={busy}
          />
        )}
        {view === "help" && identity && <HelpPage roles={identity.roles} />}

        {view === "validation" && isTeacher && (
          <section
            className="panel"
            data-friday-week-start={weekStart}
            data-friday-assignment-id={selectedAssignmentId}
          >
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Friday closeout</p>
                <h2>Close one Monday–Friday week at a time</h2>
                <p className="supporting">
                  Validate instruction, complete the teacher-authored reflection, review the
                  completed packet, then continue to the following week.
                </p>
              </div>
            </div>
            <div className="setup-stepper closeout-stepper">
              <StepMarker
                number={1}
                title="Validate"
                complete={validationFinalized}
                active={!validationFinalized}
              />
              <StepMarker
                number={2}
                title="Reflect & Submit"
                complete={completedPacketSubmitted}
                active={validationFinalized && !completedPacketSubmitted}
              />
              <StepMarker
                number={3}
                title="Review Packet"
                complete={completedPacketReviewed}
                active={completedPacketSubmitted && !completedPacketReviewed}
              />
              <StepMarker
                number={4}
                title="Continue"
                complete={false}
                active={completedPacketReviewed}
              />
            </div>

            {!validationFinalized && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">1</span>
                  <div>
                    <p className="eyebrow">Step 1</p>
                    <h2>Friday validation</h2>
                    <p className="supporting">
                      Confirm what actually happened. You decide whether missed or modified
                      instruction carries forward.
                    </p>
                  </div>
                </div>
                <div className="toolbar">
                  <label>
                    Course
                    <select
                      value={selectedAssignmentId}
                      onChange={(event) => selectPlanningAssignment(event.target.value)}
                    >
                      <option value="">Select a class</option>
                      {assignments
                        .filter((assignment) => assignment.curriculum_id)
                        .map((assignment) => (
                          <option value={assignment.id} key={assignment.id}>
                            {assignment.course_name}
                          </option>
                        ))}
                    </select>
                  </label>
                  <WeekSelector value={weekStart} disabled={busy} onChange={selectPlanningWeek} />
                  <button
                    className="secondary"
                    disabled={!selectedAssignmentId || busy}
                    onClick={() => void loadPlan()}
                  >
                    Load week
                  </button>
                </div>
                {plan.length === 0 ? (
                  <div className="empty-state">
                    <p>Load the scheduled Monday–Friday week before completing validation.</p>
                  </div>
                ) : (
                  <div className="validation-list">
                    {plan.map((lesson) => {
                      const entry = validations[lesson.scheduled_lesson_id] ?? {
                        status: "",
                        reason: "",
                        teacherNote: "",
                        carryForward: false,
                      };
                      return (
                        <article className="validation-row" key={lesson.scheduled_lesson_id}>
                          <div className="day-block">
                            <strong>{lesson.lesson_date}</strong>
                            <span>{lesson.planned_minutes} minutes</span>
                          </div>
                          <div className="lesson-block">
                            <small>{lesson.unit_title}</small>
                            <strong>{lesson.lesson_title}</strong>
                            <label>
                              Status
                              <select
                                value={entry.status}
                                onChange={(event) => {
                                  const status = event.target.value as LessonStatus | "";
                                  updateValidation(lesson.scheduled_lesson_id, {
                                    status,
                                    carryForward: status === "missed"
                                      ? true
                                      : (status === "completed" || status === "skipped")
                                        ? false
                                        : entry.carryForward,
                                  });
                                }}
                              >
                                <option value="">Select outcome</option>
                                <option value="completed">Completed</option>
                                <option value="modified">Modified</option>
                                <option value="missed">Missed</option>
                                <option value="skipped">Skipped / not needed</option>
                              </select>
                            </label>
                            <label>
                              Reason or note
                              <input
                                value={entry.reason}
                                required={entry.status === "missed"}
                                placeholder={
                                  entry.status === "missed"
                                    ? "Required for a missed lesson"
                                    : "Optional"
                                }
                                onChange={(event) => updateValidation(
                                  lesson.scheduled_lesson_id,
                                  { reason: event.target.value },
                                )}
                              />
                            </label>
                            <label>
                              Planning note
                              <input
                                value={entry.teacherNote}
                                placeholder="Optional note for future planning"
                                onChange={(event) => updateValidation(
                                  lesson.scheduled_lesson_id,
                                  { teacherNote: event.target.value },
                                )}
                              />
                            </label>
                            <label className="check">
                              <input
                                type="checkbox"
                                checked={entry.carryForward}
                                disabled={
                                  entry.status === "completed"
                                  || entry.status === "skipped"
                                  || !entry.status
                                }
                                onChange={(event) => updateValidation(
                                  lesson.scheduled_lesson_id,
                                  { carryForward: event.target.checked },
                                )}
                              />
                              Carry this lesson forward
                            </label>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                )}
                <div className="action-bar">
                  <div>
                    <strong>
                      {plan.filter(
                        (lesson) => !validations[lesson.scheduled_lesson_id]?.status,
                      ).length} lessons still pending
                    </strong>
                    <span>Nothing carries forward unless you select it.</span>
                  </div>
                  <button
                    className="primary"
                    disabled={
                      !plan.length
                      || plan.some((lesson) => !validations[lesson.scheduled_lesson_id]?.status)
                      || busy
                    }
                    onClick={() => void saveValidation()}
                  >
                    Complete Friday validation & continue
                  </button>
                </div>
              </section>
            )}

            {validationFinalized && !completedPacketSubmitted && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">2</span>
                  <div>
                    <p className="eyebrow">Step 2</p>
                    <h2>Weekly Reflection / PLC Discussion</h2>
                    <p className="supporting">
                      Complete all 12 district prompts yourself. TPP does not generate or rewrite
                      reflection responses.
                    </p>
                  </div>
                </div>
                <div className="setup-step-summary complete-summary">
                  <div>
                    <strong>Validation complete</strong>
                    <p>Saved revision {validationRevision ?? "—"}. Carry-forward choices are preserved.</p>
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setValidationFinalized(false)}
                  >
                    Edit validation
                  </button>
                </div>
                <AiReflectionPanel
                  accessToken={session.access_token}
                  assignmentId={selectedAssignmentId || null}
                  weekStart={weekStart}
                  disabled={busy}
                  onApplyReflection={(value) => updateDraft((current) => ({
                    ...current,
                    reflection: value,
                  }))}
                />
                <div className="button-row">
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void saveCloseoutDraft()}
                  >
                    Save reflection progress
                  </button>
                  {savedForReview && (
                    <>
                      <button
                        className="secondary"
                        onClick={() => void exportDocument("weekly-reflection", "view")}
                      >
                        View reflection PDF
                      </button>
                      <button
                        className="secondary"
                        onClick={() => void exportDocument("weekly-reflection", "download")}
                      >
                        Download reflection PDF
                      </button>
                      <button
                        className="secondary"
                        onClick={() => void exportDocument("weekly-reflection", "print")}
                      >
                        Print reflection PDF
                      </button>
                    </>
                  )}
                  <button
                    className="primary"
                    disabled={!reflectionIsComplete || busy}
                    onClick={() => void submitFridayCloseout()}
                  >
                    Submit Friday closeout & continue
                  </button>
                </div>
              </section>
            )}

            {completedPacketSubmitted && !completedPacketReviewed && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">3</span>
                  <div>
                    <p className="eyebrow">Step 3</p>
                    <h2>Review completed weekly packet</h2>
                    <p className="supporting">
                      This immutable packet contains the week's Instructional Planning Framework,
                      Week at a Glance, and teacher-authored reflection.
                    </p>
                  </div>
                </div>
                <div className="pdf-review-grid">
                  <article className="card">
                    <h3>Completed Weekly Packet</h3>
                    <p className="supporting">
                      Current week's planning documents + teacher-authored reflection
                    </p>
                    <div className="button-row">
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => void exportCompletedPacket("view")}
                      >
                        {documentWorking === "completed-packet"
                          ? "Preparing…"
                          : "View completed packet"}
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => void exportCompletedPacket("download")}
                      >
                        Download PDF
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => void exportCompletedPacket("print")}
                      >
                        Print
                      </button>
                    </div>
                  </article>
                </div>
              </section>
            )}

            {completedPacketSubmitted && completedPacketReviewed && (
              <section className="setup-step-summary complete-summary">
                <div>
                  <strong>Step 3 complete · Completed Weekly Packet reviewed</strong>
                  <p>View, download, or print the immutable packet again at any time before continuing.</p>
                </div>
                <div className="button-row">
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void exportCompletedPacket("view")}
                  >
                    View packet
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void exportCompletedPacket("download")}
                  >
                    Download PDF
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void exportCompletedPacket("print")}
                  >
                    Print
                  </button>
                </div>
              </section>
            )}

            {completedPacketReviewed && (
              <section className="setup-ready-card">
                <div className="step-heading">
                  <span className="step-number">4</span>
                  <div>
                    <p className="eyebrow">Step 4</p>
                    <h2>Continue to next week</h2>
                    <p className="supporting">
                      The current week is validated, reflected, submitted, and reviewed. TPP will
                      now move to the following Monday-starting week.
                    </p>
                  </div>
                </div>
                <button className="primary" disabled={busy} onClick={continueToNextWeek}>
                  Continue to next week
                </button>
              </section>
            )}
          </section>
        )}

        {view === "plan" && isTeacher && (
          <section className="panel">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Weekly planning</p>
                <h2>{selectedAssignment?.course_name ?? "Weekly Plan"}</h2>
                <p className="supporting">
                  Only the current step is expanded. Completed steps stay as short summaries with
                  an Edit or Reopen action, so you can revise without losing saved teacher work.
                </p>
              </div>
            </div>
            <div className="setup-stepper weekly-plan-stepper">
              <StepMarker
                number={1}
                title="Build Week"
                complete={weekStep1}
                active={!weekStep1}
              />
              <StepMarker
                number={2}
                title="Standards"
                complete={weekStep2 && !weekStandardsEditing}
                active={weekStep1 && (!weekStep2 || weekStandardsEditing)}
              />
              <StepMarker
                number={3}
                title="Planning Assist"
                complete={weekStep3 && !planningAssistEditing}
                active={weekStep2 && (!weekStep3 || planningAssistEditing)}
              />
              <StepMarker
                number={4}
                title="Review & Save"
                complete={weekStep4 && !planReviewOpen}
                active={weekStep3 && (!weekStep4 || planReviewOpen)}
              />
              <StepMarker
                number={5}
                title="Review PDF"
                complete={weekStep5}
                active={weekStep4 && !weekStep5}
              />
              <StepMarker
                number={6}
                title="Submit"
                complete={weekStep6}
                active={weekStep5 && !weekStep6}
              />
            </div>

            {!weekStep1 && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">1</span>
                  <div>
                    <p className="eyebrow">Step 1</p>
                    <h2>Build or reconcile the week</h2>
                    <p className="supporting">
                      Choose a class and Monday-starting week. TPP uses its saved Curriculum &
                      Pacing, class-specific progress, class schedule, calendar, exceptions, and
                      teacher-selected carry-forward. Review the resulting lessons before you
                      confirm this step.
                    </p>
                  </div>
                </div>
                <div className="toolbar">
                  <label>
                    Class
                    <select
                      value={selectedAssignmentId}
                      onChange={(event) => selectPlanningAssignment(event.target.value)}
                    >
                      <option value="">Select a class</option>
                      {assignments.map((assignment) => (
                        <option value={assignment.id} key={assignment.id}>
                          {assignment.course_name}
                          {assignment.curriculum_id ? "" : " · setup incomplete"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <WeekSelector value={weekStart} disabled={busy} onChange={selectPlanningWeek} />
                </div>
                {selectedAssignment && !selectedAssignmentReady ? (
                  <div className="guidance-card warning-card">
                    <strong>Course Setup is not complete.</strong>
                    <p>Add Curriculum & Pacing before TPP can schedule lessons for this class.</p>
                    <button className="primary" onClick={() => setView("assignment")}>
                      Finish Course Setup
                    </button>
                  </div>
                ) : (
                  <>
                    <ScheduleExceptionPanel
                      key={`${selectedAssignmentId}-${weekStart}`}
                      accessToken={session.access_token}
                      assignmentId={selectedAssignmentId}
                      weekStart={weekStart}
                      disabled={busy}
                      onExceptionsChanged={setScheduleExceptions}
                      onChanged={() => {
                        setPlan([]);
                        setWeekCurriculumConfirmed(false);
                        setCarryForwardLessonIds([]);
                        setSavedStandardsCount(0);
                        setWeekStandardsEditing(false);
                        setPlanningAssistComplete(false);
                        setPlanningAssistEditing(false);
                        setPdfReviewed(false);
                        setValidations({});
                        setValidationRevision(null);
                        setValidationFinalized(false);
                      }}
                    />
                    <div className="button-row">
                      <button
                        className="primary"
                        disabled={!selectedAssignmentId || busy}
                        onClick={() => void generatePlan()}
                      >
                        Build / reconcile week
                      </button>
                      <button
                        className="secondary"
                        disabled={!selectedAssignmentId || busy}
                        onClick={() => void loadPlan()}
                      >
                        Reopen saved week
                      </button>
                    </div>
                  </>
                )}

                {plan.length > 0 && (
                  <section className="week-curriculum-section">
                    <div className="section-heading compact">
                      <div>
                        <p className="eyebrow">Review Step 1</p>
                        <h3>This week's Curriculum & Pacing</h3>
                        <p className="supporting">
                          Confirm these lessons and teaching days before standards or planning
                          assistance appear.
                        </p>
                      </div>
                    </div>
                    <div className="weekly-curriculum-list">
                      {plan.map((lesson) => {
                        const carried = Boolean(
                          lesson.curriculum_lesson_id
                          && carryForwardLessonIds.includes(lesson.curriculum_lesson_id),
                        );
                        return (
                          <article
                            className={`weekly-curriculum-item ${carried ? "carried-forward" : ""}`}
                            key={lesson.scheduled_lesson_id}
                          >
                            <div>
                              <div className="card-row">
                                {lesson.source_type === "manual" ? (
                                  <span className="badge">Manual class</span>
                                ) : carried ? (
                                  <span className="badge carry-badge">Carried forward</span>
                                ) : (
                                  <span className="badge">Scheduled curriculum</span>
                                )}
                                <span>{lesson.planned_minutes} minutes</span>
                              </div>
                              <small>{lesson.unit_title}</small>
                              <h3>
                                {lesson.lesson_title}
                                {lesson.segment_number > 1 ? ` · Segment ${lesson.segment_number}` : ""}
                              </h3>
                            </div>
                            <label>
                              Teach on
                              <select
                                value={lesson.lesson_date}
                                disabled={busy}
                                onChange={(event) => void movePlannedLesson(lesson, event.target.value)}
                              >
                                {meetingDates.map((date) => (
                                  <option value={date} key={date}>
                                    {new Date(`${date}T12:00:00`).toLocaleDateString(undefined, {
                                      weekday: "long",
                                      month: "short",
                                      day: "numeric",
                                    })}
                                  </option>
                                ))}
                              </select>
                            </label>
                            {lesson.source_type === "curriculum" ? (
                              <button
                                type="button"
                                className="secondary"
                                disabled={busy}
                                onClick={() => setLessonReplacement({
                                  scheduledLessonId: lesson.scheduled_lesson_id,
                                  mode: "next",
                                  unitTitle: "",
                                  lessonTitle: "",
                                  learningTargets: "",
                                  assessment: "",
                                  originalDisposition: "skip",
                                })}
                              >
                                Replace scheduled lesson
                              </button>
                            ) : (
                              <small>
                                Original curriculum lesson {lesson.replacement_disposition === "postpone"
                                  ? "will return to the pacing queue"
                                  : "was skipped"}.
                              </small>
                            )}
                          </article>
                        );
                      })}
                    </div>
                    {lessonReplacement ? (
                      <section className="guidance-card lesson-replacement-editor" aria-labelledby="lesson-replacement-title">
                        <div className="section-heading compact">
                          <div>
                            <p className="eyebrow">Adjust this week</p>
                            <h3 id="lesson-replacement-title">Replace scheduled lesson</h3>
                            <p className="supporting">
                              Choose the next item in your pacing sequence or add a manual class.
                            </p>
                          </div>
                        </div>
                        <fieldset className="replacement-choice-group">
                          <legend>Replacement</legend>
                          <label className="check">
                            <input
                              type="radio"
                              name="replacement-mode"
                              checked={lessonReplacement.mode === "next"}
                              onChange={() => setLessonReplacement((current) => current
                                ? { ...current, mode: "next" }
                                : current)}
                            />
                            Use the next pacing lesson and move the remaining sequence forward
                          </label>
                          <label className="check">
                            <input
                              type="radio"
                              name="replacement-mode"
                              checked={lessonReplacement.mode === "manual"}
                              onChange={() => setLessonReplacement((current) => current
                                ? { ...current, mode: "manual" }
                                : current)}
                            />
                            Add a manual class
                          </label>
                        </fieldset>
                        {lessonReplacement.mode === "manual" ? (
                          <div className="form-grid">
                            <label>
                              Unit / topic
                              <input
                                required
                                value={lessonReplacement.unitTitle}
                                maxLength={300}
                                onChange={(event) => setLessonReplacement((current) => current
                                  ? { ...current, unitTitle: event.target.value }
                                  : current)}
                              />
                            </label>
                            <label>
                              Lesson / focus
                              <input
                                required
                                value={lessonReplacement.lessonTitle}
                                maxLength={1000}
                                onChange={(event) => setLessonReplacement((current) => current
                                  ? { ...current, lessonTitle: event.target.value }
                                  : current)}
                              />
                            </label>
                            <label className="full-width">
                              Learning target(s) — one per line
                              <textarea
                                rows={3}
                                maxLength={20000}
                                value={lessonReplacement.learningTargets}
                                onChange={(event) => setLessonReplacement((current) => current
                                  ? { ...current, learningTargets: event.target.value }
                                  : current)}
                              />
                            </label>
                            <label className="full-width">
                              Assessment / check
                              <textarea
                                rows={2}
                                maxLength={2000}
                                value={lessonReplacement.assessment}
                                onChange={(event) => setLessonReplacement((current) => current
                                  ? { ...current, assessment: event.target.value }
                                  : current)}
                              />
                            </label>
                            <fieldset className="full-width replacement-choice-group">
                              <legend>What should happen to the original curriculum lesson?</legend>
                              <label className="check">
                                <input
                                  type="radio"
                                  name="original-disposition"
                                  checked={lessonReplacement.originalDisposition === "skip"}
                                  onChange={() => setLessonReplacement((current) => current
                                    ? { ...current, originalDisposition: "skip" }
                                    : current)}
                                />
                                Replace and skip the original
                              </label>
                              <label className="check">
                                <input
                                  type="radio"
                                  name="original-disposition"
                                  checked={lessonReplacement.originalDisposition === "postpone"}
                                  onChange={() => setLessonReplacement((current) => current
                                    ? { ...current, originalDisposition: "postpone" }
                                    : current)}
                                />
                                Insert the manual class and postpone the original
                              </label>
                            </fieldset>
                          </div>
                        ) : null}
                        <div className="boundary-notice">
                          Professional planning content only. Do not enter student names, IDs,
                          grades, IEP/504 information, or identifiable student work.
                        </div>
                        <div className="button-row">
                          <button
                            type="button"
                            className="primary"
                            disabled={busy || (lessonReplacement.mode === "manual" && (
                              !lessonReplacement.unitTitle.trim() || !lessonReplacement.lessonTitle.trim()
                            ))}
                            onClick={() => void replacePlannedLesson()}
                          >
                            Apply replacement
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busy}
                            onClick={() => setLessonReplacement(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      </section>
                    ) : null}
                    <div className="action-bar">
                      <div>
                        <strong>{plan.length} scheduled lesson{plan.length === 1 ? "" : "s"}</strong>
                        <span>Nothing advances to standards until you confirm this sequence.</span>
                      </div>
                      <button
                        type="button"
                        className="primary"
                        disabled={busy}
                        onClick={() => {
                          setWeekCurriculumConfirmed(true);
                          setMessage("Step 1 complete — this week's Curriculum & Pacing is confirmed. Review authoritative standards next.");
                        }}
                      >
                        Confirm this week's curriculum & continue
                      </button>
                    </div>
                  </section>
                )}
              </section>
            )}

            {weekStep1 && (
              <section className="setup-step-summary complete-summary">
                <div>
                  <strong>Step 1 complete · This week's curriculum confirmed</strong>
                  <p>
                    {plan.length} scheduled lesson{plan.length === 1 ? "" : "s"} for the week of
                    {` ${weekStart}`}.
                  </p>
                </div>
                <button
                  className="secondary"
                  onClick={() => {
                    setWeekCurriculumConfirmed(false);
                    setSavedStandardsCount(0);
                    setWeekStandardsEditing(false);
                    setPlanningAssistComplete(false);
                    setPlanningAssistEditing(false);
                    setPdfReviewed(false);
                  }}
                >
                  Review/change week
                </button>
              </section>
            )}

            {weekStep1 && (!weekStep2 || weekStandardsEditing) && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">2</span>
                  <div>
                    <p className="eyebrow">{weekStep2 ? "Edit Step 2" : "Step 2"}</p>
                    <h2>Authoritative standards</h2>
                    <p className="supporting">
                      Confirm and save the governed standards relevant to this week's scheduled
                      curriculum.
                    </p>
                  </div>
                </div>
                <StandardsPanel
                  key={`${selectedAssignmentId}-${weekStart}-${standardsMappingVersion}`}
                  accessToken={session.access_token}
                  assignmentId={selectedAssignmentId || null}
                  weekStart={weekStart}
                  weeklyLessons={plan}
                  onSelectionResolved={resolveSelectedStandards}
                  onSelectionSaved={(selected) => {
                    setSavedStandardsCount(selected.length);
                    resolveSelectedStandards(selected);
                    if (!draftRevision) setPlanningAssistComplete(false);
                    setPdfReviewed(false);
                  }}
                />
                {weekStandardsEditing && weekStep2 && (
                  <div className="button-row">
                    <button
                      className="primary"
                      onClick={() => setWeekStandardsEditing(false)}
                    >
                      Done reviewing standards
                    </button>
                  </div>
                )}
              </section>
            )}

            {weekStep2 && !weekStandardsEditing && (
              <section className="setup-step-summary complete-summary">
                <div>
                  <strong>Step 2 complete · Authoritative standards saved</strong>
                  <p>{savedStandardsCount} governed standard{savedStandardsCount === 1 ? "" : "s"} selected.</p>
                </div>
                <button
                  className="secondary"
                  onClick={() => setWeekStandardsEditing(true)}
                >
                  Edit standards
                </button>
              </section>
            )}

            {weekStep2 && (!planningAssistComplete || planningAssistEditing) && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">3</span>
                  <div>
                    <p className="eyebrow">{planningAssistComplete ? "Reopen Step 3" : "Step 3"}</p>
                    <h2>Planning assistance</h2>
                    <p className="supporting">
                      Use, edit, regenerate, or skip suggestions. Nothing enters the saved plan
                      without your action.
                    </p>
                  </div>
                </div>
                <AiPlanningPanel
                  accessToken={session.access_token}
                  assignmentId={selectedAssignmentId || null}
                  weekStart={weekStart}
                  hasScheduledLessons={plan.length > 0}
                  hasSavedStandards={savedStandardsCount > 0}
                  currentFields={{
                    unit_topic: draft.unit_topic,
                    literacy_standards: draft.literacy_standards,
                    act_preparation: draft.act_preparation,
                    learning_targets: draft.learning_targets,
                    know: draft.know,
                    understand: draft.understand,
                    do_statement: draft.do,
                    activities: draft.activities,
                    assessments: draft.assessments,
                    resources: draft.resources,
                    monday: draft.monday,
                    tuesday: draft.tuesday,
                    wednesday: draft.wednesday,
                    thursday: draft.thursday,
                    friday: draft.friday,
                  }}
                  onApplyField={applyAiPlanningField}
                />
                <div className="action-bar">
                  <div>
                    <strong>Teacher decision</strong>
                    <span>You may use planning assistance or continue with your own planning text.</span>
                  </div>
                  <button
                    className="primary"
                    onClick={() => {
                      setPlanningAssistComplete(true);
                      setPlanningAssistEditing(false);
                      setPlanReviewOpen(true);
                    }}
                  >
                    Continue to review/edit plan
                  </button>
                </div>
              </section>
            )}

            {weekStep3 && !planningAssistEditing && (
              <section className="setup-step-summary complete-summary">
                <div>
                  <strong>Step 3 complete · Planning assistance reviewed</strong>
                  <p>Teacher-approved or teacher-authored planning text is preserved.</p>
                </div>
                <button
                  className="secondary"
                  onClick={() => setPlanningAssistEditing(true)}
                >
                  Reopen planning assistance
                </button>
              </section>
            )}

            {weekStep3 && (!weekStep4 || planReviewOpen) && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">4</span>
                  <div>
                    <p className="eyebrow">{weekStep4 ? "Edit Step 4" : "Step 4"}</p>
                    <h2>Review and save the working plan</h2>
                    <p className="supporting">
                      Review the Framework and Week at a Glance in district PDF order. Save before
                      PDF review.
                    </p>
                  </div>
                </div>
                <PlanningPdfFieldsPanel draft={draft} disabled={busy} onChange={updateDraft} />
                <div className="button-row">
                  <button
                    className="primary"
                    disabled={!selectedAssignmentId || busy}
                    onClick={() => void saveDraft()}
                  >
                    Save plan & continue
                  </button>
                  {draftRevision && (
                    <button
                      className="secondary"
                      onClick={() => setPlanReviewOpen(false)}
                    >
                      Cancel editing
                    </button>
                  )}
                </div>
              </section>
            )}

            {weekStep4 && !planReviewOpen && (
              <section className="setup-step-summary complete-summary">
                <div>
                  <strong>Step 4 complete · Draft revision {draftRevision}</strong>
                  <p>{submissionLabel(draftSubmissionStatus)} · no unsaved changes.</p>
                </div>
                <button
                  className="secondary"
                  onClick={() => setPlanReviewOpen(true)}
                >
                  Edit plan
                </button>
              </section>
            )}

            {weekStep4 && !pdfReviewed && (
              <section className="setup-step-card active-step">
                <div className="step-heading">
                  <span className="step-number">5</span>
                  <div>
                    <p className="eyebrow">Step 5</p>
                    <h2>Review Weekly Lesson Plan PDF</h2>
                    <p className="supporting">
                      Open the Instructional Planning Framework + Week at a Glance and review it.
                      Viewing the PDF only completes this review step; it does not submit or
                      resubmit the weekly plan. Submission is a separate Step 6 action.
                    </p>
                  </div>
                </div>
                {documentWorking && (
                  <p className="working-status" role="status" aria-live="polite">
                    <span className="button-spinner" aria-hidden="true" />
                    Preparing {documentTitle(documentWorking)}…
                  </p>
                )}
                <div className="pdf-review-grid">
                  <article className="card">
                    <h3>Weekly Lesson Plan</h3>
                    <p className="supporting">
                      Instructional Planning Framework + Week at a Glance
                    </p>
                    <div className="button-row">
                      <button
                        className="primary"
                        disabled={busy}
                        onClick={() => void exportDocument("lesson-plan", "view")}
                      >
                        {documentWorking === "lesson-plan" ? "Preparing…" : "View PDF"}
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => void exportDocument("lesson-plan", "download")}
                      >
                        Download PDF
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => void exportDocument("lesson-plan", "print")}
                      >
                        Print
                      </button>
                    </div>
                  </article>
                </div>
              </section>
            )}

            {weekStep5 && (
              <section className="setup-step-summary complete-summary">
                <div>
                  <strong>Step 5 complete · Weekly Lesson Plan PDF reviewed</strong>
                  <p>PDF review is complete. Viewing did not submit the plan; Step 6 controls submission separately.</p>
                </div>
                <div className="button-row">
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void exportDocument("lesson-plan", "view")}
                  >
                    View PDF
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void exportDocument("lesson-plan", "download")}
                  >
                    Download PDF
                  </button>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => void exportDocument("lesson-plan", "print")}
                  >
                    Print
                  </button>
                </div>
              </section>
            )}

            {weekStep5 && (
              <section className="setup-ready-card">
                <div className="step-heading">
                  <span className="step-number">{weekStep6 ? "✓" : "6"}</span>
                  <div>
                    <p className="eyebrow">Step 6</p>
                    <h2>{weekStep6 ? "Weekly plan submitted" : "Submit weekly plan"}</h2>
                    <p className="supporting">
                      {weekStep6
                        ? "This saved revision was already submitted. Reviewing the PDF did not submit it again."
                        : "Select Submit weekly plan when you are ready to create the immutable administrator-visible upcoming lesson plan for this class and Monday-starting week."}
                    </p>
                  </div>
                </div>
                {draftSubmittedAt && (
                  <p className="guidance-text">
                    Last submitted {new Date(draftSubmittedAt).toLocaleString()}.
                  </p>
                )}
                <button
                  className="primary"
                  disabled={!savedForReview || weekStep6 || busy}
                  onClick={() => void submitDraft()}
                >
                  {draftSubmissionStatus === "revised_after_submission"
                    ? "Resubmit weekly plan"
                    : weekStep6
                      ? "Weekly plan submitted"
                      : "Submit weekly plan"}
                </button>
              </section>
            )}
          </section>
        )}
      </main>

      {pdfPreview && (
        <div
          className="pdf-modal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label={`${pdfPreview.title} preview`}
        >
          <section className="pdf-modal">
            <div className="pdf-modal-heading">
              <h2>{pdfPreview.title}</h2>
              <button type="button" className="secondary" onClick={closePdfPreview}>
                Close preview
              </button>
            </div>
            <iframe src={pdfPreview.url} title={`${pdfPreview.title} PDF`} />
          </section>
        </div>
      )}
      <footer>
        Prepared with Teacher Planning Platform · Anniston controlled pilot · Teacher and curriculum
        data only
      </footer>
    </div>
  );
}
