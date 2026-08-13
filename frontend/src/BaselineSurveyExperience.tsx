import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import "./baseline-survey.css";

type Identity = {
  id: string;
  roles: string[];
};

type BaselineStatus = {
  survey_key: string;
  eligible: boolean;
  available: boolean;
  submitted: boolean;
  submitted_at: string | null;
};

const COMMENT_LIMIT = 1000;
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const baselineSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

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

export function BaselineSurveyExperience() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [status, setStatus] = useState<BaselineStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [planningTime, setPlanningTime] = useState("");
  const [planUsefulness, setPlanUsefulness] = useState("");
  const [submissionBurden, setSubmissionBurden] = useState("");
  const [reflectionReview, setReflectionReview] = useState("");
  const [plcUse, setPlcUse] = useState("");
  const [biggestBurden, setBiggestBurden] = useState("");

  const accessToken = session?.access_token ?? "";
  const isTeacher = identity?.roles.includes("teacher") ?? false;
  const shouldShow = Boolean(
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
    const response = await authenticatedFetch("/api/v1/baseline/status");
    if (!response.ok) return;
    setStatus(await response.json() as BaselineStatus);
  }

  useEffect(() => {
    if (!baselineSupabase) return;
    void baselineSupabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      if (data.session) void loadIdentity(data.session);
    });
    const { data } = baselineSupabase.auth.onAuthStateChange((_event, nextSession) => {
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
  }, [accessToken, identity?.id, isTeacher, dismissed, submitted]);

  async function submitBaseline(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!planningTime || !planUsefulness || !submissionBurden || !reflectionReview || !plcUse) {
      setError("Complete the five baseline questions before submitting.");
      return;
    }
    setWorking(true);
    setError("");
    try {
      const response = await authenticatedFetch("/api/v1/baseline", {
        method: "POST",
        body: JSON.stringify({
          planning_time_before: planningTime,
          plan_usefulness_before: Number(planUsefulness),
          submission_burden_before: Number(submissionBurden),
          reflection_review_frequency_before: reflectionReview,
          plc_use_frequency_before: plcUse,
          biggest_burden_before: biggestBurden,
        }),
      });
      if (!response.ok) {
        throw new Error(await readError(response, "Your baseline could not be submitted."));
      }
      setSubmitted(true);
      setStatus((current) => current
        ? { ...current, submitted: true, available: false }
        : current);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Your baseline could not be submitted.");
    } finally {
      setWorking(false);
    }
  }

  if (!baselineSupabase || !session || !identity || (!shouldShow && !shouldShowThanks)) return null;

  return (
    <div className="baseline-backdrop" role="presentation">
      <section
        className="baseline-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="baseline-title"
      >
        {shouldShowThanks ? (
          <div className="baseline-thanks">
            <p className="eyebrow">Teacher baseline</p>
            <h2 id="baseline-title">Thank you.</h2>
            <p>Your pre-TPP baseline has been recorded. You will not be asked to complete it again.</p>
            <button className="primary" type="button" onClick={() => setDismissed(true)}>
              Continue to TPP
            </button>
          </div>
        ) : (
          <form onSubmit={(event) => void submitBaseline(event)}>
            <div className="baseline-heading">
              <div>
                <p className="eyebrow">One-time teacher baseline</p>
                <h2 id="baseline-title">Think about your planning process before TPP</h2>
                <p>This should take about 60–90 seconds and helps us measure whether TPP actually reduces workload and makes planning more useful.</p>
              </div>
            </div>

            <div className="baseline-prior-note" role="note">
              <strong>Please answer about your normal experience before you began using TPP.</strong>
              <span>Even if you have already used TPP this week, answer these questions based on how lesson planning, submission, and reflection usually worked for you before TPP.</span>
            </div>

            <div className="boundary-notice baseline-boundary" role="note">
              This survey is about your professional planning process. Do not include student names,
              grades, IEP/504 information, identifiable student work, or other student-specific information.
            </div>

            <div className="baseline-grid">
              <label>
                Before TPP, about how much time did you usually spend each week preparing and submitting lesson plans?
                <select required value={planningTime} onChange={(event) => setPlanningTime(event.target.value)}>
                  <option value="">Select</option>
                  <option value="under_30">Less than 30 minutes</option>
                  <option value="30_60">30–60 minutes</option>
                  <option value="61_120">61–120 minutes</option>
                  <option value="121_180">121–180 minutes</option>
                  <option value="over_180">More than 3 hours</option>
                  <option value="not_sure">Not sure</option>
                </select>
              </label>

              <label>
                Before TPP, how useful were your completed lesson plans to your actual teaching?
                <select required value={planUsefulness} onChange={(event) => setPlanUsefulness(event.target.value)}>
                  <option value="">Select</option>
                  <option value="1">1 — Not useful</option>
                  <option value="2">2</option>
                  <option value="3">3 — Somewhat useful</option>
                  <option value="4">4</option>
                  <option value="5">5 — Very useful</option>
                </select>
              </label>

              <label>
                Before TPP, how burdensome did the required lesson-planning and submission process feel?
                <select required value={submissionBurden} onChange={(event) => setSubmissionBurden(event.target.value)}>
                  <option value="">Select</option>
                  <option value="1">1 — Very little burden</option>
                  <option value="2">2</option>
                  <option value="3">3 — Moderate</option>
                  <option value="4">4</option>
                  <option value="5">5 — Very burdensome</option>
                </select>
              </label>

              <label>
                Before TPP, how often did you look back at previous weekly reflections?
                <select required value={reflectionReview} onChange={(event) => setReflectionReview(event.target.value)}>
                  <option value="">Select</option>
                  <option value="never">Never</option>
                  <option value="rarely">Rarely</option>
                  <option value="sometimes">Sometimes</option>
                  <option value="often">Often</option>
                  <option value="very_often">Very often</option>
                </select>
              </label>

              <label className="full-width">
                Before TPP, how often did lesson plans or reflections contribute to instructional discussion in PLC or faculty meetings?
                <select required value={plcUse} onChange={(event) => setPlcUse(event.target.value)}>
                  <option value="">Select</option>
                  <option value="never">Never</option>
                  <option value="rarely">Rarely</option>
                  <option value="sometimes">Sometimes</option>
                  <option value="often">Often</option>
                  <option value="very_often">Very often</option>
                </select>
              </label>

              <label className="full-width">
                Before TPP, what part of weekly planning or submission took the most time or created the most frustration?
                <span className="optional-label">Optional</span>
                <textarea
                  rows={2}
                  maxLength={COMMENT_LIMIT}
                  value={biggestBurden}
                  onChange={(event) => setBiggestBurden(event.target.value)}
                />
                <small>{COMMENT_LIMIT - biggestBurden.length} characters remaining</small>
              </label>
            </div>

            {error && <p className="error-message" role="alert">{error}</p>}
            <div className="baseline-actions">
              <button
                type="button"
                className="secondary"
                disabled={working}
                onClick={() => setDismissed(true)}
              >
                Continue for now
              </button>
              <button type="submit" className="primary" disabled={working}>
                {working ? "Saving…" : "Save my baseline"}
              </button>
            </div>
            <p className="baseline-reminder-note">If you continue for now, TPP will ask again the next time you sign in until the one-time baseline is completed.</p>
          </form>
        )}
      </section>
    </div>
  );
}
