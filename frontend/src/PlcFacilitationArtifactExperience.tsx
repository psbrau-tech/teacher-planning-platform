import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./plc-facilitation-artifact.css";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const plcSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

type Identity = {
  id: string;
  roles: string[];
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

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  } catch {
    // Use the bounded fallback below.
  }
  return fallback;
}

function ThemeList({ title, items }: { title: string; items: SupportedTheme[] }) {
  if (!items.length) return null;
  return (
    <section className="plc-artifact-section">
      <h5>{title}</h5>
      <ul className="plc-theme-list">
        {items.slice(0, 3).map((item) => (
          <li key={`${title}-${item.theme}`}>
            <strong>{item.theme}</strong>
            <span>{item.evidence_summary}</span>
            <small>{item.source_refs.length} anonymous teacher sources</small>
          </li>
        ))}
      </ul>
    </section>
  );
}

function BoundedList({ title, items, limit = 4 }: { title: string; items: string[]; limit?: number }) {
  if (!items.length) return null;
  return (
    <section className="plc-artifact-section">
      <h5>{title}</h5>
      <ul>{items.slice(0, limit).map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}

function FacilitationHandout({ brief, weekLabel }: { brief: SchoolBrief; weekLabel: string }) {
  const focus = brief.brief.common_challenges[0]
    ?? brief.brief.emerging_themes[0]
    ?? brief.brief.common_successes[0]
    ?? null;

  return (
    <article className="plc-facilitation-handout" aria-label="Printable PLC facilitation handout">
      <header className="plc-artifact-header">
        <p className="eyebrow">Teacher Planning Platform · Reflection Intelligence</p>
        <h4>PLC Facilitation Handout — Week of {weekLabel}</h4>
        <p>
          Aggregate professional learning from {brief.source_teacher_count} anonymous teacher sources.
          Themes are discussion signals, not teacher-performance measures.
        </p>
      </header>

      {focus ? (
        <section className="plc-focus-box">
          <span>Suggested meeting focus</span>
          <strong>{focus.theme}</strong>
          <p>{focus.evidence_summary}</p>
        </section>
      ) : null}

      <div className="plc-artifact-columns">
        <div>
          <ThemeList title="Common successes" items={brief.brief.common_successes} />
          <ThemeList title="Common challenges" items={brief.brief.common_challenges} />
          <ThemeList title="Emerging themes" items={brief.brief.emerging_themes} />
        </div>
        <div>
          <section className="plc-artifact-section plc-protocol">
            <h5>40-minute PLC protocol</h5>
            <ol>
              <li><strong>5 min · Orient.</strong> Read the brief and name one aggregate success worth preserving.</li>
              <li><strong>10 min · Examine.</strong> Unpack the focus theme and clarify what the team is seeing.</li>
              <li><strong>10 min · Exchange.</strong> Share instructional moves, examples, and adaptations connected to the theme.</li>
              <li><strong>10 min · Decide.</strong> Select one practical next-step action and the support needed to try it.</li>
              <li><strong>5 min · Commit.</strong> Decide what evidence the team will bring back and when the theme will be revisited.</li>
            </ol>
          </section>
          <BoundedList title="Discussion questions" items={brief.brief.discussion_questions} />
          <BoundedList title="Possible actions" items={brief.brief.possible_actions} />
          <BoundedList title="Support needs" items={brief.brief.support_needs} limit={3} />
        </div>
      </div>

      <section className="plc-action-workspace" aria-label="Non-persistent PLC action workspace">
        <h5>Team action workspace</h5>
        <div><strong>Action we will try:</strong><span /></div>
        <div><strong>Evidence we will bring back:</strong><span /></div>
        <div><strong>Support or resource needed:</strong><span /></div>
        <div><strong>Revisit date:</strong><span /></div>
        <small>This workspace is for the meeting/printout only. TPP does not store these entries.</small>
      </section>

      <footer className="plc-artifact-footer">
        AI synthesis is limited to the governed anonymous school brief. The facilitation protocol and
        handout formatting are deterministic. Do not add student-specific information to PLC notes.
        Use this artifact for professional learning, not personnel evaluation, ranking, or comparison.
      </footer>
    </article>
  );
}

export function PlcFacilitationArtifactExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [portalTarget, setPortalTarget] = useState<Element | null>(null);
  const [weekStart, setWeekStart] = useState(mondayFor());
  const [brief, setBrief] = useState<SchoolBrief | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const accessToken = session?.access_token ?? "";
  const canView = identity?.roles.some((role) => (
    role === "school_admin" || role === "district_admin" || role === "platform_admin"
  )) ?? false;

  const weekLabel = useMemo(() => {
    const value = new Date(`${weekStart}T12:00:00`);
    return Number.isNaN(value.getTime())
      ? weekStart
      : value.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
  }, [weekStart]);

  useEffect(() => {
    if (!plcSupabase) return;
    void plcSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = plcSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setBrief(null);
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

  async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    return await fetch(path, { ...init, headers });
  }

  async function generateHandout() {
    setWorking(true);
    setError("");
    try {
      const response = await authenticatedFetch(
        `/api/v1/reflection-intelligence/school/${encodeURIComponent(weekStart)}`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "The PLC facilitation handout could not be generated."));
      }
      setBrief(await response.json() as SchoolBrief);
    } catch (caught) {
      setBrief(null);
      setError(caught instanceof Error
        ? caught.message
        : "The PLC facilitation handout could not be generated.");
    } finally {
      setWorking(false);
    }
  }

  async function printHandout() {
    if (!brief) return;
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

  if (!portalTarget || !accessToken || !canView) return null;

  return createPortal(
    <section className="plc-facilitation-artifact" aria-labelledby="plc-artifact-title">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">PLC artifact</p>
          <h3 id="plc-artifact-title">Turn the weekly reflection brief into a meeting handout</h3>
          <p className="supporting">
            Generate a condensed one-to-two-page facilitation resource from the governed anonymous school
            brief. The handout adds a fixed meeting protocol and action workspace without another AI pass
            over the content and without storing PLC notes.
          </p>
        </div>
      </div>

      <div className="plc-artifact-controls">
        <label>
          Week of
          <input
            type="date"
            value={weekStart}
            disabled={working}
            onChange={(event) => {
              setWeekStart(event.target.value);
              setBrief(null);
              setError("");
            }}
          />
        </label>
        <button type="button" className="primary" disabled={working} onClick={() => void generateHandout()}>
          {working ? "Generating PLC handout…" : "Generate PLC facilitation handout"}
        </button>
        {brief ? (
          <button type="button" className="secondary" onClick={() => void printHandout()}>
            Print PLC facilitation handout
          </button>
        ) : null}
      </div>

      <p className="plc-artifact-boundary">
        Professional learning only · anonymous aggregate teacher sources · no student data · no teacher
        scoring, ranking, comparison, or personnel evaluation.
      </p>

      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {brief ? <FacilitationHandout brief={brief} weekLabel={weekLabel} /> : null}
    </section>,
    portalTarget,
  );
}
