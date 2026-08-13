import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const ownerTimeSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

type Identity = {
  id: string;
  roles: string[];
};

type ActiveTime = {
  period_start: string;
  period_end: string;
  active_time_teachers: number;
  course_setup_total_seconds: number;
  weekly_planning_total_seconds: number;
  reflection_total_seconds: number;
  friday_closeout_total_seconds: number;
  other_friday_closeout_total_seconds: number;
  median_course_setup_seconds_per_teacher: number;
  median_weekly_planning_seconds_per_teacher_week: number;
  median_reflection_seconds_per_teacher_week: number;
  median_friday_closeout_seconds_per_teacher_week: number;
  median_other_friday_closeout_seconds_per_teacher_week: number;
  onboarding_weekly_planning_teacher_weeks: number;
  median_onboarding_weekly_planning_seconds: number;
  steady_state_weekly_planning_teacher_weeks: number;
  median_steady_state_weekly_planning_seconds: number;
  onboarding_reflection_teacher_weeks: number;
  median_onboarding_reflection_seconds: number;
  steady_state_reflection_teacher_weeks: number;
  median_steady_state_reflection_seconds: number;
};

type PeriodKind = "pilot" | "current_week" | "last_4_weeks" | "custom";

function localIsoDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localIsoDate(date);
}

function mondayFor(date = new Date()): string {
  const copy = new Date(date);
  const day = copy.getDay();
  copy.setDate(copy.getDate() + (day === 0 ? -6 : 1 - day));
  return localIsoDate(copy);
}

function activeMinutes(seconds: number): string {
  if (!seconds) return "—";
  const minutes = seconds / 60;
  return minutes < 10 ? minutes.toFixed(1) : Math.round(minutes).toString();
}

function Metric({ value, label, detail }: { value: string | number; label: string; detail?: string }) {
  return (
    <div className="owner-metric">
      <strong>{value}</strong>
      <span>{label}</span>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    return typeof payload.detail === "string" && payload.detail.trim()
      ? payload.detail
      : fallback;
  } catch {
    return fallback;
  }
}

