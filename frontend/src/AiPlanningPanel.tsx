import { useCallback, useEffect, useMemo, useState } from "react";

export type PlanningFieldKey =
  | "unit_topic" | "literacy_standards" | "act_preparation" | "learning_targets"
  | "know" | "understand" | "do_statement" | "activities" | "assessments" | "resources"
  | "monday" | "tuesday" | "wednesday" | "thursday" | "friday"
  | "plds" | "misconceptions" | "formative" | "summative" | "performance_task"
  | "clt_mon" | "clt_tue" | "clt_wed" | "clt_thu" | "clt_fri"
  | "rrt_mon" | "rrt_tue" | "rrt_wed" | "rrt_thu" | "rrt_fri"
  | "cfu_mon" | "cfu_tue" | "cfu_wed" | "cfu_thu" | "cfu_fri"
  | "ri_mon" | "ri_tue" | "ri_wed" | "ri_thu" | "ri_fri"
  | "sic_mon" | "sic_tue" | "sic_wed" | "sic_thu" | "sic_fri"
  | "esl_mon" | "esl_tue" | "esl_wed" | "esl_thu" | "esl_fri";

export type CurrentPlanningFields = Partial<Record<PlanningFieldKey, string>>;
type SuggestionSet = Record<PlanningFieldKey, string> & { alignment_summary: string };
type SuggestionResponse = { usage_event_id: string; model: string; estimated_cost_usd: string; suggestions: SuggestionSet };
type RawSuggestionResponse = { usage_event_id: string; model: string; estimated_cost_usd: string; suggestions: Record<string, string> };
type FieldDecision = "accepted" | "edited" | "rejected";

type AiPlanningPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  currentFields: CurrentPlanningFields;
  hasScheduledLessons: boolean;
  hasSavedStandards: boolean;
  onApplyField: (field: PlanningFieldKey, value: string) => void;
};

const BASE_FIELDS: PlanningFieldKey[] = [
  "unit_topic", "literacy_standards", "act_preparation", "learning_targets", "know", "understand",
  "do_statement", "activities", "assessments", "resources", "monday", "tuesday", "wednesday",
  "thursday", "friday",
];
const DISTRICT_FIELDS: PlanningFieldKey[] = [
  "plds", "misconceptions", "formative", "summative", "performance_task",
  "clt_mon", "clt_tue", "clt_wed", "clt_thu", "clt_fri",
  "rrt_mon", "rrt_tue", "rrt_wed", "rrt_thu", "rrt_fri",
  "cfu_mon", "cfu_tue", "cfu_wed", "cfu_thu", "cfu_fri",
  "ri_mon", "ri_tue", "ri_wed", "ri_thu", "ri_fri",
  "sic_mon", "sic_tue", "sic_wed", "sic_thu", "sic_fri",
  "esl_mon", "esl_tue", "esl_wed", "esl_thu", "esl_fri",
];
const BASE_FIELD_SET = new Set<PlanningFieldKey>(BASE_FIELDS);

const FIELD_LABELS: Record<PlanningFieldKey, string> = {
  unit_topic: "Unit / topic", literacy_standards: "Literacy Standards", act_preparation: "ACT Preparation",
  learning_targets: "Learning targets", know: "Know", understand: "Understand", do_statement: "Do",
  activities: "Activities", assessments: "Assessments", resources: "Resources", monday: "Monday",
  tuesday: "Tuesday", wednesday: "Wednesday", thursday: "Thursday", friday: "Friday",
  plds: "Performance-Level Descriptors / Proficiency Scale", misconceptions: "Likely Misconceptions",
  formative: "Formative Assessments", summative: "Summative Assessments",
  performance_task: "Performance Task / Authentic Application",
  clt_mon: "Monday — Clear learning target & success criteria", clt_tue: "Tuesday — Clear learning target & success criteria",
  clt_wed: "Wednesday — Clear learning target & success criteria", clt_thu: "Thursday — Clear learning target & success criteria",
  clt_fri: "Friday — Clear learning target & success criteria",
  rrt_mon: "Monday — Rigorous & relevant task", rrt_tue: "Tuesday — Rigorous & relevant task",
  rrt_wed: "Wednesday — Rigorous & relevant task", rrt_thu: "Thursday — Rigorous & relevant task", rrt_fri: "Friday — Rigorous & relevant task",
  cfu_mon: "Monday — Checks for understanding", cfu_tue: "Tuesday — Checks for understanding",
  cfu_wed: "Wednesday — Checks for understanding", cfu_thu: "Thursday — Checks for understanding", cfu_fri: "Friday — Checks for understanding",
  ri_mon: "Monday — Responsive instruction", ri_tue: "Tuesday — Responsive instruction", ri_wed: "Wednesday — Responsive instruction",
  ri_thu: "Thursday — Responsive instruction", ri_fri: "Friday — Responsive instruction",
  sic_mon: "Monday — Strong instructional culture", sic_tue: "Tuesday — Strong instructional culture",
  sic_wed: "Wednesday — Strong instructional culture", sic_thu: "Thursday — Strong instructional culture", sic_fri: "Friday — Strong instructional culture",
  esl_mon: "Monday — Evidence of student learning", esl_tue: "Tuesday — Evidence of student learning",
  esl_wed: "Wednesday — Evidence of student learning", esl_thu: "Thursday — Evidence of student learning", esl_fri: "Friday — Evidence of student learning",
};

