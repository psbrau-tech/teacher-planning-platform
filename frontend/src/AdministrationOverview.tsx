import { useEffect, useMemo, useState } from "react";
import { AdminSubmissionPanel } from "./AdminSubmissionPanel";
import { BaselineBarChart } from "./BaselineBarChart";
import { PilotFeedbackResultsPanel } from "./PilotFeedbackResultsPanel";
import { ProductOwnerDashboardExperience } from "./ProductOwnerDashboardExperience";
import { StandardsAdministrationPanel } from "./StandardsAdministrationPanel";
import "./owner-overview.css";

type AdminUsage = {
  school_id: string;
  teachers_configured: number;
  teachers_with_assignments: number;
  assignments_configured: number;
  weekly_plans_created: number;
  weekly_plans_approved: number;
  instruction_records_validated: number;
  lessons_carried_forward: number;
  documents_requested: number;
  documents_generated: number;
  document_generation_failures: number;
  data_boundary: string;
};

type AdminCost = {
  school_id: string;
  usage_month: string;
  request_count: number;
  successful_requests: number;
  failed_requests: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  estimated_cost_usd: string;
  accepted_outputs: number;
  discarded_outputs: number;
};

type BaselineResult = {
  id: string;
  survey_key: string;
  school_id: string;
  school_name: string;
  planning_time_before: string;
  plan_usefulness_before: number;
  submission_burden_before: number;
  reflection_review_frequency_before: string;
  plc_use_frequency_before: string;
  biggest_burden_before: string;
  submitted_at: string;
};

type PeriodKind = "current_week" | "last_4_weeks" | "grading_period" | "custom";
type AdminTab = "administration" | "owner";
type Props = { accessToken: string; roles: string[]; disabled?: boolean };

type BaselineSchoolSummary = {
  schoolId: string;
  schoolName: string;
  responses: BaselineResult[];
  averageUsefulness: number;
  averageBurden: number;
  averageReflectionReview: number;
  averagePlcUse: number;
  mostCommonTime: string;
};

const TIME_LABELS: Record<string, string> = {
  under_30: "Less than 30 minutes",
  "30_60": "30–60 minutes",
  "61_90": "61–90 minutes",
  "91_120": "91–120 minutes",
  "61_120": "61–120 minutes",
  "121_180": "121–180 minutes",
  over_180: "More than 3 hours",
  not_sure: "Not sure",
};

const FREQUENCY_SCORE: Record<string, number> = {
  never: 1,
  rarely: 2,
  sometimes: 3,
  often: 4,
  very_often: 5,
};

