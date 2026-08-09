import { useCallback, useEffect, useMemo, useState } from "react";

export type PlanningFieldKey =
  | "unit_topic" | "literacy_standards" | "act_preparation" | "learning_targets"
  | "know" | "understand" | "do_statement" | "activities" | "assessments" | "resources"
  | "monday" | "tuesday" | "wednesday" | "thursday" | "friday";

export type CurrentPlanningFields = Record<PlanningFieldKey, string>;
type SuggestionSet = Record<PlanningFieldKey, string> & { alignment_summary: string };
type SuggestionResponse = { usage_event_id: string; model: string; estimated_cost_usd: string; suggestions: SuggestionSet };
type FieldDecision = "accepted" | "edited" | "rejected";

type AiPlanningPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  currentFields: CurrentPlanningFields;
  hasScheduledLessons: boolean;
  onApplyField: (field: PlanningFieldKey, value: string) => void;
};

const FIELD_LABELS: Record<PlanningFieldKey, string> = {
  unit_topic: "Unit / topic", literacy_standards: "Literacy Standards", act_preparation: "ACT Preparation",
  learning_targets: "Learning targets", know: "Know", understand: "Understand", do_statement: "Do",
  activities: "Activities", assessments: "Assessments", resources: "Resources", monday: "Monday",
  tuesday: "Tuesday", wednesday: "Wednesday", thursday: "Thursday", friday: "Friday",
};

const FIELD_GROUPS: Array<{ label: string; fields: PlanningFieldKey[] }> = [
  { label: "Standards alignment", fields: ["unit_topic", "literacy_standards", "act_preparation", "learning_targets", "know", "understand", "do_statement"] },
  { label: "Instructional design", fields: ["activities", "assessments", "resources"] },
  { label: "Daily plan", fields: ["monday", "tuesday", "wednesday", "thursday", "friday"] },
];
const FIELD_ORDER = FIELD_GROUPS.flatMap((group) => group.fields);

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch { /* bounded fallback */ }
  return fallback;
}

