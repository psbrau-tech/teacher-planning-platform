import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useRef, useState } from "react";
import "./admin-weekly-digest.css";

type Identity = {
  id: string;
  email: string;
  display_name: string;
  school_id: string;
  roles: string[];
};

type DigestResult = {
  week_start: string;
  status: "sent";
  recipient_scope: "requesting-admin";
  content_boundary: "counts-and-authenticated-link-only";
  metrics: {
    configured_assignments: number;
    lesson_plans_submitted: number;
    lesson_plans_missing: number;
    completed_packets_submitted: number;
    completed_packets_missing: number;
    teachers_with_completed_packets: number;
    plc_brief_available: boolean;
  };
};

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const digestSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

function currentMonday(): string {
  const date = new Date();
  const day = date.getDay();
  const offset = day === 0 ? -6 : 1 - day;
  date.setDate(date.getDate() + offset);
  return date.toISOString().slice(0, 10);
}

async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;
  } catch {
    // Use the bounded fallback below.
  }
  return "The weekly admin digest could not be sent.";
}

export function AdminWeeklyDigestAction() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [open, setOpen] = useState(false);
  const [weekStart, setWeekStart] = useState(currentMonday());
  const [working, setWorking] = useState(false);
  const [result, setResult] = useState<DigestResult | null>(null);
  const [error, setError] = useState("");
  const closeButton = useRef<HTMLButtonElement>(null);
  const triggerButton = useRef<HTMLButtonElement>(null);

  const accessToken = session?.access_token ?? "";
  const canSend = identity?.roles.some((role) => (
    role === "school_admin" || role === "district_admin" || role === "platform_admin"
  )) ?? false;

  useEffect(() => {
    if (!digestSupabase) return;
    void digestSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = digestSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setOpen(false);
      setResult(null);
      setError("");
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!accessToken) return;
    let active = true;
    void fetch("/api/v1/session", {
      headers: { Authorization: `Bearer ${accessToken}` },
    }).then(async (response) => {
      if (!active || !response.ok) return;
      setIdentity(await response.json() as Identity);
    });
    return () => { active = false; };
  }, [accessToken]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => closeButton.current?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      window.requestAnimationFrame(() => triggerButton.current?.focus());
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function sendDigest() {
    setWorking(true);
    setResult(null);
    setError("");
    try {
      const response = await fetch(
        `/api/v1/notifications/admin-weekly-digest/${encodeURIComponent(weekStart)}`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setResult(await response.json() as DigestResult);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The weekly admin digest could not be sent.");
    } finally {
      setWorking(false);
    }
  }

  function closePanel() {
    setOpen(false);
    window.requestAnimationFrame(() => triggerButton.current?.focus());
  }

  if (!digestSupabase || !accessToken || !identity || !canSend) return null;

  return (
    <>
      <button
        ref={triggerButton}
        type="button"
        className="admin-digest-launcher"
        aria-expanded={open}
        aria-controls="admin-weekly-digest-panel"
        onClick={() => {
          setOpen((current) => !current);
          setError("");
          setResult(null);
        }}
      >
        Weekly admin email
      </button>

      {open ? (
        <aside
          id="admin-weekly-digest-panel"
          className="admin-digest-panel"
          aria-labelledby="admin-weekly-digest-title"
        >
          <header className="admin-digest-header">
            <div>
              <p className="admin-digest-eyebrow">School operations</p>
              <h2 id="admin-weekly-digest-title">Email my weekly TPP digest</h2>
            </div>
            <button ref={closeButton} type="button" onClick={closePanel}>Close</button>
          </header>

          <p>
            TPP sends the digest only to your authenticated TPP account email. The message contains
            school-level submission counts and a link back to TPP; it does not include teacher names,
            reflection text, generated instructional insight, student data, or teacher-quality scores.
          </p>

          <label className="admin-digest-week">
            Week of
            <input
              type="date"
              value={weekStart}
              onChange={(event) => {
                setWeekStart(event.target.value);
                setResult(null);
                setError("");
              }}
            />
          </label>

          <button
            type="button"
            className="admin-digest-primary"
            disabled={working}
            onClick={() => void sendDigest()}
          >
            {working ? "Sending digest…" : "Email digest to my TPP account"}
          </button>

          {result ? (
            <div className="admin-digest-success" role="status">
              <strong>Weekly digest sent.</strong>
              <span>
                {` ${result.metrics.lesson_plans_submitted} lesson plans and ${result.metrics.completed_packets_submitted} completed Friday packets are submitted for this week.`}
              </span>
              {result.metrics.plc_brief_available ? (
                <span> A school PLC reflection brief is also available to generate in TPP.</span>
              ) : null}
            </div>
          ) : null}

          {error ? <p className="admin-digest-error" role="alert">{error}</p> : null}
        </aside>
      ) : null}
    </>
  );
}
