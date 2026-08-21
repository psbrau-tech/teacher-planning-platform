import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
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

type TeacherStatusRow = {
  current_week_required: boolean;
  current_packet_submitted: boolean;
};

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

function findFridayValidationPanel(): HTMLElement | null {
  const panels = Array.from(document.querySelectorAll<HTMLElement>("section.panel"));
  return panels.find((panel) => (
    panel.querySelector(".section-heading .eyebrow")?.textContent?.trim() === "Friday closeout"
  )) ?? null;
}

export function ReflectionIntelligenceExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [stepTarget, setStepTarget] = useState<Element | null>(null);
  const [stepperTarget, setStepperTarget] = useState<Element | null>(null);
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [lookbackWeeks, setLookbackWeeks] = useState(12);
  const [teacherInsight, setTeacherInsight] = useState<TeacherInsight | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;

  useEffect(() => {
    if (!reflectionSupabase) return;
    void reflectionSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = reflectionSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setTeacherInsight(null);
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
      if (!response.ok || !active) return;
      setIdentity(await response.json() as Identity);
    });
    return () => { active = false; };
  }, [accessToken]);

  useEffect(() => {
    if (!isTeacher || !accessToken) {
      setStepTarget(null);
      setStepperTarget(null);
      return;
    }

    let active = true;
    let requestedContext = "";
    let eligibleContext = "";

    const removeInjectedTargets = () => {
      document.querySelectorAll<HTMLElement>("[data-ri-step-marker-host], [data-ri-friday-step-host]")
        .forEach((element) => element.remove());
      document.querySelectorAll<HTMLElement>(".ri-renumbered-continue-marker")
        .forEach((element) => {
          element.classList.remove("ri-renumbered-continue-marker");
          element.removeAttribute("aria-label");
        });
      document.querySelectorAll<HTMLElement>(".ri-renumbered-continue-card")
        .forEach((element) => {
          element.classList.remove("ri-renumbered-continue-card");
          element.removeAttribute("aria-label");
        });
    };

    const clearTargets = () => {
      setStepTarget(null);
      setStepperTarget(null);
      removeInjectedTargets();
    };

    const mountEligibleTargets = (panel: HTMLElement) => {
      const stepper = panel.querySelector<HTMLElement>(".closeout-stepper");
      if (stepper) {
        let markerHost = stepper.querySelector<HTMLElement>("[data-ri-step-marker-host]");
        if (!markerHost) {
          markerHost = document.createElement("div");
          markerHost.dataset.riStepMarkerHost = "true";
          markerHost.className = "ri-step-marker-host";
          const continueMarker = Array.from(stepper.children).find((element) => (
            element.querySelector("small")?.textContent?.trim() === "Continue"
          ));
          if (continueMarker) stepper.insertBefore(markerHost, continueMarker);
          else stepper.appendChild(markerHost);
        }
        setStepperTarget(markerHost);

        const continueMarker = Array.from(stepper.children).find((element) => (
          element !== markerHost
          && element.querySelector("small")?.textContent?.trim() === "Continue"
        ));
        if (continueMarker instanceof HTMLElement) {
          continueMarker.classList.add("ri-renumbered-continue-marker");
          continueMarker.setAttribute("aria-label", "Step 5 Continue");
        }
      }

      const continueCard = Array.from(panel.querySelectorAll<HTMLElement>(".setup-ready-card"))
        .find((card) => card.querySelector("h2")?.textContent?.trim() === "Continue to next week");

      if (!continueCard) {
        setStepTarget(null);
        return;
      }

      continueCard.classList.add("ri-renumbered-continue-card");
      continueCard.setAttribute("aria-label", "Step 5 Continue to next week");

      let stepHost = panel.querySelector<HTMLElement>("[data-ri-friday-step-host]");
      if (!stepHost) {
        stepHost = document.createElement("div");
        stepHost.dataset.riFridayStepHost = "true";
        stepHost.className = "ri-friday-step-host";
        continueCard.parentElement?.insertBefore(stepHost, continueCard);
      }
      setStepTarget(stepHost);
    };

    const syncTargets = () => {
      const panel = findFridayValidationPanel();
      const continueCard = panel
        ? Array.from(panel.querySelectorAll<HTMLElement>(".setup-ready-card"))
          .find((card) => card.querySelector("h2")?.textContent?.trim() === "Continue to next week")
        : null;
      const panelWeekStart = panel?.dataset.fridayWeekStart ?? "";
      const assignmentId = panel?.dataset.fridayAssignmentId ?? "";

      if (!panel || !continueCard || !panelWeekStart || !assignmentId) {
        clearTargets();
        return;
      }

      const context = `${panelWeekStart}:${assignmentId}`;
      if (context === eligibleContext) {
        mountEligibleTargets(panel);
        return;
      }
      if (context === requestedContext) return;

      requestedContext = context;
      clearTargets();
      void fetch(
        `/api/v1/friday-status/teacher?week_start=${encodeURIComponent(panelWeekStart)}`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      ).then(async (response) => {
        if (!response.ok || !active || context !== requestedContext) return;
        const rows = await response.json() as TeacherStatusRow[];
        const requiredRows = rows.filter((row) => row.current_week_required);
        if (!requiredRows.length || requiredRows.some((row) => !row.current_packet_submitted)) return;
        eligibleContext = context;
        setWeekStart(panelWeekStart);
        mountEligibleTargets(panel);
      }).catch(() => {
        // Status failure is fail-closed: do not recommend or enable another AI request.
      });
    };

    syncTargets();
    const observer = new MutationObserver(syncTargets);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-friday-week-start", "data-friday-assignment-id"],
    });

    return () => {
      active = false;
      observer.disconnect();
      removeInjectedTargets();
    };
  }, [accessToken, isTeacher]);

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
    setWorking(true);
    setError("");
    try {
      const response = await authenticatedFetch(
        `/api/v1/reflection-intelligence/teacher/${encodeURIComponent(weekStart)}?lookback_weeks=${lookbackWeeks}`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Your private reflection recap could not be generated."));
      }
      setTeacherInsight(await response.json() as TeacherInsight);
    } catch (caught) {
      setTeacherInsight(null);
      setError(caught instanceof Error ? caught.message : "Your private reflection recap could not be generated.");
    } finally {
      setWorking(false);
    }
  }

  if (!reflectionSupabase || !accessToken || !identity || !isTeacher) return null;

  const marker = stepperTarget ? createPortal(
    <div
      className={`setup-step-marker ${teacherInsight ? "complete" : ""} ${stepTarget && !teacherInsight ? "active" : ""}`}
      aria-label={`Step 4 Reflection insights${teacherInsight ? " complete" : " optional"}`}
    >
      <span className="step-number" aria-hidden="true">{teacherInsight ? "✓" : 4}</span>
      <span><strong>Step 4</strong><small>Reflection insights</small></span>
    </div>,
    stepperTarget,
  ) : null;

  const fridayStep = stepTarget ? createPortal(
    <section className="setup-step-card active-step ri-friday-reflection-step" aria-labelledby="reflection-intelligence-title">
      <div className="step-heading">
        <span className="step-number">4</span>
        <div>
          <p className="eyebrow">Step 4 · Optional</p>
          <h2 id="reflection-intelligence-title">Review your reflection insights</h2>
          <p className="supporting">
            After every required class closeout for this week is submitted, TPP can privately
            synthesize patterns from your own submitted reflections. This combined recap does not
            change your reflections and is not a teacher-performance score.
          </p>
        </div>
      </div>

      <div className="ri-inline-body">
        <div className="ri-boundary" role="note">
          <strong>Instructional insight, not evaluation.</strong>
          <span> No teacher quality score. No student data. AI synthesizes only your submitted teacher-authored professional reflections after the governed local data-boundary preflight.</span>
        </div>

        <div className="ri-controls">
          <label>
            Week of
            <input type="date" value={weekStart} onChange={(event) => {
              setWeekStart(event.target.value);
              setTeacherInsight(null);
            }} />
          </label>
          <label>
            Pattern window
            <select value={lookbackWeeks} onChange={(event) => {
              setLookbackWeeks(Number(event.target.value));
              setTeacherInsight(null);
            }}>
              <option value={4}>4 weeks</option>
              <option value={8}>8 weeks</option>
              <option value={12}>12 weeks</option>
            </select>
          </label>
        </div>

        <div className="button-row ri-action-row">
          <button type="button" className="ri-primary" disabled={working} onClick={() => void generateTeacherInsight()}>
            {working ? "Generating private recap…" : teacherInsight ? "Regenerate my private recap" : "Generate my private recap"}
          </button>
          {teacherInsight ? (
            <span className="ri-step-status" role="status">Private recap generated for this session.</span>
          ) : null}
        </div>

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

        {error ? <p className="ri-error" role="alert">{error}</p> : null}
      </div>

      <p className="ri-step-note">
        Reflection insights are optional. You may continue to Step 5 without generating a recap.
      </p>
    </section>,
    stepTarget,
  ) : null;

  return <>{marker}{fridayStep}</>;
}
