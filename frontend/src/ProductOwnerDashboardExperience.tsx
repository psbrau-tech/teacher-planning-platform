import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import "./product-owner-dashboard.css";

type Identity = {
  id: string;
  display_name: string;
  roles: string[];
};

type Usage = {
  period_start: string;
  period_end: string;
  teachers_authorized: number;
  teachers_authenticated: number;
  teachers_pilot_cohort: number;
  teachers_active: number;
  classes_configured: number;
  shared_curriculum_teachers: number;
  shared_curriculum_classes: number;
  curriculum_excel_saves: number;
  curriculum_excel_teachers: number;
  curriculum_builder_saves: number;
  curriculum_builder_teachers: number;
  curriculum_reuse_events: number;
  curriculum_reuse_teachers: number;
  curriculum_copy_events: number;
  curriculum_copy_teachers: number;
  curriculum_export_events: number;
  curriculum_export_teachers: number;
  weekly_plan_generate_events: number;
  weekly_plan_generate_teachers: number;
  weekly_plans_saved: number;
  weekly_plan_teachers: number;
  ai_requests: number;
  ai_teachers: number;
  ai_fields_accepted: number;
  ai_fields_edited: number;
  ai_fields_rejected: number;
  lesson_plan_pdf_views: number;
  lesson_plan_pdf_view_teachers: number;
  lesson_plan_submissions: number;
  lesson_plan_submission_teachers: number;
  completed_packet_submissions: number;
  completed_packet_teachers: number;
  completed_packet_views: number;
  completed_packet_view_teachers: number;
  pilot_feedback_responses: number;
};

type PeriodKind = "pilot" | "current_week" | "last_4_weeks" | "custom";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const ownerSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

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

function Metric({
  value,
  label,
  detail,
}: {
  value: string | number;
  label: string;
  detail?: string;
}) {
  return (
    <div className="owner-metric">
      <strong>{value}</strong>
      <span>{label}</span>
      {detail && <small>{detail}</small>}
    </div>
  );
}

function UsageRow({
  label,
  teachers,
  events,
  note,
}: {
  label: string;
  teachers: number;
  events: number;
  note?: string;
}) {
  return (
    <div className="owner-usage-row">
      <div><strong>{label}</strong>{note && <small>{note}</small>}</div>
      <span><strong>{teachers}</strong> teacher{teachers === 1 ? "" : "s"}</span>
      <span><strong>{events}</strong> use{events === 1 ? "" : "s"}</span>
    </div>
  );
}

