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
  const [teacher, setTeacher] = useState<StatusState<TeacherStatusRow>>({
    rows: [], loading: false, error: "",
  });
  const currentMonday = mondayFor();
  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;

  useEffect(() => {
    if (!statusSupabase) return;
    void statusSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = statusSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setTeacher({ rows: [], loading: false, error: "" });
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
    function updateTarget() {
      const activeNavigation = document.querySelector(".workflow-nav button.active")?.textContent?.trim();
      setTeacherTarget(
        activeNavigation === "Dashboard" && isTeacher
          ? document.querySelector(".shell > main")
          : null,
      );
    }
    updateTarget();
    const observer = new MutationObserver(updateTarget);
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

  useEffect(() => {
    if (teacherTarget && accessToken && isTeacher) void loadTeacherStatus();
  }, [accessToken, currentMonday, isTeacher, teacherTarget]);

  const nextWeekStart = teacher.rows[0]?.next_week_start
    ?? localIsoDate(new Date(new Date(`${currentMonday}T12:00:00`).getTime() + 7 * 86_400_000));

  const teacherOutstanding = useMemo(() => teacher.rows.filter((row) => (
    (row.current_week_required && !row.current_packet_submitted)
    || (row.next_week_required && !row.next_plan_submitted)
  )).length, [teacher.rows]);

  if (!teacherTarget || !isTeacher) return null;

  return createPortal(
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
  );
}
