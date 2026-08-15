import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./friday-status.css";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const statusSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

type Identity = {
  id: string;
  roles: string[];
};

type TeacherStatusRow = {
  assignment_id: string;
  course_name: string;
  current_week_required: boolean;
  current_packet_submitted: boolean;
  next_week_start: string;
  next_week_required: boolean;
  next_plan_submitted: boolean;
};

type AdminStatusRow = TeacherStatusRow & {
  school_id: string;
  school_name: string;
  teacher_id: string;
  teacher_name: string;
};

type StatusState<T> = {
  rows: T[];
  loading: boolean;
  error: string;
};

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

function dateLabel(iso: string): string {
  const date = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  } catch {
    // Use the bounded fallback below.
  }
  return "Friday submission status could not be loaded.";
}

function statusText(required: boolean, submitted: boolean): string {
  if (!required) return "Not required";
  return submitted ? "Submitted" : "Needs submission";
}

function statusClass(required: boolean, submitted: boolean): string {
  if (!required) return "not-required";
  return submitted ? "complete" : "attention";
}

function StatusBadge({ required, submitted }: { required: boolean; submitted: boolean }) {
  return (
    <span className={`friday-status-badge ${statusClass(required, submitted)}`}>
      {statusText(required, submitted)}
    </span>
  );
}

