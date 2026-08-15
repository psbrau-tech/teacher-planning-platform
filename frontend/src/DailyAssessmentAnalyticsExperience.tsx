import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./daily-assessment-analytics.css";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const assessmentSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

type Identity = {
  id: string;
  roles: string[];
};

type AssessmentTypeCount = { key: string; label: string; count: number };

type WeeklyAssessmentTrend = {
  week_start: string;
  submitted_course_weeks: number;
  distinct_teachers: number;
  daily_assessment_entries: number;
  cfu_entries: number;
  evidence_entries: number;
  assessment_types: AssessmentTypeCount[];
};

type AssessmentAnalytics = {
  period_start: string;
  period_end: string;
  submitted_course_weeks: number;
  distinct_teachers: number;
  daily_assessment_entries: number;
  cfu_entries: number;
  evidence_entries: number;
  assessment_types: AssessmentTypeCount[];
  weekday_entries: Array<{ weekday: string; count: number }>;
  weekly_trends: WeeklyAssessmentTrend[];
  source_scope: "immutable-submitted-lesson-plans";
  classification_method: "deterministic-keyword-v1";
  interpretation: "planned-formative-assessment-signals-only";
  evaluation: "none";
};

type PeriodKind = "current_week" | "last_4_weeks" | "custom";

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

function weekLabel(iso: string): string {
  const value = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(value.getTime())) return iso;
  return value.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function assessmentCount(trend: WeeklyAssessmentTrend, key: string): number {
  return trend.assessment_types.find((item) => item.key === key)?.count ?? 0;
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  } catch {
    // Use the bounded fallback below.
  }
  return "Daily formative-assessment analytics could not be loaded.";
}

export function DailyAssessmentAnalyticsExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [portalTarget, setPortalTarget] = useState<Element | null>(null);
  const [periodKind, setPeriodKind] = useState<PeriodKind>("current_week");
  const currentMonday = mondayFor();
  const [customStart, setCustomStart] = useState(currentMonday);
  const [customEnd, setCustomEnd] = useState(addDays(currentMonday, 6));
  const [analytics, setAnalytics] = useState<AssessmentAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const accessToken = session?.access_token ?? "";
  const canView = identity?.roles.some((role) => (
    role === "school_admin" || role === "district_admin" || role === "platform_admin"
  )) ?? false;

  const period = useMemo(() => {
    if (periodKind === "last_4_weeks") {
      return {
        start: addDays(currentMonday, -21),
        end: addDays(currentMonday, 6),
        label: "Last 4 weeks",
      };
    }
    if (periodKind === "custom") {
      return { start: customStart, end: customEnd, label: "Custom period" };
    }
    return {
      start: currentMonday,
      end: addDays(currentMonday, 6),
      label: "Current week",
    };
  }, [currentMonday, customEnd, customStart, periodKind]);

  const trendTypeColumns = useMemo(() => {
    const exitTickets: AssessmentTypeCount = {
      key: "exit_ticket",
      label: "Exit tickets / slips",
      count: analytics?.assessment_types.find((item) => item.key === "exit_ticket")?.count ?? 0,
    };
    const otherTopTypes = (analytics?.assessment_types ?? [])
      .filter((item) => item.key !== "exit_ticket")
      .slice(0, 4);
    return [exitTickets, ...otherTopTypes];
  }, [analytics]);

  useEffect(() => {
    if (!assessmentSupabase) return;
    void assessmentSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = assessmentSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setAnalytics(null);
      setError("");
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
    const updateTarget = () => {
      setPortalTarget(document.querySelector(
        '.administration-overview [role="tabpanel"][aria-label="Administration reporting"]',
      ));
    };
    updateTarget();
    const observer = new MutationObserver(updateTarget);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!accessToken || !canView || !portalTarget || !period.start || !period.end) return;
    let active = true;
    setLoading(true);
    setError("");
    const query = new URLSearchParams({
      period_start: period.start,
      period_end: period.end,
    });
    void fetch(`/api/v1/assessment-analytics/school?${query.toString()}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(async (response) => {
      if (!response.ok) throw new Error(await readError(response));
      const next = await response.json() as AssessmentAnalytics;
      if (active) setAnalytics(next);
    }).catch((caught: unknown) => {
      if (active) {
        setAnalytics(null);
        setError(caught instanceof Error
          ? caught.message
          : "Daily formative-assessment analytics could not be loaded.");
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [accessToken, canView, period.end, period.start, portalTarget]);

  if (!portalTarget || !accessToken || !canView) return null;

  const topType = analytics?.assessment_types[0] ?? null;

  return createPortal(
    <section className="daily-assessment-analytics" aria-labelledby="daily-assessment-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Instructional planning signals</p>
          <h3 id="daily-assessment-title">Planned daily formative-assessment mix</h3>
          <p className="supporting">
            TPP reads the Checks for Understanding and Evidence of Student Learning cells already in
            submitted lesson plans and classifies recognizable assessment types such as exit tickets.
            This is planning analytics, not a teacher-performance measure and not evidence that an
            assessment was actually administered or that students mastered the content.
          </p>
        </div>
      </div>

      <div className="assessment-period-control">
        <label>
          Assessment analytics period
          <select
            value={periodKind}
            disabled={loading}
            onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}
          >
            <option value="current_week">Current week</option>
            <option value="last_4_weeks">Last 4 weeks</option>
            <option value="custom">Custom dates</option>
          </select>
        </label>
        {periodKind === "custom" ? (
          <>
            <label>
              Start
              <input
                type="date"
                value={customStart}
                onChange={(event) => setCustomStart(event.target.value)}
              />
            </label>
            <label>
              End
              <input
                type="date"
                value={customEnd}
                onChange={(event) => setCustomEnd(event.target.value)}
              />
            </label>
          </>
        ) : null}
        <span>{period.label}: {period.start} through {period.end}</span>
      </div>

      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {loading ? <p className="working-status" role="status">Updating assessment analytics…</p> : null}

      {analytics && !loading ? (
        <>
          <div className="assessment-summary-grid">
            <article>
              <strong>{analytics.daily_assessment_entries}</strong>
              <span>planned daily assessment entries</span>
            </article>
            <article>
              <strong>{analytics.distinct_teachers}</strong>
              <span>teachers represented</span>
            </article>
            <article>
              <strong>{analytics.submitted_course_weeks}</strong>
              <span>submitted course-weeks analyzed</span>
            </article>
            <article>
              <strong>{topType?.count ?? 0}</strong>
              <span>{topType ? `${topType.label} mentions` : "recognized type mentions"}</span>
            </article>
          </div>

          <div className="assessment-analytics-grid">
            <article className="card">
              <h4>Assessment types teachers are planning</h4>
              {analytics.assessment_types.length ? (
                <table className="assessment-type-table">
                  <thead><tr><th scope="col">Planned type</th><th scope="col">Daily entries</th></tr></thead>
                  <tbody>
                    {analytics.assessment_types.map((item) => (
                      <tr key={item.key}><th scope="row">{item.label}</th><td>{item.count}</td></tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p>No recognizable daily assessment entries are present in submitted plans for this period.</p>
              )}
            </article>

            <article className="card">
              <h4>Where daily assessment planning appears</h4>
              <table className="assessment-type-table">
                <thead><tr><th scope="col">Day</th><th scope="col">Entries</th></tr></thead>
                <tbody>
                  {analytics.weekday_entries.map((item) => (
                    <tr key={item.weekday}><th scope="row">{item.weekday}</th><td>{item.count}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="assessment-source-note">
                {analytics.cfu_entries} CFU cells and {analytics.evidence_entries} Evidence of Student
                Learning cells contain planned entries in this period. One day may match more than one
                assessment type.
              </p>
            </article>
          </div>

          <article className="card assessment-weekly-trend-card">
            <div className="assessment-trend-heading">
              <div>
                <h4>Week-over-week planned assessment trend</h4>
                <p>
                  Track exit tickets/slips and the most common additional assessment types across
                  submitted plan weeks. Counts remain anonymous school-level planning signals.
                </p>
              </div>
            </div>
            {analytics.weekly_trends.length ? (
              <div className="assessment-trend-scroll" tabIndex={0}>
                <table className="assessment-type-table assessment-trend-table">
                  <thead>
                    <tr>
                      <th scope="col">Week of</th>
                      <th scope="col">Course-weeks</th>
                      <th scope="col">Teachers represented</th>
                      <th scope="col">Daily entries</th>
                      {trendTypeColumns.map((item) => (
                        <th scope="col" key={item.key}>{item.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {analytics.weekly_trends.map((trend) => (
                      <tr key={trend.week_start}>
                        <th scope="row">{weekLabel(trend.week_start)}</th>
                        <td>{trend.submitted_course_weeks}</td>
                        <td>{trend.distinct_teachers}</td>
                        <td>{trend.daily_assessment_entries}</td>
                        {trendTypeColumns.map((item) => (
                          <td key={`${trend.week_start}-${item.key}`}>
                            {assessmentCount(trend, item.key)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p>No submitted lesson-plan weeks are represented in this period.</p>
            )}
            <p className="assessment-source-note">
              Read trend counts alongside submitted course-week and anonymous teacher coverage. TPP
              does not normalize these counts into teacher comparisons or assume every course meets
              five days per week, so a lower weekly count may reflect different coverage or schedules.
            </p>
          </article>

          <div className="guidance-card compact-guidance assessment-interpretation">
            <strong>How to use this in coaching and PLCs</strong>
            <p>
              Use the mix and weekly trend to ask instructional questions—for example, whether
              teachers want more low-prep exit-ticket options, whether a strategy is becoming more
              common across submitted plans, or whether one assessment format is dominating planning.
              “Other / not yet classified” is intentional: TPP keeps unfamiliar wording visible as a
              count rather than guessing what the teacher meant. No lesson-plan text is sent to AI for
              this classification.
            </p>
          </div>
        </>
      ) : null}
    </section>,
    portalTarget,
  );
}