const FIELD_GROUPS: Array<{ label: string; fields: PlanningFieldKey[] }> = [
  { label: "Instructional Planning Framework", fields: ["unit_topic", "literacy_standards", "act_preparation", "know", "understand", "do_statement", "plds", "misconceptions", "formative", "summative", "performance_task", "resources"] },
  { label: "Week at a Glance — Clear learning target & success criteria", fields: ["clt_mon", "clt_tue", "clt_wed", "clt_thu", "clt_fri"] },
  { label: "Week at a Glance — Rigorous & relevant task", fields: ["rrt_mon", "rrt_tue", "rrt_wed", "rrt_thu", "rrt_fri"] },
  { label: "Week at a Glance — Checks for understanding", fields: ["cfu_mon", "cfu_tue", "cfu_wed", "cfu_thu", "cfu_fri"] },
  { label: "Week at a Glance — Responsive instruction", fields: ["ri_mon", "ri_tue", "ri_wed", "ri_thu", "ri_fri"] },
  { label: "Week at a Glance — Strong instructional culture", fields: ["sic_mon", "sic_tue", "sic_wed", "sic_thu", "sic_fri"] },
  { label: "Week at a Glance — Evidence of student learning", fields: ["esl_mon", "esl_tue", "esl_wed", "esl_thu", "esl_fri"] },
];
const FIELD_ORDER = FIELD_GROUPS.flatMap((group) => group.fields);

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch { /* bounded fallback */ }
  return fallback;
}

function requireGovernedLiteracySuggestion(suggestions: Record<string, string>): void {
  if (!(suggestions.literacy_standards ?? "").trim()) {
    throw new Error("TPP did not receive an approved Literacy Standards recommendation. Generate the planning draft again; the weekly plan will not silently continue with a blank governed literacy field.");
  }
}

