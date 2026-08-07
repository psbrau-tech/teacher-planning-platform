import { useMemo, useState } from "react";

export type PlanningFieldKey =
  | "learning_targets"
  | "know"
  | "understand"
  | "do_statement"
  | "activities"
  | "assessments"
  | "resources"
  | "literacy_standards"
  | "act_preparation";

export type CurrentPlanningFields = {
  unit_topic: string;
  literacy_standards: string;
  act_preparation: string;
  learning_targets: string;
  know: string;
  understand: string;
  do_statement: string;
  activities: string;
  assessments: string;
  resources: string;
  monday: string;
  tuesday: string;
  wednesday: string;
  thursday: string;
  friday: string;
};

type SuggestionSet = Record<PlanningFieldKey, string> & {
  alignment_summary: string;
};

type SuggestionResponse = {
  usage_event_id: string;
  model: string;
  estimated_cost_usd: string;
  suggestions: SuggestionSet;
};

type FieldDecision = "accepted" | "edited" | "rejected";

type AiPlanningPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  currentFields: CurrentPlanningFields;
  onApplyField: (field: PlanningFieldKey, value: string) => void;
};

const FIELD_LABELS: Record<PlanningFieldKey, string> = {
  learning_targets: "Learning targets",
  know: "Know",
  understand: "Understand",
  do_statement: "Do",
  activities: "Activities",
  assessments: "Assessments",
  resources: "Resources",
  literacy_standards: "Literacy Standards",
  act_preparation: "ACT Preparation",
};

const FIELD_ORDER = Object.keys(FIELD_LABELS) as PlanningFieldKey[];

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep the bounded fallback; never surface raw provider/server content.
  }
  return fallback;
}

export function AiPlanningPanel({
  accessToken,
  assignmentId,
  weekStart,
  currentFields,
  onApplyField,
}: AiPlanningPanelProps) {
  const [result, setResult] = useState<SuggestionResponse | null>(null);
  const [working, setWorking] = useState(false);
  const [decisionWorking, setDecisionWorking] = useState<PlanningFieldKey | null>(null);
  const [decisions, setDecisions] = useState<Partial<Record<PlanningFieldKey, FieldDecision>>>({});
  const [edits, setEdits] = useState<Partial<Record<PlanningFieldKey, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const pendingFields = useMemo(
    () => FIELD_ORDER.filter((field) => !decisions[field]),
    [decisions],
  );

  const suggest = async () => {
    if (!accessToken || !assignmentId) return;
    setWorking(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(
        `/api/v1/ai/planning/${encodeURIComponent(assignmentId)}` +
          `/week/${encodeURIComponent(weekStart)}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(currentFields),
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "AI planning suggestions are unavailable."));
      }
      const body = (await response.json()) as SuggestionResponse;
      setResult(body);
      setDecisions({});
      setEdits({});
      setMessage(
        "AI draft suggestions are ready for review. Nothing has been added to your plan.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI planning suggestions are unavailable.");
    } finally {
      setWorking(false);
    }
  };

  const recordDecision = async (
    field: PlanningFieldKey,
    decision: FieldDecision,
  ): Promise<void> => {
    if (!accessToken || !result) return;
    const response = await fetch(
      `/api/v1/ai/usage/${encodeURIComponent(result.usage_event_id)}` +
        `/decision/${encodeURIComponent(field)}`,
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ decision }),
      },
    );
    if (!response.ok) {
      throw new Error(await readError(response, "AI review decision could not be recorded."));
    }
  };

  const accept = async (field: PlanningFieldKey) => {
    if (!result) return;
    setDecisionWorking(field);
    setError(null);
    try {
      await recordDecision(field, "accepted");
      onApplyField(field, result.suggestions[field]);
      setDecisions((current) => ({ ...current, [field]: "accepted" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI review decision could not be recorded.");
    } finally {
      setDecisionWorking(null);
    }
  };

  const applyEdit = async (field: PlanningFieldKey) => {
    if (!result) return;
    const value = edits[field] ?? result.suggestions[field];
    setDecisionWorking(field);
    setError(null);
    try {
      await recordDecision(field, "edited");
      onApplyField(field, value);
      setDecisions((current) => ({ ...current, [field]: "edited" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI review decision could not be recorded.");
    } finally {
      setDecisionWorking(null);
    }
  };

  const reject = async (field: PlanningFieldKey) => {
    setDecisionWorking(field);
    setError(null);
    try {
      await recordDecision(field, "rejected");
      setDecisions((current) => ({ ...current, [field]: "rejected" }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI review decision could not be recorded.");
    } finally {
      setDecisionWorking(null);
    }
  };

  return (
    <section className="panel ai-planning-panel" aria-labelledby="ai-planning-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Optional planning assistance</p>
          <h2 id="ai-planning-heading">AI planning suggestions</h2>
        </div>
        <button
          type="button"
          onClick={() => void suggest()}
          disabled={!accessToken || !assignmentId || working}
        >
          {working ? "Generating suggestions…" : "Suggest planning"}
        </button>
      </div>

      <div className="guidance-card ai-guidance">
        <strong>AI suggestions are drafts.</strong>
        <p>
          Suggestions use the standards you selected and your current teacher-planning context.
          They do not change or save your plan until you review and apply them.
        </p>
      </div>

      {error ? <p className="error-message">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}

      {result ? (
        <>
          <div className="ai-alignment-summary">
            <p className="example-label">AI alignment note — reference only</p>
            <p>{result.suggestions.alignment_summary}</p>
          </div>

          <div className="ai-suggestion-list">
            {FIELD_ORDER.map((field) => {
              const decision = decisions[field];
              const editingValue = edits[field] ?? result.suggestions[field];
              return (
                <article className="ai-suggestion-card" key={field}>
                  <div className="ai-suggestion-heading">
                    <div>
                      <p className="example-label">AI draft suggestion — not saved</p>
                      <h3>{FIELD_LABELS[field]}</h3>
                    </div>
                    {decision ? <span className="decision-badge">{decision}</span> : null}
                  </div>

                  {decision ? (
                    <p>
                      {decision === "rejected"
                        ? "Suggestion rejected."
                        : "Applied to the working form. Save the weekly draft when ready."}
                    </p>
                  ) : (
                    <>
                      <textarea
                        aria-label={`AI draft for ${FIELD_LABELS[field]}`}
                        value={editingValue}
                        onChange={(event) =>
                          setEdits((current) => ({ ...current, [field]: event.target.value }))
                        }
                        rows={4}
                      />
                      <div className="button-row">
                        <button
                          type="button"
                          onClick={() => void accept(field)}
                          disabled={decisionWorking !== null}
                        >
                          Accept as written
                        </button>
                        <button
                          type="button"
                          className="secondary-button"
                          onClick={() => void applyEdit(field)}
                          disabled={decisionWorking !== null}
                        >
                          Apply edited version
                        </button>
                        <button
                          type="button"
                          className="text-button"
                          onClick={() => void reject(field)}
                          disabled={decisionWorking !== null}
                        >
                          Reject
                        </button>
                      </div>
                    </>
                  )}
                </article>
              );
            })}
          </div>

          <p className="muted-text">
            {pendingFields.length} suggestion{pendingFields.length === 1 ? "" : "s"} still awaiting
            review. Estimated request cost: ${result.estimated_cost_usd}.
          </p>
        </>
      ) : null}
    </section>
  );
}