export function OwnerActiveTimeBreakout() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [portalTarget, setPortalTarget] = useState<Element | null>(null);
  const [periodKind, setPeriodKind] = useState<PeriodKind>("pilot");
  const [customStart, setCustomStart] = useState("2026-08-13");
  const [customEnd, setCustomEnd] = useState(localIsoDate());
  const [activeTime, setActiveTime] = useState<ActiveTime | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isPlatformAdmin = identity?.roles.includes("platform_admin") ?? false;
  const currentMonday = mondayFor();
  const today = localIsoDate();
  const period = useMemo(() => {
    if (periodKind === "current_week") {
      return { start: currentMonday, end: addDays(currentMonday, 6), label: "Current week" };
    }
    if (periodKind === "last_4_weeks") {
      return { start: addDays(currentMonday, -21), end: addDays(currentMonday, 6), label: "Last 4 weeks" };
    }
    if (periodKind === "custom") {
      return { start: customStart, end: customEnd, label: "Custom period" };
    }
    return { start: "2026-08-13", end: today, label: "Active-time release to date" };
  }, [currentMonday, customEnd, customStart, periodKind, today]);

  useEffect(() => {
    if (!ownerTimeSupabase) return;
    void ownerTimeSupabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      if (data.session) {
        void fetch("/api/v1/session", {
          headers: { Authorization: `Bearer ${data.session.access_token}` },
        }).then(async (response) => {
          if (response.ok) setIdentity(await response.json() as Identity);
        });
      }
    });
    const { data } = ownerTimeSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setActiveTime(null);
      if (nextSession) {
        void fetch("/api/v1/session", {
          headers: { Authorization: `Bearer ${nextSession.access_token}` },
        }).then(async (response) => {
          if (response.ok) setIdentity(await response.json() as Identity);
        });
      }
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const updateTarget = () => setPortalTarget(document.querySelector(".owner-tab"));
    updateTarget();
    const observer = new MutationObserver(updateTarget);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!session?.access_token || !isPlatformAdmin || !portalTarget || !period.start || !period.end) {
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    const query = new URLSearchParams({ period_start: period.start, period_end: period.end });
    void fetch(`/api/v1/product-owner/active-time?${query.toString()}`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    }).then(async (response) => {
      if (!response.ok) throw new Error(await readError(response, "Active-time reporting could not be loaded."));
      if (active) setActiveTime(await response.json() as ActiveTime);
    }).catch((caught: unknown) => {
      if (active) {
        setActiveTime(null);
        setError(caught instanceof Error ? caught.message : "Active-time reporting could not be loaded.");
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [isPlatformAdmin, period.end, period.start, portalTarget, session?.access_token]);

  if (!portalTarget || !session || !isPlatformAdmin) return null;

  return createPortal(
    <section className="owner-section owner-active-time-breakout" aria-label="Planning and reflection active time">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Planning vs reflection</p>
          <h3>Where is active TPP time going?</h3>
          <p className="supporting">
            Platform Owner only. Weekly Planning includes the planning workflow and AI-assisted
            planning. Teacher Reflection measures the required 12-prompt reflection step separately.
            Other Friday Closeout covers validation, packet review, and closeout work outside the
            reflection step. These are active TPP interaction estimates, not total teacher planning time.
          </p>
        </div>
      </div>

      <div className="owner-period-control">
        <label>
          Reporting period
          <select value={periodKind} onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}>
            <option value="pilot">Active-time release to date</option>
            <option value="current_week">Current week</option>
            <option value="last_4_weeks">Last 4 weeks</option>
            <option value="custom">Custom dates</option>
          </select>
        </label>
        {periodKind === "custom" ? (
          <>
            <label>
              Start
              <input type="date" value={customStart} onChange={(event) => setCustomStart(event.target.value)} />
            </label>
            <label>
              End
              <input type="date" value={customEnd} onChange={(event) => setCustomEnd(event.target.value)} />
            </label>
          </>
        ) : null}
        <span className="owner-period-label">{period.label}: {period.start} through {period.end}</span>
      </div>

      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {loading ? <p className="working-status" role="status">Updating active-time breakout…</p> : null}

      {activeTime && !loading ? (
        <>
          <div className="owner-summary-grid compact-grid">
            <Metric
              value={activeMinutes(activeTime.median_weekly_planning_seconds_per_teacher_week)}
              label="median Weekly Planning active minutes"
              detail="per teacher-week"
            />
            <Metric
              value={activeMinutes(activeTime.median_reflection_seconds_per_teacher_week)}
              label="median Teacher Reflection active minutes"
              detail="per teacher-week"
            />
            <Metric
              value={activeMinutes(activeTime.median_other_friday_closeout_seconds_per_teacher_week)}
              label="median other Friday Closeout active minutes"
              detail="per teacher-week · reflection excluded"
            />
            <Metric
              value={activeMinutes(activeTime.median_course_setup_seconds_per_teacher)}
              label="median Course Setup active minutes"
              detail="per teacher in selected period"
            />
          </div>

          <div className="owner-summary-grid">
            <Metric
              value={activeMinutes(activeTime.median_onboarding_weekly_planning_seconds)}
              label="onboarding planning median"
              detail={`${activeTime.onboarding_weekly_planning_teacher_weeks} teacher-weeks · first 14 days`}
            />
            <Metric
              value={activeMinutes(activeTime.median_onboarding_reflection_seconds)}
              label="onboarding reflection median"
              detail={`${activeTime.onboarding_reflection_teacher_weeks} teacher-weeks · first 14 days`}
            />
            <Metric
              value={activeMinutes(activeTime.median_steady_state_weekly_planning_seconds)}
              label="steady-state planning median"
              detail={`${activeTime.steady_state_weekly_planning_teacher_weeks} teacher-weeks · day 15+`}
            />
            <Metric
              value={activeMinutes(activeTime.median_steady_state_reflection_seconds)}
              label="steady-state reflection median"
              detail={`${activeTime.steady_state_reflection_teacher_weeks} teacher-weeks · day 15+`}
            />
          </div>

          <p className="guidance-text">
            Keep planning and reflection separate when interpreting workload. A longer reflection
            period may reflect the required teacher-authored professional thinking rather than
            friction in TPP's planning workflow. The existing total Friday-closeout metric still
            includes reflection for continuity. School and district administrators do not receive
            these duration metrics.
          </p>
        </>
      ) : null}
    </section>,
    portalTarget,
  );
}