export function AiPlanningPanel({ accessToken, assignmentId, weekStart, currentFields, hasScheduledLessons, hasSavedStandards, onApplyField }: AiPlanningPanelProps) {
  const [result, setResult] = useState<SuggestionResponse | null>(null);
  const [working, setWorking] = useState(false);
  const [decisionWorking, setDecisionWorking] = useState<PlanningFieldKey | "all" | null>(null);
  const [refreshingField, setRefreshingField] = useState<PlanningFieldKey | null>(null);
  const [decisions, setDecisions] = useState<Partial<Record<PlanningFieldKey, FieldDecision>>>({});
  const [edits, setEdits] = useState<Partial<Record<PlanningFieldKey, string>>>({});
  const [usageEventByField, setUsageEventByField] = useState<Partial<Record<PlanningFieldKey, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const pendingFields = useMemo(
    () => result ? FIELD_ORDER.filter((field) => (result.suggestions[field] ?? "").trim() && !decisions[field]) : [],
    [decisions, result],
  );

  const baseRequestFields = useCallback((fieldToRegenerate?: PlanningFieldKey): Record<string, string> => {
    const request: Record<string, string> = {};
    for (const field of BASE_FIELDS) request[field] = currentFields[field] ?? "";
    if (fieldToRegenerate && BASE_FIELD_SET.has(fieldToRegenerate)) request[fieldToRegenerate] = "";
    return request;
  }, [currentFields]);

  const requestBaseDraft = useCallback(async (fieldToRegenerate?: PlanningFieldKey): Promise<RawSuggestionResponse> => {
    if (!accessToken || !assignmentId) throw new Error("Select a course before generating a planning draft.");
    if (!hasScheduledLessons) throw new Error("Build this week's curriculum schedule before generating a planning draft.");
    if (!hasSavedStandards) throw new Error("Save at least one authoritative standard before generating a planning draft.");
    const response = await fetch(`/api/v1/ai/planning/${encodeURIComponent(assignmentId)}/week/${encodeURIComponent(weekStart)}`, {
      method: "POST", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify(baseRequestFields(fieldToRegenerate)),
    });
    if (!response.ok) throw new Error(await readError(response, "AI planning suggestions are unavailable."));
    const body = await response.json() as RawSuggestionResponse;
    requireGovernedLiteracySuggestion(body.suggestions);
    return body;
  }, [accessToken, assignmentId, baseRequestFields, hasSavedStandards, hasScheduledLessons, weekStart]);

  const requestDistrictDraft = useCallback(async (): Promise<RawSuggestionResponse> => {
    if (!accessToken || !assignmentId) throw new Error("Select a course before generating district planning details.");
    const response = await fetch(`/api/v1/ai/district-planning/${encodeURIComponent(assignmentId)}/week/${encodeURIComponent(weekStart)}`, {
      method: "POST", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify(baseRequestFields()),
    });
    if (!response.ok) throw new Error(await readError(response, "AI district planning suggestions are unavailable."));
    return await response.json() as RawSuggestionResponse;
  }, [accessToken, assignmentId, baseRequestFields, weekStart]);

  const suggest = useCallback(async (automatic = false) => {
    if (!accessToken || !assignmentId || working || !hasScheduledLessons || !hasSavedStandards) return;
    setWorking(true); setError(null); setMessage(automatic ? "Standards saved. Building your complete weekly planning draft…" : "Building your complete weekly planning draft…");
    try {
      const [base, district] = await Promise.all([requestBaseDraft(), requestDistrictDraft()]);
      const suggestions = { ...base.suggestions, ...district.suggestions } as SuggestionSet;
      requireGovernedLiteracySuggestion(suggestions);
      suggestions.alignment_summary = [base.suggestions.alignment_summary, district.suggestions.alignment_summary].filter(Boolean).join(" ");
      setResult({ ...base, suggestions }); setDecisions({}); setEdits({});
      setUsageEventByField(Object.fromEntries([
        ...BASE_FIELDS.map((field) => [field, base.usage_event_id]),
        ...DISTRICT_FIELDS.map((field) => [field, district.usage_event_id]),
      ]));
      setMessage("Complete planning draft ready. Framework suggestions follow the approved PDF order, followed by Week at a Glance. Nothing is saved until you save your weekly plan.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI planning suggestions are unavailable."); setMessage(null);
    } finally { setWorking(false); }
  }, [accessToken, assignmentId, hasSavedStandards, hasScheduledLessons, requestBaseDraft, requestDistrictDraft, working]);

  useEffect(() => {
    const handleStandardsSaved = (event: Event) => {
      const detail = (event as CustomEvent<{ assignmentId?: string; weekStart?: string }>).detail;
      if (detail?.assignmentId !== assignmentId || detail?.weekStart !== weekStart || !hasScheduledLessons) return;
      window.setTimeout(() => void suggest(true), 0);
    };
    window.addEventListener("tpp:standards-saved", handleStandardsSaved);
    return () => window.removeEventListener("tpp:standards-saved", handleStandardsSaved);
  }, [assignmentId, hasScheduledLessons, suggest, weekStart]);

  const recordDecision = async (field: PlanningFieldKey, decision: FieldDecision): Promise<void> => {
    if (!accessToken || !result) return;
    const usageEventId = usageEventByField[field] ?? result.usage_event_id;
    const response = await fetch(`/api/v1/ai/usage/${encodeURIComponent(usageEventId)}/decision/${encodeURIComponent(field)}`, {
      method: "PUT", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify({ decision }),
    });
    if (!response.ok) throw new Error(await readError(response, "AI review decision could not be recorded."));
  };

  const accept = async (field: PlanningFieldKey) => { if (!result) return; setDecisionWorking(field); setError(null); try { await recordDecision(field, "accepted"); onApplyField(field, result.suggestions[field]); setDecisions((current) => ({ ...current, [field]: "accepted" })); setMessage(`${FIELD_LABELS[field]} added to your working plan.`); } catch (caught) { setError(caught instanceof Error ? caught.message : "AI review decision could not be recorded."); } finally { setDecisionWorking(null); } };
  const applyEdit = async (field: PlanningFieldKey) => { if (!result) return; const value = edits[field] ?? result.suggestions[field]; setDecisionWorking(field); setError(null); try { await recordDecision(field, "edited"); onApplyField(field, value); setDecisions((current) => ({ ...current, [field]: "edited" })); setMessage(`${FIELD_LABELS[field]} edited text added to your working plan.`); } catch (caught) { setError(caught instanceof Error ? caught.message : "AI review decision could not be recorded."); } finally { setDecisionWorking(null); } };
  const reject = async (field: PlanningFieldKey) => { setDecisionWorking(field); setError(null); try { await recordDecision(field, "rejected"); setDecisions((current) => ({ ...current, [field]: "rejected" })); setMessage(`${FIELD_LABELS[field]} suggestion skipped. You can request another suggestion if needed.`); } catch (caught) { setError(caught instanceof Error ? caught.message : "AI review decision could not be recorded."); } finally { setDecisionWorking(null); } };

  const refreshField = async (field: PlanningFieldKey) => {
    if (!result || refreshingField || working) return; setRefreshingField(field); setError(null);
    try {
      const body = BASE_FIELD_SET.has(field) ? await requestBaseDraft(field) : await requestDistrictDraft();
      if (field === "literacy_standards") requireGovernedLiteracySuggestion(body.suggestions);
      setResult((current) => current ? { ...current, suggestions: { ...current.suggestions, [field]: body.suggestions[field] } } : current);
      setUsageEventByField((current) => ({ ...current, [field]: body.usage_event_id }));
      setDecisions((current) => { const next = { ...current }; delete next[field]; return next; });
      setEdits((current) => { const next = { ...current }; delete next[field]; return next; });
      setMessage(`A new ${FIELD_LABELS[field]} suggestion is ready for review.`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "A new suggestion could not be generated."); }
    finally { setRefreshingField(null); }
  };

  const applyFullDraft = async () => {
    if (!result) return;
    const fieldsToApply = pendingFields.filter((field) => (edits[field] ?? result.suggestions[field]).trim().length > 0);
    if (!fieldsToApply.length) return; setDecisionWorking("all"); setError(null);
    try {
      const nextDecisions: Partial<Record<PlanningFieldKey, FieldDecision>> = {};
      await Promise.all(fieldsToApply.map(async (field) => { const decision: FieldDecision = Object.prototype.hasOwnProperty.call(edits, field) ? "edited" : "accepted"; await recordDecision(field, decision); nextDecisions[field] = decision; }));
      for (const field of fieldsToApply) onApplyField(field, edits[field] ?? result.suggestions[field]);
      setDecisions((current) => ({ ...current, ...nextDecisions })); setMessage(`${fieldsToApply.length} planning fields added to your working plan. Review them before saving.`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "AI review decisions could not be recorded."); }
    finally { setDecisionWorking(null); }
  };

  return (
    <section className="panel ai-planning-panel" aria-labelledby="ai-planning-heading">
      <div className="section-heading-row"><div><p className="eyebrow">Planning assistance</p><h2 id="ai-planning-heading">Weekly planning draft</h2><p className="supporting">TPP prepares a grounded starting point for the full district weekly lesson plan, including the Framework and Week at a Glance. You decide what becomes part of your plan.</p></div><button type="button" className="primary" onClick={() => void suggest(false)} disabled={!accessToken || !assignmentId || !hasScheduledLessons || !hasSavedStandards || working}>{working ? <><span className="button-spinner" aria-hidden="true" /> Generating draft…</> : result ? "Generate a new draft" : "Generate planning draft"}</button></div>
      {!hasScheduledLessons ? <div className="guidance-card"><strong>Build this week's curriculum first.</strong><p>Add Curriculum & Pacing in Course Setup if needed, then build/reconcile the week. AI will not invent a weekly lesson sequence from standards alone.</p></div> : null}
      {hasScheduledLessons && !hasSavedStandards ? <div className="guidance-card"><strong>Save the standards you want to use.</strong><p>Select at least one authoritative standard above and choose Save standards and continue. AI planning starts only from the saved governed selection.</p></div> : null}
      {working ? <div className="working-status" role="status" aria-live="polite"><span className="button-spinner" aria-hidden="true" /><strong> Building your complete weekly planning draft…</strong><span>TPP is using scheduled lessons, selected standards, approved literacy candidates, governed ACT references, and the district planning-document structure.</span></div> : null}
      <div className="guidance-card ai-guidance"><strong>Planning suggestions are drafts.</strong><p>Suggestions use this week&apos;s scheduled lessons, selected authoritative standards, approved Alabama literacy standards, and governed ACT references. Authoritative wording is never rewritten. District Framework and Week-at-a-Glance entries are instructional suggestions for teacher review.</p></div>
      <div className="guidance-card" role="note" aria-label="Student data restriction"><strong>Professional planning only.</strong><p>Do not enter student names, identifiers, grades, identifiable student work, IEP/504, health, discipline, or other student-specific information.</p></div>
      {error ? <p className="error-message" role="alert">{error}</p> : null}{message ? <p className="success-message" role="status" aria-live="polite">{message}</p> : null}
      {result ? <><div className="ai-alignment-summary"><p className="example-label">Planning alignment note</p><p>{result.suggestions.alignment_summary}</p></div><div className="ai-full-draft-action"><div><strong>Use this draft as your starting point</strong><p>Framework suggestions follow the approved PDF order. Edit any suggestion if needed, then add all remaining nonblank fields in one action.</p></div><button type="button" className="primary" onClick={() => void applyFullDraft()} disabled={decisionWorking !== null || refreshingField !== null || pendingFields.length === 0}>{decisionWorking === "all" ? "Adding draft…" : "Use all remaining suggestions"}</button></div>{FIELD_GROUPS.map((group) => { const visibleFields = group.fields.filter((field) => (result.suggestions[field] ?? "").trim()); if (!visibleFields.length) return null; return <section className={`ai-suggestion-group ${group.fields.includes("literacy_standards") ? "governed-literacy-group" : ""}`} key={group.label}><h3>{group.label}</h3>{group.fields.includes("literacy_standards") ? <p className="supporting">TPP resolves Literacy Standards recommendations to exact approved Alabama ELA wording. They are never fabricated or rewritten by AI.</p> : null}<div className="ai-suggestion-list">{visibleFields.map((field) => { const decision = decisions[field]; const editingValue = edits[field] ?? result.suggestions[field]; return <article className="ai-suggestion-card" key={field}><div className="ai-suggestion-heading"><div><p className="example-label">Suggested text — not saved</p><h4>{FIELD_LABELS[field]}</h4></div>{decision ? <span className="decision-badge">{decision === "accepted" ? "Used" : decision === "edited" ? "Used with edits" : "Skipped"}</span> : null}</div>{decision ? <><p>{decision === "rejected" ? "This suggestion was skipped." : "This text was added to the working plan."}</p><button type="button" className="secondary" onClick={() => void refreshField(field)} disabled={decisionWorking !== null || refreshingField !== null}>{refreshingField === field ? "Generating another…" : "Generate another suggestion"}</button></> : <><textarea aria-label={`Suggested text for ${FIELD_LABELS[field]}`} value={editingValue} onChange={(event) => setEdits((current) => ({ ...current, [field]: event.target.value }))} rows={field === "literacy_standards" || field === "act_preparation" ? 6 : 4} /><div className="button-row"><button type="button" className="primary" onClick={() => void accept(field)} disabled={decisionWorking !== null || refreshingField !== null}>{field === "literacy_standards" ? "Use governed literacy standard" : "Use suggestion"}</button><button type="button" className="secondary" onClick={() => void applyEdit(field)} disabled={decisionWorking !== null || refreshingField !== null}>Use edited text</button><button type="button" className="secondary" onClick={() => void refreshField(field)} disabled={decisionWorking !== null || refreshingField !== null}>{refreshingField === field ? "Generating another…" : "Generate another"}</button><button type="button" className="link-button" onClick={() => void reject(field)} disabled={decisionWorking !== null || refreshingField !== null}>Skip suggestion</button></div></>}</article>; })}</div></section>; })}<p className="muted-text">{pendingFields.length} suggestion{pendingFields.length === 1 ? "" : "s"} still awaiting review.</p></> : null}
    </section>
  );
}