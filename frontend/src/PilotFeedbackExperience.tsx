import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import "./pilot-feedback.css";

type Identity = {
  id: string;
  display_name: string;
  roles: string[];
};

type FeedbackStatus = {
  survey_key: string;
  eligible: boolean;
  available: boolean;
  submitted: boolean;
  preferred_ready: boolean;
  fallback_ready: boolean;
  required_closeouts: number;
  completed_closeouts: number;
  required_next_week_plans: number;
  saved_next_week_plans: number;
  submitted_at: string | null;
};

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

type TextField =
  | "most_useful"
  | "biggest_challenge"
  | "dislike_or_simplify"
  | "recommended_improvement";

const TEXT_LIMIT = 1500;
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const feedbackSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

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
    return typeof payload.detail === "string" && payload.detail.trim()
      ? payload.detail
      : fallback;
  } catch {
    return fallback;
  }
}

function Counter({ value }: { value: string }) {
  const remaining = TEXT_LIMIT - value.length;
  return (
    <small className={`pilot-feedback-counter ${remaining <= 150 ? "near-limit" : ""}`}>
      {remaining === 0
        ? "Character limit reached"
        : `${remaining.toLocaleString()} characters remaining`}
    </small>
  );
}

export function PilotFeedbackExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [status, setStatus] = useState<FeedbackStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [results, setResults] = useState<FeedbackResult[]>([]);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [overallUsefulness, setOverallUsefulness] = useState("");
  const [planningTimeChange, setPlanningTimeChange] = useState("");
  const [rolloutReadiness, setRolloutReadiness] = useState("");
  const [text, setText] = useState<Record<TextField, string>>({
    most_useful: "",
    biggest_challenge: "",
    dislike_or_simplify: "",
    recommended_improvement: "",
  });

  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;
  const isPlatformAdmin = identity?.roles.includes("platform_admin") ?? false;
  const shouldShowSurvey = Boolean(
    accessToken && isTeacher && status?.available && !status.submitted && !dismissed && !submitted,
  );
  const shouldShowThanks = Boolean(accessToken && isTeacher && submitted && !dismissed);

  async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    if (init?.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    return await fetch(path, { ...init, headers });
  }

  async function loadIdentity(activeSession: Session) {
    const response = await fetch("/api/v1/session", {
      headers: { Authorization: `Bearer ${activeSession.access_token}` },
    });
    if (!response.ok) return;
    setIdentity(await response.json() as Identity);
  }

  async function loadStatus() {
    if (!accessToken || !isTeacher || dismissed || submitted) return;
    const response = await authenticatedFetch("/api/v1/session/pilot-feedback/status");
    if (!response.ok) return;
    setStatus(await response.json() as FeedbackStatus);
  }

  async function loadResults() {
    if (!accessToken || !isPlatformAdmin) return;
    const response = await authenticatedFetch("/api/v1/session/pilot-feedback/results");
    if (!response.ok) return;
    setResults(await response.json() as FeedbackResult[]);
  }

  useEffect(() => {
    if (!feedbackSupabase) return;
    void feedbackSupabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      if (data.session) void loadIdentity(data.session);
    });
    const { data } = feedbackSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setStatus(null);
      setDismissed(false);
      setSubmitted(false);
      if (nextSession) void loadIdentity(nextSession);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!accessToken || !identity) return;
    void loadStatus();
    void loadResults();
    const interval = window.setInterval(() => {
      void loadStatus();
      if (isPlatformAdmin) void loadResults();
    }, 30_000);
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      void loadStatus();
      if (isPlatformAdmin) void loadResults();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [accessToken, identity?.id, isTeacher, isPlatformAdmin, dismissed, submitted]);

  function updateText(field: TextField, value: string) {
    setText((current) => ({ ...current, [field]: value }));
  }

  async function submitFeedback(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!overallUsefulness || !planningTimeChange || !rolloutReadiness) {
      setError("Complete the rating, time-impact, and rollout-readiness questions.");
      return;
    }
    if (
      !text.most_useful.trim()
      || !text.biggest_challenge.trim()
      || !text.recommended_improvement.trim()
    ) {
      setError("Complete the three required written feedback questions.");
      return;
    }

    setWorking(true);
    setError("");
    try {
      const response = await authenticatedFetch("/api/v1/session/pilot-feedback", {
        method: "POST",
        body: JSON.stringify({
          overall_usefulness: Number(overallUsefulness),
          planning_time_change: planningTimeChange,
          most_useful: text.most_useful,
          biggest_challenge: text.biggest_challenge,
          dislike_or_simplify: text.dislike_or_simplify,
          recommended_improvement: text.recommended_improvement,
          rollout_readiness: rolloutReadiness,
        }),
      });
      if (!response.ok) {
        throw new Error(await readError(response, "Pilot feedback could not be submitted."));
      }
      setSubmitted(true);
      setStatus((current) => current
        ? { ...current, submitted: true, available: false }
        : current);
      if (isPlatformAdmin) void loadResults();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Pilot feedback could not be submitted.");
    } finally {
      setWorking(false);
    }
  }

  const summary = useMemo(() => {
    if (!results.length) return null;
    const average = results.reduce((sum, item) => sum + item.overall_usefulness, 0) / results.length;
    const timeSaved = results.filter(
      (item) => ["much_less", "somewhat_less"].includes(item.planning_time_change),
    ).length;
    const rolloutPositive = results.filter(
      (item) => ["ready_now", "ready_minor_fixes"].includes(item.rollout_readiness),
    ).length;
    return { average, timeSaved, rolloutPositive };
  }, [results]);

  if (!feedbackSupabase || !session || !identity) return null;

  return (
    <>
      {(shouldShowSurvey || shouldShowThanks) && (
        <div className="pilot-feedback-backdrop" role="presentation">
          <section
            className="pilot-feedback-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pilot-feedback-title"
          >
            {shouldShowThanks ? (
              <div className="pilot-feedback-thanks">
                <p className="eyebrow">Pilot feedback</p>
                <h2 id="pilot-feedback-title">Thank you.</h2>
                <p>
                  Your feedback has been recorded and will be used to improve TPP before broader
                  staff rollout.
                </p>
                <button className="primary" type="button" onClick={() => setDismissed(true)}>
                  Continue
                </button>
              </div>
            ) : (
              <form onSubmit={(event) => void submitFeedback(event)}>
                <div className="pilot-feedback-heading">
                  <div>
                    <p className="eyebrow">One-time Pilot feedback</p>
                    <h2 id="pilot-feedback-title">Help us improve TPP before full staff rollout</h2>
                    <p>
                      This should take about 3 minutes. Tell us what saved time, what created
                      friction, and what should change.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setDismissed(true)}
                  >
                    Remind me later
                  </button>
                </div>

                <div className="boundary-notice pilot-feedback-boundary" role="note">
                  Feedback is visible to the TPP Product Owner and is used to improve the Pilot.
                  Do not include student names, grades, IEP/504 information, identifiable student
                  work, or other student-specific information.
                </div>

                {status?.preferred_ready && (
                  <p className="pilot-feedback-ready-note" role="status">
                    You have completed the Pilot cycle TPP was waiting for: this week's closeouts
                    and next week's saved planning.
                  </p>
                )}

                <div className="pilot-feedback-grid">
                  <label>
                    Overall, how useful has TPP been for your weekly planning? <span aria-hidden="true">*</span>
                    <select
                      required
                      value={overallUsefulness}
                      onChange={(event) => setOverallUsefulness(event.target.value)}
                    >
                      <option value="">Select</option>
                      <option value="1">1 — Not useful</option>
                      <option value="2">2</option>
                      <option value="3">3 — Mixed</option>
                      <option value="4">4</option>
                      <option value="5">5 — Very useful</option>
                    </select>
                  </label>

                  <label>
                    Compared with your previous process, how has TPP affected the time you spend
                    on weekly planning? <span aria-hidden="true">*</span>
                    <select
                      required
                      value={planningTimeChange}
                      onChange={(event) => setPlanningTimeChange(event.target.value)}
                    >
                      <option value="">Select</option>
                      <option value="much_less">Much less time</option>
                      <option value="somewhat_less">Somewhat less time</option>
                      <option value="about_same">About the same</option>
                      <option value="somewhat_more">Somewhat more time</option>
                      <option value="much_more">Much more time</option>
                    </select>
                  </label>

                  <label className="full-width">
                    What did you appreciate or find most useful? <span aria-hidden="true">*</span>
                    <textarea
                      required
                      rows={3}
                      maxLength={TEXT_LIMIT}
                      value={text.most_useful}
                      onChange={(event) => updateText("most_useful", event.target.value)}
                    />
                    <Counter value={text.most_useful} />
                  </label>

                  <label className="full-width">
                    What was most challenging, confusing, or frustrating? <span aria-hidden="true">*</span>
                    <textarea
                      required
                      rows={3}
                      maxLength={TEXT_LIMIT}
                      value={text.biggest_challenge}
                      onChange={(event) => updateText("biggest_challenge", event.target.value)}
                    />
                    <Counter value={text.biggest_challenge} />
                  </label>

                  <label className="full-width">
                    What did you dislike, or what should we simplify or remove?
                    <span className="optional-label">Optional</span>
                    <textarea
                      rows={3}
                      maxLength={TEXT_LIMIT}
                      value={text.dislike_or_simplify}
                      onChange={(event) => updateText("dislike_or_simplify", event.target.value)}
                    />
                    <Counter value={text.dislike_or_simplify} />
                  </label>

                  <label className="full-width">
                    If we make one improvement before full staff rollout, what should it be?
                    <span aria-hidden="true">*</span>
                    <textarea
                      required
                      rows={3}
                      maxLength={TEXT_LIMIT}
                      value={text.recommended_improvement}
                      onChange={(event) => updateText("recommended_improvement", event.target.value)}
                    />
                    <Counter value={text.recommended_improvement} />
                  </label>

                  <label className="full-width">
                    How ready is TPP for full staff rollout? <span aria-hidden="true">*</span>
                    <select
                      required
                      value={rolloutReadiness}
                      onChange={(event) => setRolloutReadiness(event.target.value)}
                    >
                      <option value="">Select</option>
                      <option value="ready_now">Ready now</option>
                      <option value="ready_minor_fixes">Ready with minor fixes</option>
                      <option value="needs_significant_fixes">Needs significant fixes</option>
                      <option value="not_ready">Not ready</option>
                    </select>
                  </label>
                </div>

                {error && <p className="error-message" role="alert">{error}</p>}
                <div className="pilot-feedback-actions">
                  <button
                    type="button"
                    className="secondary"
                    disabled={working}
                    onClick={() => setDismissed(true)}
                  >
                    Remind me later
                  </button>
                  <button type="submit" className="primary" disabled={working}>
                    {working ? "Submitting…" : "Submit Pilot feedback"}
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      )}

      {isPlatformAdmin && !shouldShowSurvey && !shouldShowThanks && (
        <button
          type="button"
          className="pilot-feedback-owner-button"
          onClick={() => setShowResults(true)}
        >
          Pilot feedback{results.length ? ` (${results.length})` : ""}
        </button>
      )}

      {showResults && isPlatformAdmin && (
        <div className="pilot-feedback-backdrop" role="presentation">
          <section
            className="pilot-feedback-modal pilot-feedback-results"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pilot-feedback-results-title"
          >
            <div className="pilot-feedback-heading">
              <div>
                <p className="eyebrow">Platform Owner</p>
                <h2 id="pilot-feedback-results-title">Pilot feedback</h2>
                <p>Adult professional/product feedback submitted before broader staff rollout.</p>
              </div>
              <button type="button" className="secondary" onClick={() => setShowResults(false)}>
                Close
              </button>
            </div>

            {summary && (
              <div className="pilot-feedback-summary" aria-label="Pilot feedback summary">
                <div><strong>{results.length}</strong><span>responses</span></div>
                <div><strong>{summary.average.toFixed(1)}/5</strong><span>average usefulness</span></div>
                <div>
                  <strong>{summary.timeSaved}/{results.length}</strong>
                  <span>report less planning time</span>
                </div>
                <div>
                  <strong>{summary.rolloutPositive}/{results.length}</strong>
                  <span>ready / minor fixes</span>
                </div>
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
                      <span className="badge">
                        {new Date(item.submitted_at).toLocaleString()}
                      </span>
                    </div>
                    <p>
                      <strong>Usefulness:</strong> {item.overall_usefulness}/5 · <strong>Time:</strong>{" "}
                      {TIME_LABELS[item.planning_time_change] ?? item.planning_time_change} ·{" "}
                      <strong>Rollout:</strong>{" "}
                      {READINESS_LABELS[item.rollout_readiness] ?? item.rollout_readiness}
                    </p>
                    <dl>
                      <div><dt>Most useful</dt><dd>{item.most_useful}</dd></div>
                      <div><dt>Biggest challenge</dt><dd>{item.biggest_challenge}</dd></div>
                      {item.dislike_or_simplify && (
                        <div><dt>Simplify / remove</dt><dd>{item.dislike_or_simplify}</dd></div>
                      )}
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
