import { useCallback, useEffect, useMemo, useState } from "react";

export type PlanningFieldKey =
  | "unit_topic"
  | "literacy_standards"
  | "act_preparation"
  | "learning_targets"
  | "know"
  | "understand"
  | "do_statement"
  | "activities"
  | "assessments"
  | "resources"
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday";

export type CurrentPlanningFields = Record<PlanningFieldKey, string>;

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
  unit_topic: "Unit / topic",
  literacy_standards: "Literacy Standards",
  act_preparation: "ACT Preparation",
  learning_targets: "Learning targets",
  know: "Know",
  understand: "Understand",
  do_statement: "Do",
  activities: "Activities",
  assessments: "Assessments",
  resources: "Resources",
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
};

const FIELD_GROUPS: Array<{ label: string; fields: PlanningFieldKey[] }> = [
  {
    label: "Standards alignment",
    fields: [
      "unit_topic",
      "literacy_standards",
      "act_preparation",
      "learning_targets",
      "know",
      "understand",
      "do_statement",
    ],
  },
  {
    label: "Instructional design",
    fields: ["activities", "assessments", "resources"],
  },
  {
    label: "Daily plan",
    fields: ["monday", "tuesday", "wednesday", "thursday", "friday"],
  },
];

const FIELD_ORDER = FIELD_GROUPS.flatMap((group) => group.fields);

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
  const [decisionWorking, setDecisionWorking] = useState<PlanningFieldKey | "all" | null>(null);
  const [decisions, setDecisions] = useState<Partial<Record<PlanningFieldKey, FieldDecision>>>({});
  const [edits, setEdits] = useState<Partial<Record<PlanningFieldKey, string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const pendingFields = useMemo(
    () => FIELD_ORDER.filter((field) => !decisions[field]),
    [decisions],
  );

  const suggest = useCallback(async (automatic = false) => {
    if (!accessToken || !assignmentId || working) return;
    setWorking(true);
    setError(null);
    setMessage(
      automatic
        ? "Standards saved. Preparing a grounded weekly planning draft…"
        : null,
    );
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
        "Planning draft ready. Review it below, then apply the full draft or handle fields individually. Nothing has been added to your plan.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI planning suggestions are unavailable.");
      setMessage(null);
    } finally {
      setWorking(false);
    }
  }, [accessToken, assignmentId, currentFields, weekStart, working]);

  useEffect(() => {
    const handleStandardsSaved = (event: Event) => {
      const detail = (event as CustomEvent<{ assignmentId?: string; weekStart?: string }>).detail;
      if (detail?.assignmentId !== assignmentId || detail?.weekStart !== weekStart) return;
      void suggest(true);
    };
    window.addEventListener("tpp:standards-saved", handleStandardsSaved);
    return () => window.removeEventListener("tpp:standards-saved", handleStandardsSaved);
  }, [assignmentId, suggest, weekStart]);

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

  const applyFullDraft = async () => {
    if (!result) return;
    const fieldsToApply = pendingFields.filter((field) => {
      const value = edits[field] ?? result.suggestions[field];
      return value.trim().length > 0;
    });
    if (fieldsToApply.length === 0) return;
    setDecisionWorking("all");
    setError(null);
    try {
      const nextDecisions: Partial<Record<PlanningFieldKey, FieldDecision>> = {};
      await Promise.all(
        fieldsToApply.map(async (field) => {
          const edited = Object.prototype.hasOwnProperty.call(edits, field);
          const decision: FieldDecision = edited ? "edited" : "accepted";
          await recordDecision(field, decision);
          nextDecisions[field] = decision;
        }),
      );
      for (const field of fieldsToApply) {
        onApplyField(field, edits[field] ?? result.suggestions[field]);
      }
      setDecisions((current) => ({ ...current, ...nextDecisions }));
      setMessage(
        `${fieldsToApply.length} planning fields applied to the working form. Review or edit them before saving the weekly draft.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI review decisions could not be recorded.");
    } finally {
      setDecisionWorking(null);
    }
  };

  return (
    <section className="panel ai-planning-panel" aria-labelledby="ai-planning-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Integrated planning assistance</p>
          <h2 id="ai-planning-heading">Weekly planning draft</h2>
          <p className="supporting">
            Saving weekly standards prepares a draft automatically. You remain in control of every
            field before anything becomes part of the saved plan.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void suggest(false)}
          disabled={!accessToken || !assignmentId || working}
        >
          {working ? "Generating planning draft…" : result ? "Regenerate draft" : "Generate planning draft"}
        </button>
      </div>

      <div className="guidance-card ai-guidance">
        <strong>AI suggestions are drafts.</strong>
        <p>
          TPP grounds the draft in the imported lessons scheduled for this week, the exact
          authoritative standards you selected, approved Alabama literacy standards, and the
          governed ACT reference catalog. AI does not rewrite authoritative wording.
        </p>
      </div>

      <div className="guidance-card" role="note" aria-label="Student data restriction">
        <strong>Do not include student data.</strong>
        <p>
          TPP AI assistance is for professional planning context only. Do not enter student names,
          identifiers, grades, identifiable student work, IEP or 504 information, health or
          discipline information, or other information that can reasonably be linked to a student.
        </p>
      </div>

      {error ? (
        <p className="error-message" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="success-message" role="status" aria-live="polite">
          {message}
        </p>
      ) : null}

      {result ? (
        <>
          <div className="ai-alignment-summary">
            <p className="example-label">AI alignment note — reference only</p>
            <p>{result.suggestions.alignment_summary}</p>
          </div>

          <div className="ai-full-draft-action">
            <div>
              <strong>Use the draft as your starting point</strong>
              <p>
                You can edit any suggestion below first, then apply the full draft in one action.
                Empty unscheduled weekdays are left unchanged.
              </p>
            </div>
            <button
              type="button"
              className="primary"
              onClick={() => void applyFullDraft()}
              disabled={decisionWorking !== null || pendingFields.length === 0}
            >
              {decisionWorking === "all" ? "Applying draft…" : "Apply full planning draft"}
            </button>
          </div>

          {FIELD_GROUPS.map((group) => (
            <section className="ai-suggestion-group" key={group.label} aria-label={group.label}>
              <h3>{group.label}</h3>
              <div className="ai-suggestion-list">
                {group.fields.map((field) => {
                  const decision = decisions[field];
                  const editingValue = edits[field] ?? result.suggestions[field];
                  return (
                    <article className="ai-suggestion-card" key={field}>
                      <div className="ai-suggestion-heading">
                        <div>
                          <p className="example-label">AI draft suggestion — not saved</p>
                          <h4>{FIELD_LABELS[field]}</h4>
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
                            rows={field === "literacy_standards" || field === "act_preparation" ? 6 : 4}
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
            </section>
          ))}

          <p className="muted-text">
            {pendingFields.length} suggestion{pendingFields.length === 1 ? "" : "s"} still awaiting
            review. Estimated request cost: ${result.estimated_cost_usd}.
          </p>
        </>
      ) : null}
    </section>
  );
}
