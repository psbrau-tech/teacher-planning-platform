import { useEffect, useMemo, useState } from "react";
import { AdminSubmissionPanel } from "./AdminSubmissionPanel";
import { StandardsAdministrationPanel } from "./StandardsAdministrationPanel";

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

type PeriodKind = "current_week" | "last_4_weeks" | "grading_period" | "custom";

type Props = {
  accessToken: string;
  roles: string[];
  disabled?: boolean;
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

export function AdministrationOverview({ accessToken, roles, disabled = false }: Props) {
  const currentMonday = mondayFor();
  const savedGradingPeriod = storedGradingPeriod();
  const [periodKind, setPeriodKind] = useState<PeriodKind>("current_week");
  const [customStart, setCustomStart] = useState(currentMonday);
  const [customEnd, setCustomEnd] = useState(addDays(currentMonday, 6));
  const [gradingStart, setGradingStart] = useState(savedGradingPeriod.start);
  const [gradingEnd, setGradingEnd] = useState(savedGradingPeriod.end);
  const [usage, setUsage] = useState<AdminUsage | null>(null);
  const [costs, setCosts] = useState<AdminCost[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isPlatformAdmin = roles.includes("platform_admin");

  const period = useMemo(() => {
    if (periodKind === "current_week") return { start: currentMonday, end: addDays(currentMonday, 6), label: "Current week" };
    if (periodKind === "last_4_weeks") return { start: addDays(currentMonday, -21), end: addDays(currentMonday, 6), label: "Last 4 weeks" };
    if (periodKind === "grading_period") return { start: gradingStart, end: gradingEnd, label: "Current grading period" };
    return { start: customStart, end: customEnd, label: "Custom dates" };
  }, [currentMonday, customEnd, customStart, gradingEnd, gradingStart, periodKind]);

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

  async function loadCosts() {
    if (!isPlatformAdmin) return;
    try {
      const response = await fetch("/api/v1/administration/costs", { headers: { Authorization: `Bearer ${accessToken}` } });
      if (!response.ok) throw new Error(await readError(response, "Cost reporting could not be loaded."));
      setCosts(await response.json() as AdminCost[]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Cost reporting could not be loaded.");
    }
  }

  useEffect(() => { void loadUsage(); }, [accessToken, period.start, period.end]);
  useEffect(() => { void loadCosts(); }, [accessToken, isPlatformAdmin]);

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
      <div className="section-heading compact"><div><p className="eyebrow">Governed reporting</p><h2>Administration</h2><p className="supporting">Professional educator planning operations only.</p></div></div>

      <div className="report-period-control">
        <label>Reporting period
          <select value={periodKind} disabled={disabled || loading} onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}>
            <option value="current_week">Current week</option>
            <option value="last_4_weeks">Last 4 weeks</option>
            <option value="grading_period">Current grading period</option>
            <option value="custom">Custom dates</option>
          </select>
        </label>
        {periodKind === "custom" && <><label>Start<input type="date" value={customStart} onChange={(event) => setCustomStart(event.target.value)} /></label><label>End<input type="date" value={customEnd} onChange={(event) => setCustomEnd(event.target.value)} /></label></>}
        {periodKind === "grading_period" && <><label>Grading period start<input type="date" value={gradingStart} onChange={(event) => setGradingStart(event.target.value)} /></label><label>Grading period end<input type="date" value={gradingEnd} onChange={(event) => setGradingEnd(event.target.value)} /></label><button type="button" className="secondary" onClick={saveGradingPeriod}>Save grading-period dates</button></>}
        <div className="guidance-card compact-guidance"><strong>{period.label}</strong><p>{period.start && period.end ? `${period.start} through ${period.end}` : "Enter the district's actual grading-period dates."}</p></div>
      </div>
      {periodKind === "grading_period" && (!gradingStart || !gradingEnd) && <p className="guidance-text">TPP does not currently store district grading-period boundaries. Enter the district's actual dates once; this browser will remember them until a governed calendar configuration is added.</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {loading && <p className="working-status"><span className="button-spinner" aria-hidden="true" /> Updating reporting period…</p>}

      {usage ? <>
        <section className="summary" aria-label="School planning usage"><div><strong>{usage.teachers_configured}</strong><span>teachers configured</span></div><div><strong>{usage.teachers_with_assignments}</strong><span>teachers with courses</span></div><div><strong>{usage.assignments_configured}</strong><span>courses configured</span></div><div><strong>{usage.weekly_plans_created}</strong><span>weekly plans in period</span></div></section>
        <div className="grid"><article className="card"><h3>Weekly validation</h3><p>{usage.weekly_plans_approved} submitted plans</p><p>{usage.instruction_records_validated} instruction records validated</p><p>{usage.lessons_carried_forward} lessons carried forward</p></article><article className="card"><h3>Document generation</h3><p>{usage.documents_requested} requested</p><p>{usage.documents_generated} generated</p><p>{usage.document_generation_failures} failures</p></article><article className="card"><h3>Access boundary</h3><p>{roles.join(" · ")}</p><p>{usage.data_boundary}</p><p>Professional educator operations only</p></article></div>
      </> : !loading && period.start && period.end ? <div className="empty-state"><p>Reporting is unavailable for this period.</p></div> : null}

      <AdminSubmissionPanel accessToken={accessToken} roles={roles} disabled={disabled || loading} />

      {isPlatformAdmin && <>
        <StandardsAdministrationPanel accessToken={accessToken} disabled={disabled || loading} />
        <section>
          <div className="section-heading compact"><div><p className="eyebrow">Platform Owner</p><h2>AI cost reporting</h2><p className="supporting">Operational AI usage and estimated cost. A failed request means the planning request did not return a usable governed result; this summary does not infer the technical cause.</p></div></div>
          {costs.length === 0 ? <div className="empty-state"><p>No AI usage has been recorded.</p></div> : <div className="grid">{costs.map((cost) => <article className="card" key={`${cost.school_id}-${cost.usage_month}`}><span className="badge">{cost.usage_month.slice(0, 7)}</span><h3>${cost.estimated_cost_usd}</h3><p>{cost.request_count} requests · {cost.successful_requests} successful · {cost.failed_requests} failed</p><small>{cost.input_tokens} input · {cost.output_tokens} output · {cost.cached_tokens} cached tokens</small></article>)}</div>}
        </section>
      </>}
    </section>
  );
}