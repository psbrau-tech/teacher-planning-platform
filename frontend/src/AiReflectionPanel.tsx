import { useState } from "react";

type ReflectionResponse = {
  usage_event_id: string;
  model: string;
  estimated_cost_usd: string;
  suggestions: {
    weekly_reflection: string;
  };
};

type Decision = "accepted" | "edited" | "rejected";

type AiReflectionPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  disabled?: boolean;
  onApplyReflection: (value: string) => void;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep the bounded fallback; never surface raw provider/server content.
  }
  return fallback;
}

export function AiReflectionPanel({
  accessToken,
  assignmentId,
  weekStart,
  disabled = false,
  onApplyReflection,
}: AiReflectionPanelProps) {
  const [result, setResult] = useState<ReflectionResponse | null>(null);
  const [editedText, setEditedText] = useState("");
  const [decision, setDecision] = useState<Decision | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const requestReflection = async () => {
    if (!assignmentId) return;
    setWorking(true);
    setError(null);
    setMessage(null);
    setDecision(null);
    try {
      const response = await fetch(
        `/api/v1/ai/reflection/${encodeURIComponent(assignmentId)}` +
          `/week/${encodeURIComponent(weekStart)}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "AI reflection assistance is unavailable."));
      }
      const body = (await response.json()) as ReflectionResponse;
      setResult(body);
      setEditedText(body.suggestions.weekly_reflection);
      setMessage(
        "AI reflection draft is ready for review. Nothing has been added to your saved plan.",
      );
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "AI reflection assistance is unavailable.");
    } finally {
      setWorking(false);
    }
  };

  const recordDecision = async (nextDecision: Decision) => {
    if (!result) return;
    setWorking(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/v1/ai/usage/${encodeURIComponent(result.usage_event_id)}` +
          "/decision/weekly_reflection",
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ decision: nextDecision }),
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "AI reflection decision could not be recorded."));
      }
      if (nextDecision === "accepted") {
        onApplyReflection(result.suggestions.weekly_reflection);
      } else if (nextDecision === "edited") {
        onApplyReflection(editedText);
      }
      setDecision(nextDecision);
      setMessage(
        nextDecision === "rejected"
          ? "AI reflection suggestion rejected. Your plan was not changed."
          : "Reflection applied to the working form. Save the weekly draft when ready.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "AI reflection decision could not be recorded.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <section className="panel ai-reflection-panel" aria-labelledby="ai-reflection-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Optional reflection assistance</p>
          <h2 id="ai-reflection-heading">Weekly Reflection suggestion</h2>
        </div>
        <button
          type="button"
          className="secondary"
          disabled={!assignmentId || disabled || working}
          onClick={() => void requestReflection()}
        >
          {working && !result ? "Generating reflection…" : "Suggest Weekly Reflection"}
        </button>
      </div>

      <div className="guidance-card ai-guidance">
        <strong>Reflection suggestions are drafts.</strong>
        <p>
          The suggestion is generated only from the saved weekly plan, finalized Friday validation,
          and governed standards context. It does not infer or use student-specific information.
        </p>
      </div>

      <div className="guidance-card" role="note" aria-label="Student data restriction">
        <strong>Do not include student data.</strong>
        <p>
          Weekly Reflection AI assistance is limited to professional planning and finalized
          validation context. Do not enter student names, identifiers, grades, identifiable student
          work, IEP or 504 information, health or discipline information, or other information that
          can reasonably be linked to a student.
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
        <article className="ai-suggestion-card">
          <div className="ai-suggestion-heading">
            <div>
              <p className="example-label">AI draft suggestion — not saved</p>
              <h3>Weekly Reflection</h3>
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
                aria-label="AI draft Weekly Reflection"
                rows={7}
                value={editedText}
                onChange={(event) => setEditedText(event.target.value)}
              />
              <div className="button-row">
                <button
                  type="button"
                  className="primary"
                  disabled={working}
                  onClick={() => void recordDecision("accepted")}
                >
                  Accept as written
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={working}
                  onClick={() => void recordDecision("edited")}
                >
                  Apply edited version
                </button>
                <button
                  type="button"
                  className="link-button"
                  disabled={working}
                  onClick={() => void recordDecision("rejected")}
                >
                  Reject
                </button>
              </div>
            </>
          )}
          <p className="muted-text">
            Model: {result.model} · Estimated request cost: ${result.estimated_cost_usd}
          </p>
        </article>
      ) : null}
    </section>
  );
}