export function AiPlanningPanel({ accessToken, assignmentId, weekStart, currentFields, hasScheduledLessons, onApplyField }: AiPlanningPanelProps) {
  const [result, setResult] = useState<SuggestionResponse | null>(null);
  const [working, setWorking] = useState(false);
  const [decisionWorking, setDecisionWorking] = useState<PlanningFieldKey | "all" | null>(null);
  const [refreshingField, setRefreshingField] = useState<PlanningFieldKey | null>(null);
  const [decisions, setDecisions] = useState<Partial<Record<PlanningFieldKey, FieldDecision>>>({});
  const [edits, setEdits] = useState<Partial<Record<PlanningFieldKey, string>>>({});
  const [usageEventByField, setUsageEventByField] = useState<Partial<Record<PlanningFieldKey, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const pendingFields = useMemo(() => FIELD_ORDER.filter((field) => !decisions[field]), [decisions]);

  const requestDraft = useCallback(async (fieldToRegenerate?: PlanningFieldKey): Promise<SuggestionResponse> => {
    if (!accessToken || !assignmentId) throw new Error("Select a course before generating a planning draft.");
    if (!hasScheduledLessons) throw new Error("Build this week's curriculum schedule before generating a planning draft.");
    const requestFields: CurrentPlanningFields = fieldToRegenerate ? { ...currentFields, [fieldToRegenerate]: "" } : currentFields;
    const response = await fetch(`/api/v1/ai/planning/${encodeURIComponent(assignmentId)}/week/${encodeURIComponent(weekStart)}`, {
      method: "POST", headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" }, body: JSON.stringify(requestFields),
    });
    if (!response.ok) throw new Error(await readError(response, "AI planning suggestions are unavailable."));
    return await response.json() as SuggestionResponse;
  }, [accessToken, assignmentId, currentFields, hasScheduledLessons, weekStart]);

  const suggest = useCallback(async (automatic = false) => {
    if (!accessToken || !assignmentId || working || !hasScheduledLessons) return;
    setWorking(true); setError(null); setMessage(automatic ? "Standards saved. Building your weekly planning draft…" : "Building your weekly planning draft…");
    try {
      const body = await requestDraft();
      setResult(body); setDecisions({}); setEdits({});
      setUsageEventByField(Object.fromEntries(FIELD_ORDER.map((field) => [field, body.usage_event_id])));
      setMessage("Planning draft ready. Use the whole draft or review each field. Nothing is saved until you save your weekly plan.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI planning suggestions are unavailable."); setMessage(null);
    } finally { setWorking(false); }
  }, [accessToken, assignmentId, hasScheduledLessons, requestDraft, working]);

  useEffect(() => {
    const handleStandardsSaved = (event: Event) => {
      const detail = (event as CustomEvent<{ assignmentId?: string; weekStart?: string }>).detail;
      if (detail?.assignmentId !== assignmentId || detail?.weekStart !== weekStart || !hasScheduledLessons) return;
      void suggest(true);
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
      const body = await requestDraft(field);
      setResult((current) => current ? { ...current, suggestions: { ...current.suggestions, [field]: body.suggestions[field] } } : body);
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
      <div className="section-heading-row"><div><p className="eyebrow">Planning assistance</p><h2 id="ai-planning-heading">Weekly planning draft</h2><p className="supporting">TPP prepares a grounded starting point from the curriculum actually scheduled this week. You decide what becomes part of your plan.</p></div><button type="button" className="secondary" onClick={() => void suggest(false)} disabled={!accessToken || !assignmentId || !hasScheduledLessons || working}>{working ? <><span className="button-spinner" aria-hidden="true" /> Generating draft…</> : result ? "Generate a new draft" : "Generate planning draft"}</button></div>
      {!hasScheduledLessons ? <div className="guidance-card"><strong>Build this week's curriculum first.</strong><p>Add Curriculum & Pacing in Course Setup if needed, then build/reconcile the week. AI will not invent a weekly lesson sequence from standards alone.</p></div> : null}
      {working ? <div className="working-status" role="status" aria-live="polite"><span className="button-spinner" aria-hidden="true" /><strong> Building your weekly planning draft…</strong><span>TPP is using the scheduled lessons, selected standards, approved literacy candidates, and governed ACT references.</span></div> : null}
      <div className="guidance-card ai-guidance"><strong>Planning suggestions are drafts.</strong><p>Suggestions use this week&apos;s scheduled lessons, selected authoritative standards, approved Alabama literacy standards, and governed ACT references. Authoritative wording is never rewritten.</p></div>
      <div className="guidance-card" role="note" aria-label="Student data restriction"><strong>Professional planning only.</strong><p>Do not enter student names, identifiers, grades, identifiable student work, IEP/504, health, discipline, or other student-specific information.</p></div>
      {error ? <p className="error-message" role="alert">{error}</p> : null}{message ? <p className="success-message" role="status" aria-live="polite">{message}</p> : null}
      {result ? <><div className="ai-alignment-summary"><p className="example-label">Planning alignment note</p><p>{result.suggestions.alignment_summary}</p></div><div className="ai-full-draft-action"><div><strong>Use this draft as your starting point</strong><p>Edit any suggestion first if needed, then add all remaining nonblank fields in one action.</p></div><button type="button" className="primary" onClick={() => void applyFullDraft()} disabled={decisionWorking !== null || refreshingField !== null || pendingFields.length === 0}>{decisionWorking === "all" ? "Adding draft…" : "Use all remaining suggestions"}</button></div>{FIELD_GROUPS.map((group) => <section className="ai-suggestion-group" key={group.label}><h3>{group.label}</h3><div className="ai-suggestion-list">{group.fields.map((field) => { const decision = decisions[field]; const editingValue = edits[field] ?? result.suggestions[field]; return <article className="ai-suggestion-card" key={field}><div className="ai-suggestion-heading"><div><p className="example-label">Suggested text — not saved</p><h4>{FIELD_LABELS[field]}</h4></div>{decision ? <span className="decision-badge">{decision === "accepted" ? "Used" : decision === "edited" ? "Used with edits" : "Skipped"}</span> : null}</div>{decision ? <><p>{decision === "rejected" ? "This suggestion was skipped." : "This text was added to the working plan."}</p><button type="button" className="secondary" onClick={() => void refreshField(field)} disabled={decisionWorking !== null || refreshingField !== null}>{refreshingField === field ? "Generating another…" : "Generate another suggestion"}</button></> : <><textarea aria-label={`Suggested text for ${FIELD_LABELS[field]}`} value={editingValue} onChange={(event) => setEdits((current) => ({ ...current, [field]: event.target.value }))} rows={field === "literacy_standards" || field === "act_preparation" ? 6 : 4} /><div className="button-row"><button type="button" className="primary" onClick={() => void accept(field)} disabled={decisionWorking !== null || refreshingField !== null}>Use suggestion</button><button type="button" className="secondary" onClick={() => void applyEdit(field)} disabled={decisionWorking !== null || refreshingField !== null}>Use edited text</button><button type="button" className="secondary" onClick={() => void refreshField(field)} disabled={decisionWorking !== null || refreshingField !== null}>{refreshingField === field ? "Generating another…" : "Generate another"}</button><button type="button" className="link-button" onClick={() => void reject(field)} disabled={decisionWorking !== null || refreshingField !== null}>Skip suggestion</button></div></>}</article>; })}</div></section>)}<p className="muted-text">{pendingFields.length} suggestion{pendingFields.length === 1 ? "" : "s"} still awaiting review.</p></> : null}
    </section>
  );
}