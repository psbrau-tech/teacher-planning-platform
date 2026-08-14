import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useRef, useState } from "react";
import "./reflection-intelligence.css";

type Identity = {
  id: string;
  display_name: string;
  school_id: string;
  roles: string[];
};

type TeacherInsight = {
  week_start: string;
  lookback_weeks: number;
  source_submission_count: number;
  source_week_count: number;
  scope: "private-teacher";
  evaluation: "none";
  insight: {
    weekly_recap: string;
    recurring_themes: string[];
    strategies_that_work: string[];
    challenges_to_watch: string[];
    carry_forward_ideas: string[];
  };
};

type SupportedTheme = {
  theme: string;
  evidence_summary: string;
  source_refs: number[];
};

type SchoolBrief = {
  week_start: string;
  source_teacher_count: number;
  source_submission_count: number;
  scope: "school-aggregate";
  evaluation: "none";
  brief: {
    common_successes: SupportedTheme[];
    common_challenges: SupportedTheme[];
    emerging_themes: SupportedTheme[];
    discussion_questions: string[];
    possible_actions: string[];
    support_needs: string[];
  };
};

type View = "teacher" | "school";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const reflectionSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

function mondayFor(dateValue = new Date()): string {
  const date = new Date(dateValue);
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
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

function BulletSection({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="ri-result-section">
      <h4>{title}</h4>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}

function ThemeSection({ title, items }: { title: string; items: SupportedTheme[] }) {
  if (!items.length) return null;
  return (
    <section className="ri-result-section">
      <h4>{title}</h4>
      <div className="ri-theme-list">
        {items.map((item) => (
          <article className="ri-theme-card" key={`${title}-${item.theme}`}>
            <strong>{item.theme}</strong>
            <p>{item.evidence_summary}</p>
            <small>Supported by {item.source_refs.length} anonymous teacher sources</small>
          </article>
        ))}
      </div>
    </section>
  );
}

export function ReflectionIntelligenceExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<View>("teacher");
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [lookbackWeeks, setLookbackWeeks] = useState(12);
  const [boundaryConfirmed, setBoundaryConfirmed] = useState(false);
  const [teacherInsight, setTeacherInsight] = useState<TeacherInsight | null>(null);
  const [schoolBrief, setSchoolBrief] = useState<SchoolBrief | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const closeButton = useRef<HTMLButtonElement>(null);
  const triggerButton = useRef<HTMLButtonElement>(null);

  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;
  const canViewSchool = identity?.roles.some((role) => (
    role === "school_admin" || role === "district_admin" || role === "platform_admin"
  )) ?? false;
  const available = Boolean(accessToken && identity && (isTeacher || canViewSchool));

  useEffect(() => {
    if (!reflectionSupabase) return;
    void reflectionSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = reflectionSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setOpen(false);
      setTeacherInsight(null);
      setSchoolBrief(null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    let active = true;
    void fetch("/api/v1/session", {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(async (response) => {
      if (!response.ok || !active) return;
      setIdentity(await response.json() as Identity);
    });
    return () => { active = false; };
  }, [accessToken]);

  useEffect(() => {
    if (!identity) return;
    if (!isTeacher && canViewSchool) setView("school");
  }, [canViewSchool, identity?.id, isTeacher]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => closeButton.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        window.requestAnimationFrame(() => triggerButton.current?.focus());
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const weekLabel = useMemo(() => {
    const value = new Date(`${weekStart}T12:00:00`);
    return Number.isNaN(value.getTime())
      ? weekStart
      : value.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
  }, [weekStart]);

  async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    return await fetch(path, { ...init, headers });
  }

  async function generateTeacherInsight() {
    if (!boundaryConfirmed) {
      setError("Confirm the no-student-data boundary before generating your private recap.");
      return;
    }
    setWorking(true);
    setError("");
    try {
      const response = await authenticatedFetch(
        `/api/v1/reflection-intelligence/teacher/${encodeURIComponent(weekStart)}?lookback_weeks=${lookbackWeeks}`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error(await readError(response, "Your private reflection recap could not be generated."));
      setTeacherInsight(await response.json() as TeacherInsight);
    } catch (caught) {
      setTeacherInsight(null);
      setError(caught instanceof Error ? caught.message : "Your private reflection recap could not be generated.");
    } finally {
      setWorking(false);
    }
  }

  async function generateSchoolBrief() {
    setWorking(true);
    setError("");
    try {
      const response = await authenticatedFetch(
        `/api/v1/reflection-intelligence/school/${encodeURIComponent(weekStart)}`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error(await readError(response, "The school PLC brief could not be generated."));
      setSchoolBrief(await response.json() as SchoolBrief);
    } catch (caught) {
      setSchoolBrief(null);
      setError(caught instanceof Error ? caught.message : "The school PLC brief could not be generated.");
    } finally {
      setWorking(false);
    }
  }

  async function printHandout() {
    if (!schoolBrief) return;
    try {
      await authenticatedFetch(
        `/api/v1/reflection-intelligence/school/${encodeURIComponent(weekStart)}/handout-viewed`,
        { method: "POST" },
      );
    } catch {
      // Content-free adoption telemetry may never block the PLC artifact.
    }
    window.print();
  }

  function closePanel() {
    setOpen(false);
    window.requestAnimationFrame(() => triggerButton.current?.focus());
  }

  if (!reflectionSupabase || !available) return null;

  return (
    <>
      <button
        ref={triggerButton}
        type="button"
        className="ri-launcher"
        aria-expanded={open}
        aria-controls="reflection-intelligence-panel"
        onClick={() => {
          setOpen((current) => !current);
          setError("");
        }}
      >
        Reflection insights
      </button>

      {open ? (
        <aside
          id="reflection-intelligence-panel"
          className="ri-panel"
          aria-labelledby="reflection-intelligence-title"
        >
          <div className="ri-panel-header">
            <div>
              <p className="ri-eyebrow">Reflection Intelligence</p>
              <h2 id="reflection-intelligence-title">Learn from teacher-authored reflection</h2>
            </div>
            <button ref={closeButton} type="button" className="ri-close" onClick={closePanel}>
              Close
            </button>
          </div>

          <div className="ri-boundary" role="note">
            <strong>Instructional insight, not evaluation.</strong>
            <span> No teacher quality score. No student data. AI synthesizes only submitted teacher-authored professional reflections.</span>
          </div>

          {isTeacher && canViewSchool ? (
            <div className="ri-tabs" role="tablist" aria-label="Reflection Intelligence views">
              <button
                type="button"
                role="tab"
                aria-selected={view === "teacher"}
                className={view === "teacher" ? "active" : ""}
                onClick={() => { setView("teacher"); setError(""); }}
              >
                My recap
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={view === "school"}
                className={view === "school" ? "active" : ""}
                onClick={() => { setView("school"); setError(""); }}
              >
                School PLC brief
              </button>
            </div>
          ) : null}

          <div className="ri-controls">
            <label>
              Week of
              <input type="date" value={weekStart} onChange={(event) => {
                setWeekStart(event.target.value);
                setTeacherInsight(null);
                setSchoolBrief(null);
              }} />
            </label>
            {view === "teacher" ? (
              <label>
                Pattern window
                <select value={lookbackWeeks} onChange={(event) => setLookbackWeeks(Number(event.target.value))}>
                  <option value={4}>4 weeks</option>
                  <option value={8}>8 weeks</option>
                  <option value={12}>12 weeks</option>
                </select>
              </label>
            ) : null}
          </div>

          {view === "teacher" && isTeacher ? (
            <div role="tabpanel" aria-label="Private teacher reflection recap">
              <label className="ri-confirmation">
                <input
                  type="checkbox"
                  checked={boundaryConfirmed}
                  onChange={(event) => setBoundaryConfirmed(event.target.checked)}
                />
                <span>
                  I confirm my submitted reflections use class- or group-level observations only and contain no student names, identifiers, identifiable student work, IEP/504, health, discipline, or other student-specific information.
                </span>
              </label>
              <button type="button" className="ri-primary" disabled={working} onClick={() => void generateTeacherInsight()}>
                {working ? "Generating private recap…" : "Generate my private recap"}
              </button>

              {teacherInsight ? (
                <section className="ri-results" aria-live="polite">
                  <p className="ri-meta">
                    Private to you · {teacherInsight.source_submission_count} submitted reflection{teacherInsight.source_submission_count === 1 ? "" : "s"} across {teacherInsight.source_week_count} week{teacherInsight.source_week_count === 1 ? "" : "s"}
                  </p>
                  <h3>Week of {weekLabel}</h3>
                  <p className="ri-recap">{teacherInsight.insight.weekly_recap}</p>
                  <BulletSection title="Recurring themes" items={teacherInsight.insight.recurring_themes} />
                  <BulletSection title="Strategies I keep seeing work" items={teacherInsight.insight.strategies_that_work} />
                  <BulletSection title="Challenges to keep seeing" items={teacherInsight.insight.challenges_to_watch} />
                  <BulletSection title="Carry-forward ideas" items={teacherInsight.insight.carry_forward_ideas} />
                </section>
              ) : null}
            </div>
          ) : null}

          {view === "school" && canViewSchool ? (
            <div role="tabpanel" aria-label="School weekly PLC reflection brief">
              <p className="ri-guidance">
                The school brief uses anonymous teacher source references. TPP requires at least two distinct teachers before a common theme can appear.
              </p>
              <button type="button" className="ri-primary" disabled={working} onClick={() => void generateSchoolBrief()}>
                {working ? "Generating school brief…" : "Generate school PLC brief"}
              </button>

              {schoolBrief ? (
                <section className="ri-results reflection-intelligence-handout" aria-live="polite">
                  <header className="ri-handout-header">
                    <p className="ri-eyebrow">Teacher Planning Platform</p>
                    <h3>Weekly PLC Reflection Brief — Week of {weekLabel}</h3>
                    <p>
                      Aggregate professional learning from {schoolBrief.source_teacher_count} anonymous teacher sources. No teacher quality score; no student data.
                    </p>
                  </header>
                  <ThemeSection title="Common successes" items={schoolBrief.brief.common_successes} />
                  <ThemeSection title="Common challenges" items={schoolBrief.brief.common_challenges} />
                  <ThemeSection title="Emerging themes" items={schoolBrief.brief.emerging_themes} />
                  <BulletSection title="PLC discussion questions" items={schoolBrief.brief.discussion_questions} />
                  <BulletSection title="Possible actions" items={schoolBrief.brief.possible_actions} />
                  <BulletSection title="Support needs" items={schoolBrief.brief.support_needs} />
                  <footer className="ri-handout-footer">
                    AI-synthesized from teacher-authored submitted reflections. Use as a discussion aid; verify context with professional judgment.
                  </footer>
                </section>
              ) : null}

              {schoolBrief ? (
                <button type="button" className="ri-secondary" onClick={() => void printHandout()}>
                  Print PLC handout
                </button>
              ) : null}
            </div>
          ) : null}

          {error ? <p className="ri-error" role="alert">{error}</p> : null}
        </aside>
      ) : null}
    </>
  );
}