export function ProductOwnerDashboardExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [open, setOpen] = useState(false);
  const [periodKind, setPeriodKind] = useState<PeriodKind>("pilot");
  const [customStart, setCustomStart] = useState("2026-08-06");
  const [customEnd, setCustomEnd] = useState(localIsoDate());
  const [usage, setUsage] = useState<Usage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isPlatformAdmin = identity?.roles.includes("platform_admin") ?? false;
  const today = localIsoDate();
  const currentMonday = mondayFor();
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
    return { start: "2026-08-06", end: today, label: "Pilot to date" };
  }, [currentMonday, customEnd, customStart, periodKind, today]);

  useEffect(() => {
    if (!ownerSupabase) return;
    void ownerSupabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      if (data.session) void loadIdentity(data.session);
    });
    const { data } = ownerSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setUsage(null);
      setOpen(false);
      if (nextSession) void loadIdentity(nextSession);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  async function loadIdentity(activeSession: Session) {
    const response = await fetch("/api/v1/session", {
      headers: { Authorization: `Bearer ${activeSession.access_token}` },
    });
    if (!response.ok) return;
    setIdentity(await response.json() as Identity);
  }

  async function loadUsage() {
    if (!session?.access_token || !isPlatformAdmin || !period.start || !period.end) return;
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ period_start: period.start, period_end: period.end });
      const response = await fetch(`/api/v1/product-owner/usage?${query.toString()}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!response.ok) {
        throw new Error(await readError(response, "Product usage could not be loaded."));
      }
      setUsage(await response.json() as Usage);
    } catch (caught) {
      setUsage(null);
      setError(caught instanceof Error ? caught.message : "Product usage could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (open && isPlatformAdmin) void loadUsage();
  }, [open, isPlatformAdmin, period.start, period.end]);

  const signals = useMemo(() => {
    if (!usage) return [] as string[];
    const items: string[] = [];

    items.push(
      `${usage.teachers_pilot_cohort} authenticated teacher${usage.teachers_pilot_cohort === 1 ? " is" : "s are"} in the pre-rollout Pilot cohort; ${usage.teachers_active} teacher${usage.teachers_active === 1 ? " showed" : "s showed"} measurable TPP activity in this selected period.`,
    );

    if (usage.teachers_authorized > usage.teachers_authenticated) {
      items.push(
        `${usage.teachers_authenticated} of ${usage.teachers_authorized} currently authorized teacher accounts have authenticated. Authorized access may include staff who have not yet been asked to begin using TPP.`,
      );
    }

    const pathways = [
      { label: "Excel pacing", teachers: usage.curriculum_excel_teachers },
      { label: "Build in TPP", teachers: usage.curriculum_builder_teachers },
      { label: "Reuse curriculum", teachers: usage.curriculum_reuse_teachers },
    ].sort((a, b) => b.teachers - a.teachers);
    if (pathways[0]?.teachers) {
      items.push(
        `${pathways[0].label} is the most-used measured curriculum setup pathway `
        + `(${pathways[0].teachers} teachers).`,
      );
    }

    const decisions = usage.ai_fields_accepted + usage.ai_fields_edited + usage.ai_fields_rejected;
    if (decisions) {
      const editedPct = Math.round((usage.ai_fields_edited / decisions) * 100);
      items.push(
        `${editedPct}% of recorded AI field decisions were edited before use; `
        + "accepted, edited, and rejected decisions remain teacher-controlled.",
      );
    }

    if (usage.shared_curriculum_teachers) {
      items.push(
        `${usage.shared_curriculum_teachers} teacher${usage.shared_curriculum_teachers === 1 ? " is" : "s are"} `
        + "currently reusing the same curriculum across multiple active classes.",
      );
    }

    if (usage.teachers_active && usage.completed_packet_teachers < usage.teachers_active) {
      const gap = usage.teachers_active - usage.completed_packet_teachers;
      items.push(
        `${gap} active teacher${gap === 1 ? " has" : "s have"} activity but no completed packet `
        + "in this selected period. That may reflect an in-progress week or an incomplete closeout.",
      );
    }
    return items;
  }, [usage]);

  if (!ownerSupabase || !session || !isPlatformAdmin) return null;

  return (
    <>
      <button type="button" className="product-owner-launcher" onClick={() => setOpen(true)}>
        Product Owner
      </button>

      {open && (
        <div className="product-owner-backdrop" role="presentation">
          <section
            className="product-owner-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="product-owner-title"
          >
            <div className="product-owner-heading">
              <div>
                <p className="eyebrow">Platform Owner</p>
                <h2 id="product-owner-title">Product usage</h2>
                <p>
                  See what teachers are actually using so product decisions follow evidence rather
                  than assumptions.
                </p>
              </div>
              <button type="button" className="secondary" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>

            <div className="owner-period-control">
              <label>
                Reporting period
                <select
                  value={periodKind}
                  onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}
                >
                  <option value="pilot">Pilot to date</option>
                  <option value="current_week">Current week</option>
                  <option value="last_4_weeks">Last 4 weeks</option>
                  <option value="custom">Custom dates</option>
                </select>
              </label>
              {periodKind === "custom" && (
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
              )}
              <button
                type="button"
                className="secondary"
                disabled={loading}
                onClick={() => void loadUsage()}
              >
                Refresh
              </button>
              <span className="owner-period-label">
                {period.label}: {period.start} through {period.end}
              </span>
            </div>

            <div className="owner-telemetry-note" role="note">
              <strong>Interpretation note.</strong> Plan, AI, and submission counts use existing
              authoritative TPP records. Curriculum-pathway and PDF-view interaction telemetry
              begins when this release is deployed, so earlier zeros do not mean a feature was
              never used. Authorized access can include staff who are not yet in the active rollout.
            </div>

            {error && <p className="error-message" role="alert">{error}</p>}
            {loading && (
              <p className="working-status" role="status">Updating Product Owner usage…</p>
            )}

            {usage && !loading && (
              <>
                <section className="owner-section owner-onboarding">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">Onboarding and Pilot scope</p>
                      <h3>Authorized → authenticated → active</h3>
                    </div>
                  </div>
                  <div className="owner-summary-grid" aria-label="Product adoption summary">
                    <Metric value={usage.teachers_authorized} label="authorized teachers" />
                    <Metric value={usage.teachers_authenticated} label="authenticated teachers" />
                    <Metric value={usage.teachers_pilot_cohort} label="pre-rollout Pilot cohort" />
                    <Metric value={usage.teachers_active} label="active in selected period" />
                  </div>
                  <div className="owner-summary-grid compact-grid">
                    <Metric value={usage.classes_configured} label="active classes configured" />
                  </div>
                </section>

                <section className="owner-section">
                  <div className="section-heading compact">
                    <div><p className="eyebrow">Course Setup</p><h3>How teachers are starting</h3></div>
                  </div>
                  <div className="owner-usage-table">
                    <UsageRow
                      label="Excel pacing"
                      teachers={usage.curriculum_excel_teachers}
                      events={usage.curriculum_excel_saves}
                      note="successful curriculum saves after Upload Excel"
                    />
                    <UsageRow
                      label="Build in TPP"
                      teachers={usage.curriculum_builder_teachers}
                      events={usage.curriculum_builder_saves}
                      note="successful curriculum saves after Build in TPP"
                    />
                    <UsageRow
                      label="Reuse mine"
                      teachers={usage.curriculum_reuse_teachers}
                      events={usage.curriculum_reuse_events}
                    />
                    <UsageRow
                      label="Create curriculum copy"
                      teachers={usage.curriculum_copy_teachers}
                      events={usage.curriculum_copy_events}
                    />
                    <UsageRow
                      label="Download current curriculum"
                      teachers={usage.curriculum_export_teachers}
                      events={usage.curriculum_export_events}
                    />
                  </div>
                  <div className="owner-summary-grid compact-grid">
                    <Metric
                      value={usage.shared_curriculum_teachers}
                      label="teachers sharing curriculum"
                      detail={`${usage.shared_curriculum_classes} classes on shared sequences`}
                    />
                  </div>
                </section>

                <section className="owner-section">
                  <div className="section-heading compact">
                    <div><p className="eyebrow">Weekly Planning</p><h3>Planning behavior</h3></div>
                  </div>
                  <div className="owner-summary-grid compact-grid">
                    <Metric
                      value={usage.weekly_plans_saved}
                      label="weekly plans saved"
                      detail={`${usage.weekly_plan_teachers} teachers`}
                    />
                    <Metric
                      value={usage.weekly_plan_generate_events}
                      label="Build / reconcile uses"
                      detail={`${usage.weekly_plan_generate_teachers} teachers`}
                    />
                    <Metric
                      value={usage.ai_requests}
                      label="successful AI requests"
                      detail={`${usage.ai_teachers} teachers`}
                    />
                    <Metric
                      value={usage.lesson_plan_submissions}
                      label="lesson-plan submissions"
                      detail={`${usage.lesson_plan_submission_teachers} teachers`}
                    />
                    <Metric
                      value={usage.lesson_plan_pdf_views}
                      label="lesson-plan PDF views"
                      detail={`${usage.lesson_plan_pdf_view_teachers} teachers`}
                    />
                  </div>
                  <div className="owner-ai-decisions">
                    <span><strong>{usage.ai_fields_accepted}</strong> AI fields accepted</span>
                    <span><strong>{usage.ai_fields_edited}</strong> edited before use</span>
                    <span><strong>{usage.ai_fields_rejected}</strong> rejected</span>
                  </div>
                </section>

                <section className="owner-section">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">Friday Closeout</p>
                      <h3>Did the weekly loop get completed?</h3>
                    </div>
                  </div>
                  <div className="owner-summary-grid compact-grid">
                    <Metric
                      value={usage.completed_packet_submissions}
                      label="completed packets submitted"
                      detail={`${usage.completed_packet_teachers} teachers`}
                    />
                    <Metric
                      value={usage.completed_packet_views}
                      label="completed packet views"
                      detail={`${usage.completed_packet_view_teachers} teachers`}
                    />
                    <Metric value={usage.pilot_feedback_responses} label="Pilot survey responses" />
                  </div>
                </section>

                <section className="owner-section owner-signals">
                  <div className="section-heading compact">
                    <div>
                      <p className="eyebrow">Product signals</p>
                      <h3>What deserves attention</h3>
                      <p className="supporting">
                        These are descriptive product signals, not teacher-performance judgments.
                      </p>
                    </div>
                  </div>
                  {signals.map((signal) => (
                    <div className="owner-signal" key={signal}>{signal}</div>
                  ))}
                </section>
              </>
            )}
          </section>
        </div>
      )}
    </>
  );
}
