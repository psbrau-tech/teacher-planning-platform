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

type AssessmentTypeCount = {
  key: string;
  label: string;
  count: number;
};

type AssessmentPlanningSnapshot = {
  submitted_course_weeks: number;
  distinct_teachers: number;
  daily_assessment_entries: number;
  assessment_types: AssessmentTypeCount[];
  source_scope: "immutable-submitted-lesson-plans";
  classification_method: "deterministic-keyword-v1";
  interpretation: "planned-formative-assessment-signals-only";
  evaluation: "none";
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

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localIsoDate(date);
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
        {items.map((item) => (
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

function SummaryList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <section className="plc-artifact-section plc-summary-list">
      <h5>{title}</h5>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}

function AssessmentSnapshot({ snapshot }: { snapshot: AssessmentPlanningSnapshot }) {
  const exitTicketCount = snapshot.assessment_types.find((item) => item.key === "exit_ticket")?.count ?? 0;
  const otherTopTypes = snapshot.assessment_types
    .filter((item) => item.key !== "exit_ticket")
    .slice(0, 3);

  return (
    <section className="plc-assessment-snapshot" aria-label="Aggregate formative-assessment planning snapshot">
      <div className="plc-assessment-snapshot-heading">
        <div>
          <p className="eyebrow">Planning snapshot</p>
          <h5>Daily formative-assessment signals in submitted lesson plans</h5>
        </div>
        <small>Deterministic classification · no assessment text sent to AI</small>
      </div>
      <div className="plc-assessment-metrics">
        <div><strong>{snapshot.daily_assessment_entries}</strong><span>planned daily entries</span></div>
        <div><strong>{exitTicketCount}</strong><span>exit tickets / slips</span></div>
        <div><strong>{snapshot.submitted_course_weeks}</strong><span>course-weeks represented</span></div>
        <div><strong>{snapshot.distinct_teachers}</strong><span>anonymous teachers represented</span></div>
      </div>
      {otherTopTypes.length ? (
        <p className="plc-assessment-type-summary">
          <strong>Other common planned types:</strong>{" "}
          {otherTopTypes.map((item) => `${item.label} (${item.count})`).join(" · ")}
        </p>
      ) : null}
      <p className="plc-assessment-snapshot-note">
        Planning signal only. These counts do not show whether an assessment was administered,
        student results, or teacher effectiveness. Read them alongside course-week coverage.
      </p>
    </section>
  );
}

function SchoolReflectionSummary({ brief }: { brief: SchoolBrief }) {
  return (
    <section className="plc-school-reflection-summary" aria-label="School Reflection Summary">
      <div className="plc-summary-heading">
        <div>
          <p className="eyebrow">School Reflection Summary</p>
          <h5>What teachers are collectively reporting this week</h5>
        </div>
        <small>
          {brief.source_teacher_count} anonymous teacher sources · {brief.source_submission_count} submitted reflections
        </small>
      </div>
      <div className="plc-summary-theme-grid">
        <ThemeList title="Common successes" items={brief.brief.common_successes} />
        <ThemeList title="Common challenges" items={brief.brief.common_challenges} />
        <ThemeList title="Emerging themes" items={brief.brief.emerging_themes} />
      </div>
      <div className="plc-summary-action-grid">
        <SummaryList title="Discussion questions" items={brief.brief.discussion_questions} />
        <SummaryList title="Possible actions" items={brief.brief.possible_actions} />
        <SummaryList title="Support needs" items={brief.brief.support_needs} />
      </div>
    </section>
  );
}

function PlcMeetingGuide({
  brief,
  assessmentSnapshot,
  weekLabel,
}: {
  brief: SchoolBrief;
  assessmentSnapshot: AssessmentPlanningSnapshot | null;
  weekLabel: string;
}) {
  const focus = brief.brief.common_challenges[0]
    ?? brief.brief.emerging_themes[0]
    ?? brief.brief.common_successes[0]
    ?? null;

  return (
    <article className="plc-facilitation-handout" aria-label="Printable PLC meeting guide">
      <header className="plc-artifact-header">
        <p className="eyebrow">Teacher Planning Platform · Reflection Intelligence</p>
        <h4>PLC Meeting Guide — Week of {weekLabel}</h4>
        <p>
          The School Reflection Summary below is the evidence base for this meeting. It is synthesized
          from anonymous teacher-authored submitted reflections and is used for professional learning,
          not teacher evaluation.
        </p>
      </header>

      <SchoolReflectionSummary brief={brief} />

      {focus ? (
        <section className="plc-focus-box">
          <span>Suggested meeting focus</span>
          <strong>{focus.theme}</strong>
          <p>{focus.evidence_summary}</p>
        </section>
      ) : null}

      {assessmentSnapshot ? <AssessmentSnapshot snapshot={assessmentSnapshot} /> : null}

      <section className="plc-artifact-section plc-protocol">
        <h5>40-minute PLC protocol</h5>
        <ol>
          <li><strong>5 min · Orient.</strong> Read the School Reflection Summary and name one aggregate success worth preserving.</li>
          <li><strong>10 min · Examine.</strong> Unpack the suggested focus and clarify what the team is collectively seeing.</li>
          <li><strong>10 min · Exchange.</strong> Share instructional moves, examples, and adaptations connected to the focus.</li>
          <li><strong>10 min · Decide.</strong> Select one practical next-step action and the support needed to try it.</li>
          <li><strong>5 min · Commit.</strong> Decide what evidence the team will bring back and when the focus will be revisited.</li>
        </ol>
      </section>

      <section className="plc-action-workspace" aria-label="Non-persistent PLC action workspace">
        <h5>Team action workspace</h5>
        <div><strong>Action we will try:</strong><span /></div>
        <div><strong>Evidence we will bring back:</strong><span /></div>
        <div><strong>Support or resource needed:</strong><span /></div>
        <div><strong>Revisit date:</strong><span /></div>
        <small>This workspace is for the meeting/printout only. TPP does not store these entries.</small>
      </section>

      <footer className="plc-artifact-footer">
        AI synthesis is limited to the governed anonymous School Reflection Summary. The assessment
        planning snapshot, facilitation protocol, and meeting-guide formatting are deterministic.
        Do not add student-specific information to PLC notes. Use this artifact for professional
        learning, not personnel evaluation, ranking, or comparison.
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
  const [assessmentSnapshot, setAssessmentSnapshot] = useState<AssessmentPlanningSnapshot | null>(null);
  const [assessmentWarning, setAssessmentWarning] = useState("");
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
      setAssessmentSnapshot(null);
      setAssessmentWarning("");
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

  async function generateMeetingGuide() {
    setWorking(true);
    setError("");
    setAssessmentWarning("");
    try {
      const assessmentQuery = new URLSearchParams({
        period_start: weekStart,
        period_end: addDays(weekStart, 6),
      });
      const [briefResult, assessmentResult] = await Promise.allSettled([
        authenticatedFetch(
          `/api/v1/reflection-intelligence/school/${encodeURIComponent(weekStart)}`,
          { method: "POST" },
        ),
        authenticatedFetch(`/api/v1/assessment-analytics/school?${assessmentQuery.toString()}`),
      ]);

      if (briefResult.status === "rejected") {
        throw new Error("The PLC meeting guide could not be generated.");
      }
      const briefResponse = briefResult.value;
      if (!briefResponse.ok) {
        throw new Error(await readError(
          briefResponse,
          "The PLC meeting guide could not be generated.",
        ));
      }
      setBrief(await briefResponse.json() as SchoolBrief);

      if (assessmentResult.status === "fulfilled" && assessmentResult.value.ok) {
        setAssessmentSnapshot(
          await assessmentResult.value.json() as AssessmentPlanningSnapshot,
        );
      } else {
        setAssessmentSnapshot(null);
        setAssessmentWarning(
          "The School Reflection Summary and meeting guide are ready, but the optional formative-assessment planning snapshot is unavailable.",
        );
      }
    } catch (caught) {
      setBrief(null);
      setAssessmentSnapshot(null);
      setAssessmentWarning("");
      setError(caught instanceof Error
        ? caught.message
        : "The PLC meeting guide could not be generated.");
    } finally {
      setWorking(false);
    }
  }

  async function printMeetingGuide() {
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
          <p className="eyebrow">PLC meeting guide</p>
          <h3 id="plc-artifact-title">Move from school reflection patterns to a focused PLC conversation</h3>
          <p className="supporting">
            Generate a one-to-two-page meeting guide that embeds the School Reflection Summary first,
            then adds a suggested focus, an aggregate formative-assessment planning snapshot, a fixed
            40-minute protocol, and a non-persistent team action workspace. The reflection summary is
            the meeting evidence base; the guide is not a generic agenda.
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
              setAssessmentSnapshot(null);
              setAssessmentWarning("");
              setError("");
            }}
          />
        </label>
        <button type="button" className="primary" disabled={working} onClick={() => void generateMeetingGuide()}>
          {working ? "Generating PLC meeting guide…" : "Generate PLC meeting guide"}
        </button>
        {brief ? (
          <button type="button" className="secondary" onClick={() => void printMeetingGuide()}>
            Print PLC meeting guide
          </button>
        ) : null}
      </div>

      <div className="plc-artifact-boundary" role="note">
        <strong>Professional learning only.</strong>{" "}
        The School Reflection Summary uses anonymous teacher source references and requires governed
        aggregate support. It contains no teacher quality score and no student data. The meeting guide
        does not persist team notes.
      </div>

      {assessmentWarning ? (
        <p className="plc-assessment-warning" role="status">{assessmentWarning}</p>
      ) : null}
      {error ? <p className="plc-artifact-error" role="alert">{error}</p> : null}
      {brief ? (
        <PlcMeetingGuide
          brief={brief}
          assessmentSnapshot={assessmentSnapshot}
          weekLabel={weekLabel}
        />
      ) : null}
    </section>,
    portalTarget,
  );
}
