import { useMemo, useState } from "react";
import "./pilot-feedback.css";

type FeedbackResult = {
  id: string;
  school_name: string;
  teacher_name: string;
  overall_usefulness: number;
  planning_time_change: string;
  most_useful: string;
  biggest_challenge: string;
  dislike_or_simplify: string;
  recommended_improvement: string;
  rollout_readiness: string;
  submitted_at: string;
};

type Props = { accessToken: string; disabled?: boolean };

const TIME_LABELS: Record<string, string> = {
  much_less: "Much less time",
  somewhat_less: "Somewhat less time",
  about_same: "About the same",
  somewhat_more: "Somewhat more time",
  much_more: "Much more time",
};

const READINESS_LABELS: Record<string, string> = {
  ready_now: "Ready now",
  ready_minor_fixes: "Ready with minor fixes",
  needs_significant_fixes: "Needs significant fixes",
  not_ready: "Not ready",
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    return typeof payload.detail === "string" && payload.detail.trim() ? payload.detail : fallback;
  } catch {
    return fallback;
  }
}

export function PilotFeedbackResultsPanel({ accessToken, disabled = false }: Props) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<FeedbackResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadResults() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/v1/session/pilot-feedback/results", {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error(await readError(response, "Pilot feedback could not be loaded."));
      setResults(await response.json() as FeedbackResult[]);
      setOpen(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pilot feedback could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    if (!results.length) return null;
    const average = results.reduce((sum, item) => sum + item.overall_usefulness, 0) / results.length;
    const timeSaved = results.filter((item) => ["much_less", "somewhat_less"].includes(item.planning_time_change)).length;
    const rolloutPositive = results.filter((item) => ["ready_now", "ready_minor_fixes"].includes(item.rollout_readiness)).length;
    return { average, timeSaved, rolloutPositive };
  }, [results]);

  return (
    <>
      <article className="card owner-tool-card">
        <p className="eyebrow">Pilot learning</p>
        <h3>Pilot feedback</h3>
        <p>Review teacher-reported usefulness, friction, time impact, and rollout readiness.</p>
        <button type="button" className="secondary" disabled={disabled || loading} onClick={() => void loadResults()}>
          {loading ? "Loading…" : "Open Pilot feedback"}
        </button>
        {error && <p className="error-message" role="alert">{error}</p>}
      </article>

      {open && (
        <div className="pilot-feedback-backdrop" role="presentation">
          <section className="pilot-feedback-modal pilot-feedback-results" role="dialog" aria-modal="true" aria-labelledby="pilot-feedback-results-title">
            <div className="pilot-feedback-heading">
              <div>
                <p className="eyebrow">Platform Owner</p>
                <h2 id="pilot-feedback-results-title">Pilot feedback</h2>
                <p>Adult professional/product feedback submitted before broader staff rollout.</p>
              </div>
              <button type="button" className="secondary" onClick={() => setOpen(false)}>Close</button>
            </div>

            {summary && (
              <div className="pilot-feedback-summary" aria-label="Pilot feedback summary">
                <div><strong>{results.length}</strong><span>responses</span></div>
                <div><strong>{summary.average.toFixed(1)}/5</strong><span>average usefulness</span></div>
                <div><strong>{summary.timeSaved}/{results.length}</strong><span>report less planning time</span></div>
                <div><strong>{summary.rolloutPositive}/{results.length}</strong><span>ready / minor fixes</span></div>
              </div>
            )}

            {results.length === 0 ? (
              <div className="empty-state"><p>No Pilot feedback has been submitted yet.</p></div>
            ) : (
              <div className="pilot-feedback-response-list">
                {results.map((item) => (
                  <article className="pilot-feedback-response" key={item.id}>
                    <div className="card-row">
                      <div><strong>{item.teacher_name}</strong><small>{item.school_name}</small></div>
                      <span className="badge">{new Date(item.submitted_at).toLocaleString()}</span>
                    </div>
                    <p>
                      <strong>Usefulness:</strong> {item.overall_usefulness}/5 · <strong>Time:</strong>{" "}
                      {TIME_LABELS[item.planning_time_change] ?? item.planning_time_change} · <strong>Rollout:</strong>{" "}
                      {READINESS_LABELS[item.rollout_readiness] ?? item.rollout_readiness}
                    </p>
                    <dl>
                      <div><dt>Most useful</dt><dd>{item.most_useful}</dd></div>
                      <div><dt>Biggest challenge</dt><dd>{item.biggest_challenge}</dd></div>
                      {item.dislike_or_simplify && <div><dt>Simplify / remove</dt><dd>{item.dislike_or_simplify}</dd></div>}
                      <div><dt>One improvement</dt><dd>{item.recommended_improvement}</dd></div>
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