export function FridayStatusExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [teacherTarget, setTeacherTarget] = useState<Element | null>(null);
  const [adminTarget, setAdminTarget] = useState<Element | null>(null);
  const [teacher, setTeacher] = useState<StatusState<TeacherStatusRow>>({
    rows: [], loading: false, error: "",
  });
  const [admin, setAdmin] = useState<StatusState<AdminStatusRow>>({
    rows: [], loading: false, error: "",
  });
  const currentMonday = mondayFor();
  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;
  const canViewAdministration = identity?.roles.some((role) => (
    role === "school_admin" || role === "district_admin" || role === "platform_admin"
  )) ?? false;

  useEffect(() => {
    if (!statusSupabase) return;
    void statusSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = statusSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setTeacher({ rows: [], loading: false, error: "" });
      setAdmin({ rows: [], loading: false, error: "" });
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    let active = true;
    void fetch("/api/v1/session", {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(async (response) => {
      if (active && response.ok) setIdentity(await response.json() as Identity);
    });
    return () => { active = false; };
  }, [accessToken]);

  useEffect(() => {
    function updateTargets() {
      const activeNavigation = document.querySelector(".workflow-nav button.active")?.textContent?.trim();
      setTeacherTarget(
        activeNavigation === "Dashboard" && isTeacher
          ? document.querySelector(".shell > main")
          : null,
      );
      setAdminTarget(document.querySelector(
        '.administration-overview [role="tabpanel"][aria-label="Administration reporting"]',
      ));
    }
    updateTargets();
    const observer = new MutationObserver(updateTargets);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["class", "aria-selected"],
    });
    return () => observer.disconnect();
  }, [isTeacher]);

  async function loadTeacherStatus() {
    if (!accessToken || !isTeacher) return;
    setTeacher((current) => ({ ...current, loading: true, error: "" }));
    try {
      const query = new URLSearchParams({ week_start: currentMonday });
      const response = await fetch(`/api/v1/friday-status/teacher?${query.toString()}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      setTeacher({ rows: await response.json() as TeacherStatusRow[], loading: false, error: "" });
    } catch (caught) {
      setTeacher({
        rows: [],
        loading: false,
        error: caught instanceof Error ? caught.message : "Friday submission status could not be loaded.",
      });
    }
  }

  async function loadAdminStatus() {
    if (!accessToken || !canViewAdministration) return;
    setAdmin((current) => ({ ...current, loading: true, error: "" }));
    try {
      const query = new URLSearchParams({ week_start: currentMonday });
      const response = await fetch(`/api/v1/friday-status/admin?${query.toString()}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error(await responseError(response));
      setAdmin({ rows: await response.json() as AdminStatusRow[], loading: false, error: "" });
    } catch (caught) {
      setAdmin({
        rows: [],
        loading: false,
        error: caught instanceof Error ? caught.message : "Friday submission status could not be loaded.",
      });
    }
  }

  useEffect(() => {
    if (teacherTarget && accessToken && isTeacher) void loadTeacherStatus();
  }, [accessToken, currentMonday, isTeacher, teacherTarget]);

  useEffect(() => {
    if (adminTarget && accessToken && canViewAdministration) void loadAdminStatus();
  }, [accessToken, adminTarget, canViewAdministration, currentMonday]);

  const nextWeekStart = teacher.rows[0]?.next_week_start
    ?? admin.rows[0]?.next_week_start
    ?? localIsoDate(new Date(new Date(`${currentMonday}T12:00:00`).getTime() + 7 * 86_400_000));

  const teacherOutstanding = useMemo(() => teacher.rows.filter((row) => (
    (row.current_week_required && !row.current_packet_submitted)
    || (row.next_week_required && !row.next_plan_submitted)
  )).length, [teacher.rows]);

  const adminSummary = useMemo(() => {
    const currentRows = admin.rows.filter((row) => row.current_week_required);
    const nextRows = admin.rows.filter((row) => row.next_week_required);
    const teacherRollup = new Map<string, { current: boolean[]; next: boolean[] }>();
    admin.rows.forEach((row) => {
      const status = teacherRollup.get(row.teacher_id) ?? { current: [], next: [] };
      if (row.current_week_required) status.current.push(row.current_packet_submitted);
      if (row.next_week_required) status.next.push(row.next_plan_submitted);
      teacherRollup.set(row.teacher_id, status);
    });
    const currentTeachers = [...teacherRollup.values()].filter((value) => value.current.length > 0);
    const nextTeachers = [...teacherRollup.values()].filter((value) => value.next.length > 0);
    return {
      currentExpected: currentRows.length,
      currentSubmitted: currentRows.filter((row) => row.current_packet_submitted).length,
      currentTeachersExpected: currentTeachers.length,
      currentTeachersComplete: currentTeachers.filter((value) => value.current.every(Boolean)).length,
      nextExpected: nextRows.length,
      nextSubmitted: nextRows.filter((row) => row.next_plan_submitted).length,
      nextTeachersExpected: nextTeachers.length,
      nextTeachersComplete: nextTeachers.filter((value) => value.next.every(Boolean)).length,
    };
  }, [admin.rows]);

  const teacherView = teacherTarget && isTeacher ? createPortal(
    <section className="friday-status teacher-friday-status" aria-labelledby="teacher-friday-status-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Friday status</p>
          <h2 id="teacher-friday-status-title">What still needs to be submitted?</h2>
          <p className="supporting">
            A class-by-class check of this week&apos;s reflection/completed packet and the following
            week&apos;s lesson plan. Status uses submitted records, not work that is only saved as a draft.
          </p>
        </div>
        <button className="secondary" type="button" disabled={teacher.loading} onClick={() => void loadTeacherStatus()}>
          Refresh status
        </button>
      </div>
      {teacher.error ? <p className="error-message" role="alert">{teacher.error}</p> : null}
      {teacher.loading ? <p className="working-status" role="status">Checking submitted status…</p> : null}
      {!teacher.loading && !teacher.error ? (
        <>
          <div className={`friday-status-summary ${teacherOutstanding ? "attention" : "complete"}`}>
            <strong>{teacherOutstanding ? `${teacherOutstanding} class${teacherOutstanding === 1 ? "" : "es"} need attention` : "Everything due is submitted"}</strong>
            <span>
              Current week: {dateLabel(currentMonday)} · Following week: {dateLabel(nextWeekStart)}
            </span>
          </div>
          {teacher.rows.length ? (
            <div className="friday-status-table-wrap" tabIndex={0}>
              <table className="friday-status-table">
                <thead>
                  <tr>
                    <th scope="col">Class</th>
                    <th scope="col">This week&apos;s reflection / packet</th>
                    <th scope="col">Next week&apos;s lesson plan</th>
                  </tr>
                </thead>
                <tbody>
                  {teacher.rows.map((row) => (
                    <tr key={row.assignment_id}>
                      <th scope="row">{row.course_name}</th>
                      <td><StatusBadge required={row.current_week_required} submitted={row.current_packet_submitted} /></td>
                      <td><StatusBadge required={row.next_week_required} submitted={row.next_plan_submitted} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No active class has a current- or following-week submission requirement.</p>
          )}
          <p className="friday-status-note">
            TPP treats the submitted completed packet as the authoritative signal that the required
            teacher-authored reflection was submitted. A Friday 2:00 PM courtesy email is designed to
            name only classes still missing a required submission once scheduled email delivery is activated.
          </p>
        </>
      ) : null}
    </section>,
    teacherTarget,
  ) : null;

  const adminView = adminTarget && canViewAdministration ? createPortal(
    <section className="friday-status admin-friday-status" aria-labelledby="admin-friday-status-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Friday submission status</p>
          <h3 id="admin-friday-status-title">Current-week closeout and following-week planning</h3>
          <p className="supporting">
            Authorized professional operational status by teacher and class. This is submission
            follow-up, not a teacher-performance, quality, effort, or compliance score.
          </p>
        </div>
        <button className="secondary" type="button" disabled={admin.loading} onClick={() => void loadAdminStatus()}>
          Refresh status
        </button>
      </div>
      {admin.error ? <p className="error-message" role="alert">{admin.error}</p> : null}
      {admin.loading ? <p className="working-status" role="status">Updating Friday status…</p> : null}
      {!admin.loading && !admin.error ? (
        <>
          <div className="friday-admin-summary-grid">
            <article>
              <strong>{adminSummary.currentTeachersComplete} / {adminSummary.currentTeachersExpected}</strong>
              <span>teachers fully complete this week</span>
            </article>
            <article>
              <strong>{adminSummary.currentSubmitted} / {adminSummary.currentExpected}</strong>
              <span>completed packets submitted</span>
            </article>
            <article>
              <strong>{adminSummary.nextTeachersComplete} / {adminSummary.nextTeachersExpected}</strong>
              <span>teachers fully planned next week</span>
            </article>
            <article>
              <strong>{adminSummary.nextSubmitted} / {adminSummary.nextExpected}</strong>
              <span>next-week lesson plans submitted</span>
            </article>
          </div>
          {admin.rows.length ? (
            <div className="friday-status-table-wrap" tabIndex={0}>
              <table className="friday-status-table admin-status-table">
                <thead>
                  <tr>
                    <th scope="col">Teacher</th>
                    <th scope="col">Class</th>
                    <th scope="col">This week&apos;s reflection / packet</th>
                    <th scope="col">Next week&apos;s lesson plan</th>
                  </tr>
                </thead>
                <tbody>
                  {admin.rows.map((row) => (
                    <tr key={`${row.teacher_id}:${row.assignment_id}`}>
                      <th scope="row">
                        {row.teacher_name}
                        <small>{row.school_name}</small>
                      </th>
                      <td>{row.course_name}</td>
                      <td><StatusBadge required={row.current_week_required} submitted={row.current_packet_submitted} /></td>
                      <td><StatusBadge required={row.next_week_required} submitted={row.next_plan_submitted} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No active class has a current- or following-week submission requirement.</p>
          )}
          <p className="friday-status-note">
            The planned 3:30 PM Friday administrator email contains aggregate counts and an authenticated
            link only; teacher/class exceptions remain here behind TPP authorization.
          </p>
        </>
      ) : null}
    </section>,
    adminTarget,
  ) : null;

  return <>{teacherView}{adminView}</>;
}