function mondayFor(dateValue = new Date()): string {
  const date = new Date(dateValue);
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    return typeof body.detail === "string" && body.detail.trim() ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

function storedGradingPeriod(): { start: string; end: string } {
  try {
    const value = window.localStorage.getItem("tpp:current-grading-period");
    if (!value) return { start: "", end: "" };
    const parsed = JSON.parse(value) as { start?: unknown; end?: unknown };
    return {
      start: typeof parsed.start === "string" ? parsed.start : "",
      end: typeof parsed.end === "string" ? parsed.end : "",
    };
  } catch {
    return { start: "", end: "" };
  }
}

function mostCommon(values: string[]): string {
  if (!values.length) return "No responses yet";
  const counts = new Map<string, number>();
  values.forEach((value) => counts.set(value, (counts.get(value) ?? 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? values[0];
}

function averageFrequency(values: string[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + (FREQUENCY_SCORE[value] ?? 0), 0) / values.length;
}

function buildBaselineSummaries(results: BaselineResult[]): BaselineSchoolSummary[] {
  const grouped = new Map<string, BaselineResult[]>();
  results.forEach((result) => grouped.set(
    result.school_id,
    [...(grouped.get(result.school_id) ?? []), result],
  ));
  return [...grouped.entries()].map(([schoolId, responses]) => {
    const averageUsefulness = responses.reduce((sum, item) => sum + item.plan_usefulness_before, 0) / responses.length;
    const averageBurden = responses.reduce((sum, item) => sum + item.submission_burden_before, 0) / responses.length;
    const averageReflectionReview = averageFrequency(responses.map((item) => item.reflection_review_frequency_before));
    const averagePlcUse = averageFrequency(responses.map((item) => item.plc_use_frequency_before));
    const mostCommonTimeKey = mostCommon(responses.map((item) => item.planning_time_before));
    return {
      schoolId,
      schoolName: responses[0]?.school_name ?? "School",
      responses,
      averageUsefulness,
      averageBurden,
      averageReflectionReview,
      averagePlcUse,
      mostCommonTime: TIME_LABELS[mostCommonTimeKey] ?? mostCommonTimeKey,
    };
  }).sort((a, b) => a.schoolName.localeCompare(b.schoolName));
}

export function AdministrationOverview({ accessToken, roles, disabled = false }: Props) {
  const currentMonday = mondayFor();
  const savedGradingPeriod = storedGradingPeriod();
  const [activeTab, setActiveTab] = useState<AdminTab>("administration");
  const [periodKind, setPeriodKind] = useState<PeriodKind>("current_week");
  const [customStart, setCustomStart] = useState(currentMonday);
  const [customEnd, setCustomEnd] = useState(addDays(currentMonday, 6));
  const [gradingStart, setGradingStart] = useState(savedGradingPeriod.start);
  const [gradingEnd, setGradingEnd] = useState(savedGradingPeriod.end);
  const [usage, setUsage] = useState<AdminUsage | null>(null);
  const [costs, setCosts] = useState<AdminCost[]>([]);
  const [baselineResults, setBaselineResults] = useState<BaselineResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [ownerLoading, setOwnerLoading] = useState(false);
  const [error, setError] = useState("");
  const [ownerError, setOwnerError] = useState("");
  const isPlatformAdmin = roles.includes("platform_admin");

  const period = useMemo(() => {
    if (periodKind === "current_week") return { start: currentMonday, end: addDays(currentMonday, 6), label: "Current week" };
    if (periodKind === "last_4_weeks") return { start: addDays(currentMonday, -21), end: addDays(currentMonday, 6), label: "Last 4 weeks" };
    if (periodKind === "grading_period") return { start: gradingStart, end: gradingEnd, label: "Current grading period" };
    return { start: customStart, end: customEnd, label: "Custom dates" };
  }, [currentMonday, customEnd, customStart, gradingEnd, gradingStart, periodKind]);

  const baselineSummaries = useMemo(() => buildBaselineSummaries(baselineResults), [baselineResults]);

  async function loadUsage() {
    if (!period.start || !period.end) {
      setUsage(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const query = new URLSearchParams({ period_start: period.start, period_end: period.end });
      const response = await fetch(`/api/v1/administration/usage?${query.toString()}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error(await readError(response, "Administration reporting could not be loaded."));
      setUsage(await response.json() as AdminUsage);
    } catch (caught) {
      setUsage(null);
      setError(caught instanceof Error ? caught.message : "Administration reporting could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function loadOwnerReporting() {
    if (!isPlatformAdmin) return;
    setOwnerLoading(true);
    setOwnerError("");
    try {
      const [costResponse, baselineResponse] = await Promise.all([
        fetch("/api/v1/administration/costs", { headers: { Authorization: `Bearer ${accessToken}` } }),
        fetch("/api/v1/baseline/results", { headers: { Authorization: `Bearer ${accessToken}` } }),
      ]);
      if (!costResponse.ok) throw new Error(await readError(costResponse, "Cost reporting could not be loaded."));
      if (!baselineResponse.ok) throw new Error(await readError(baselineResponse, "Baseline reporting could not be loaded."));
      setCosts(await costResponse.json() as AdminCost[]);
      setBaselineResults(await baselineResponse.json() as BaselineResult[]);
    } catch (caught) {
      setOwnerError(caught instanceof Error ? caught.message : "Owner reporting could not be loaded.");
    } finally {
      setOwnerLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === "administration") void loadUsage();
  }, [accessToken, activeTab, period.start, period.end]);

  useEffect(() => {
    if (activeTab === "owner" && isPlatformAdmin) void loadOwnerReporting();
  }, [accessToken, activeTab, isPlatformAdmin]);

  useEffect(() => {
    if (!isPlatformAdmin && activeTab === "owner") setActiveTab("administration");
  }, [activeTab, isPlatformAdmin]);

  function saveGradingPeriod() {
    if (!gradingStart || !gradingEnd || gradingEnd < gradingStart) {
      setError("Enter the district grading-period start and end dates before using this reporting period.");
      return;
    }
    window.localStorage.setItem("tpp:current-grading-period", JSON.stringify({ start: gradingStart, end: gradingEnd }));
    setError("");
    void loadUsage();
  }

  return (
    <section className="panel administration-overview">
      <div className="administration-tabs" role="tablist" aria-label="Administration views">
        <button type="button" role="tab" aria-selected={activeTab === "administration"} className={activeTab === "administration" ? "active" : ""} onClick={() => setActiveTab("administration")}>Administration</button>
        {isPlatformAdmin && <button type="button" role="tab" aria-selected={activeTab === "owner"} className={activeTab === "owner" ? "active" : ""} onClick={() => setActiveTab("owner")}>Owner</button>}
      </div>

      {activeTab === "administration" && (
        <div role="tabpanel" aria-label="Administration reporting">
          <div className="section-heading compact"><div><p className="eyebrow">Governed reporting</p><h2>Administration</h2><p className="supporting">Professional educator planning operations only.</p></div></div>
          <div className="report-period-control">
            <label>Reporting period<select value={periodKind} disabled={disabled || loading} onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}><option value="current_week">Current week</option><option value="last_4_weeks">Last 4 weeks</option><option value="grading_period">Current grading period</option><option value="custom">Custom dates</option></select></label>
            {periodKind === "custom" && <><label>Start<input type="date" value={customStart} onChange={(event) => setCustomStart(event.target.value)} /></label><label>End<input type="date" value={customEnd} onChange={(event) => setCustomEnd(event.target.value)} /></label></>}
            {periodKind === "grading_period" && <><label>Grading period start<input type="date" value={gradingStart} onChange={(event) => setGradingStart(event.target.value)} /></label><label>Grading period end<input type="date" value={gradingEnd} onChange={(event) => setGradingEnd(event.target.value)} /></label><button type="button" className="secondary" onClick={saveGradingPeriod}>Save grading-period dates</button></>}
            <div className="guidance-card compact-guidance period-summary"><strong>{period.label}</strong><p>{period.start && period.end ? `${period.start} through ${period.end}` : "Enter the district's actual grading-period dates."}</p></div>
          </div>
          {periodKind === "grading_period" && (!gradingStart || !gradingEnd) && <p className="guidance-text">TPP does not currently store district grading-period boundaries. Enter the district's actual dates once; this browser will remember them until a governed calendar configuration is added.</p>}
          {error && <p className="error-message" role="alert">{error}</p>}
          {loading && <p className="working-status" role="status"><span className="button-spinner" aria-hidden="true" /> Updating reporting period…</p>}
          {usage ? <><section className="summary" aria-label="School planning usage"><div><strong>{usage.teachers_configured}</strong><span>teachers configured</span></div><div><strong>{usage.teachers_with_assignments}</strong><span>teachers with courses</span></div><div><strong>{usage.assignments_configured}</strong><span>courses configured</span></div><div><strong>{usage.weekly_plans_created}</strong><span>weekly plans in period</span></div></section><div className="grid admin-activity-grid"><article className="card"><h3>Weekly validation</h3><p>{usage.weekly_plans_approved} submitted plans</p><p>{usage.instruction_records_validated} instruction records validated</p><p>{usage.lessons_carried_forward} lessons carried forward</p></article><article className="card"><h3>Document generation</h3><p>{usage.documents_requested} requested</p><p>{usage.documents_generated} generated</p><p>{usage.document_generation_failures} failures</p></article></div></> : !loading && period.start && period.end ? <div className="empty-state"><p>Reporting is unavailable for this period.</p></div> : null}
          <AdminSubmissionPanel accessToken={accessToken} roles={roles} disabled={disabled || loading} />
        </div>
      )}

      {activeTab === "owner" && isPlatformAdmin && (
        <div className="owner-tab" role="tabpanel" aria-label="Platform Owner reporting">
          <div className="section-heading compact"><div><p className="eyebrow">Platform Owner</p><h2>Owner</h2><p className="supporting">Product adoption, Pilot learning, baseline evidence, governed standards operations, and AI cost reporting in one place.</p></div><button type="button" className="secondary" disabled={ownerLoading} onClick={() => void loadOwnerReporting()}>{ownerLoading ? "Refreshing…" : "Refresh owner data"}</button></div>
          {ownerError && <p className="error-message" role="alert">{ownerError}</p>}

          <section className="owner-section">
            <div className="section-heading compact"><div><p className="eyebrow">Product and Pilot intelligence</p><h3>Usage and teacher feedback</h3><p className="supporting">These are product-learning tools, not teacher-performance measures.</p></div></div>
            <div className="grid owner-tool-grid"><article className="card owner-tool-card"><p className="eyebrow">Product adoption</p><h3>Product usage</h3><p>See what teachers are actually using, where adoption is growing, and where the product may be creating friction.</p><ProductOwnerDashboardExperience /></article><PilotFeedbackResultsPanel accessToken={accessToken} disabled={disabled || ownerLoading} /></div>
          </section>

          <section className="owner-section">
            <div className="section-heading compact"><div><p className="eyebrow">Pre-TPP baseline</p><h3>What planning looked like before TPP</h3><p className="supporting">Responses are intentionally reported without teacher identity. They provide a comparison point for later workload and value measures.</p></div></div>
            {ownerLoading && baselineResults.length === 0 ? <p className="working-status" role="status">Loading teacher baseline…</p> : baselineSummaries.length === 0 ? <div className="empty-state"><p>No teacher baseline responses have been submitted yet.</p></div> : (
              <div className="baseline-owner-schools">
                {baselineSummaries.map((summary) => (
                  <article className="card baseline-owner-school" key={summary.schoolId}>
                    <div className="card-row"><div><p className="eyebrow">School baseline</p><h3>{summary.schoolName}</h3></div><span className="badge">{summary.responses.length} response{summary.responses.length === 1 ? "" : "s"}</span></div>
                    <div className="owner-summary-grid">
                      <div className="owner-metric"><strong>{summary.mostCommonTime}</strong><span>most common pre-TPP planning time</span></div>
                      <div className="owner-metric"><strong>{summary.averageUsefulness.toFixed(1)}/5</strong><span>average plan usefulness</span></div>
                      <div className="owner-metric"><strong>{summary.averageBurden.toFixed(1)}/5</strong><span>average submission burden</span></div>
                      <div className="owner-metric"><strong>{summary.averageReflectionReview.toFixed(1)}/5</strong><span>average frequency of revisiting reflections</span></div>
                      <div className="owner-metric"><strong>{summary.averagePlcUse.toFixed(1)}/5</strong><span>average frequency of using plans or reflections in PLC/faculty discussion</span></div>
                    </div>
                    <BaselineBarChart responses={summary.responses} />
                    {summary.responses.some((item) => item.biggest_burden_before) && <div className="baseline-owner-comments"><strong>Optional pre-TPP burden comments</strong>{summary.responses.filter((item) => item.biggest_burden_before).map((item) => <p key={item.id}>{item.biggest_burden_before}</p>)}</div>}
                  </article>
                ))}
              </div>
            )}
          </section>

          <StandardsAdministrationPanel accessToken={accessToken} disabled={disabled || ownerLoading} />

          <section className="owner-section">
            <div className="section-heading compact"><div><p className="eyebrow">Platform Owner</p><h3>AI cost reporting</h3><p className="supporting">Operational AI usage and estimated cost. A failed request means the planning request did not return a usable governed result; this summary does not infer the technical cause.</p></div></div>
            {costs.length === 0 ? <div className="empty-state"><p>No AI usage has been recorded.</p></div> : <div className="grid">{costs.map((cost) => <article className="card" key={`${cost.school_id}-${cost.usage_month}`}><span className="badge">{cost.usage_month.slice(0, 7)}</span><h3>${cost.estimated_cost_usd}</h3><p>{cost.request_count} requests · {cost.successful_requests} successful · {cost.failed_requests} failed</p><small>{cost.input_tokens} input · {cost.output_tokens} output · {cost.cached_tokens} cached tokens</small></article>)}</div>}
          </section>
        </div>
      )}
    </section>
  );
}
