import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useRef, useState } from "react";
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
  const [open, setOpen] = useState(false);
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [lookbackWeeks, setLookbackWeeks] = useState(12);
  const [boundaryConfirmed, setBoundaryConfirmed] = useState(false);
  const [teacherInsight, setTeacherInsight] = useState<TeacherInsight | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const closeButton = useRef<HTMLButtonElement>(null);
  const triggerButton = useRef<HTMLButtonElement>(null);

  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;

  useEffect(() => {
    if (!reflectionSupabase) return;
    void reflectionSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = reflectionSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setOpen(false);
      setTeacherInsight(null);
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
    if (!isTeacher) {
      setStepTarget(null);
      setStepperTarget(null);
      setOpen(false);
      return;
    }

    const syncTargets = () => {
      const panel = findFridayValidationPanel();
      if (!panel) {
        setStepTarget(null);
        setStepperTarget(null);
        setOpen(false);
        return;
      }

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

    syncTargets();
    const observer = new MutationObserver(syncTargets);
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
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
  }, [isTeacher]);

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

  function closePanel() {
    setOpen(false);
    window.requestAnimationFrame(() => triggerButton.current?.focus());
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
    <section className="setup-step-card active-step ri-friday-reflection-step">
      <div className="step-heading">
        <span className="step-number">4</span>
        <div>
          <p className="eyebrow">Step 4 · Optional</p>
          <h2>Review your reflection insights</h2>
          <p className="supporting">
            After your teacher-authored reflection is submitted and the completed packet is reviewed,
            TPP can privately synthesize patterns from your own submitted reflections. This does not
            change your reflection and is not a teacher-performance score.
          </p>
        </div>
      </div>
      <div className="button-row">
        <button
          ref={triggerButton}
          type="button"
          className="primary"
          aria-expanded={open}
          aria-controls="reflection-intelligence-panel"
          onClick={() => {
            setOpen(true);
            setError("");
          }}
        >
          {teacherInsight ? "Review reflection insights again" : "Review reflection insights"}
        </button>
        {teacherInsight ? (
          <span className="ri-step-status" role="status">Private recap generated for this session.</span>
        ) : null}
      </div>
      <p className="ri-step-note">
        Reflection insights are optional. You may continue to Step 5 without generating a recap.
      </p>
    </section>,
    stepTarget,
  ) : null;

  return (
    <>
      {marker}
      {fridayStep}
      {open ? (
        <aside
          id="reflection-intelligence-panel"
          className="ri-panel"
          aria-labelledby="reflection-intelligence-title"
        >
          <div className="ri-panel-header">
            <div>
              <p className="ri-eyebrow">Reflection Intelligence</p>
              <h2 id="reflection-intelligence-title">Your private reflection insights</h2>
            </div>
            <button ref={closeButton} type="button" className="ri-close" onClick={closePanel}>
              Close
            </button>
          </div>

          <div className="ri-boundary" role="note">
            <strong>Instructional insight, not evaluation.</strong>
            <span> No teacher quality score. No student data. AI synthesizes only your submitted teacher-authored professional reflections.</span>
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
              <select value={lookbackWeeks} onChange={(event) => setLookbackWeeks(Number(event.target.value))}>
                <option value={4}>4 weeks</option>
                <option value={8}>8 weeks</option>
                <option value={12}>12 weeks</option>
              </select>
            </label>
          </div>

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

          {error ? <p className="ri-error" role="alert">{error}</p> : null}
        </aside>
      ) : null}
    </>
  );
}
