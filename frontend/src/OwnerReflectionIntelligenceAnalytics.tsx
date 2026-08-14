import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import "./owner-reflection-intelligence.css";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const ownerReflectionSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

type Identity = {
  id: string;
  roles: string[];
};

type ReflectionUsage = {
  period_start: string;
  period_end: string;
  teacher_recaps_generated: number;
  teacher_recap_users: number;
  school_plc_briefs_generated: number;
  plc_brief_users: number;
  plc_handouts_viewed: number;
  plc_handout_users: number;
};

type NotificationUsage = {
  period_start: string;
  period_end: string;
  admin_weekly_digests_sent: number;
  admin_digest_senders: number;
};

type PeriodKind = "current_week" | "last_4_weeks" | "release_to_date" | "custom";

function localIsoDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T12:00:00`);
  date.setDate(date.getDate() + days);
  return localIsoDate(date);
}

function mondayFor(date = new Date()): string {
  const copy = new Date(date);
  const day = copy.getDay();
  copy.setDate(copy.getDate() + (day === 0 ? -6 : 1 - day));
  return localIsoDate(copy);
}

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

function Metric({
  value,
  label,
  detail,
}: {
  value: number;
  label: string;
  detail: string;
}) {
  return (
    <div className="owner-metric">
      <strong>{value}</strong>
      <span>{label}</span>
      <small>{detail}</small>
    </div>
  );
}

export function OwnerReflectionIntelligenceAnalytics() {
  const [session, setSession] = useState<Session | null>(null);
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [portalTarget, setPortalTarget] = useState<Element | null>(null);
  const [periodKind, setPeriodKind] = useState<PeriodKind>("release_to_date");
  const [customStart, setCustomStart] = useState("2026-08-14");
  const [customEnd, setCustomEnd] = useState(localIsoDate());
  const [reflectionUsage, setReflectionUsage] = useState<ReflectionUsage | null>(null);
  const [notificationUsage, setNotificationUsage] = useState<NotificationUsage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isPlatformAdmin = identity?.roles.includes("platform_admin") ?? false;
  const currentMonday = mondayFor();
  const today = localIsoDate();
  const period = useMemo(() => {
    if (periodKind === "current_week") {
      return { start: currentMonday, end: addDays(currentMonday, 6), label: "Current week" };
    }
    if (periodKind === "last_4_weeks") {
      return { start: addDays(currentMonday, -21), end: addDays(currentMonday, 6), label: "Last 4 weeks" };
    }
    if (periodKind === "custom") {
      return { start: customStart, end: customEnd, label: "Custom period" };
    }
    return { start: "2026-08-14", end: today, label: "Reflection Intelligence release to date" };
  }, [currentMonday, customEnd, customStart, periodKind, today]);

  useEffect(() => {
    if (!ownerReflectionSupabase) return;
    void ownerReflectionSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = ownerReflectionSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setIdentity(null);
      setReflectionUsage(null);
      setNotificationUsage(null);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session?.access_token) return;
    let active = true;
    void fetch("/api/v1/session", {
      headers: { Authorization: `Bearer ${session.access_token}` },
    }).then(async (response) => {
      if (response.ok && active) setIdentity(await response.json() as Identity);
    });
    return () => { active = false; };
  }, [session?.access_token]);

  useEffect(() => {
    const updateTarget = () => setPortalTarget(document.querySelector(".owner-tab"));
    updateTarget();
    const observer = new MutationObserver(updateTarget);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!session?.access_token || !isPlatformAdmin || !portalTarget || !period.start || !period.end) {
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    const query = new URLSearchParams({ period_start: period.start, period_end: period.end });
    void Promise.all([
      fetch(`/api/v1/reflection-intelligence/usage?${query.toString()}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      }),
      fetch(`/api/v1/notifications/usage?${query.toString()}`, {
        headers: { Authorization: `Bearer ${session.access_token}` },
      }),
    ]).then(async ([reflectionResponse, notificationResponse]) => {
      if (!reflectionResponse.ok) {
        throw new Error(await readError(
          reflectionResponse,
          "Reflection Intelligence adoption reporting could not be loaded.",
        ));
      }
      if (!notificationResponse.ok) {
        throw new Error(await readError(
          notificationResponse,
          "Notification adoption reporting could not be loaded.",
        ));
      }
      const [nextReflectionUsage, nextNotificationUsage] = await Promise.all([
        reflectionResponse.json() as Promise<ReflectionUsage>,
        notificationResponse.json() as Promise<NotificationUsage>,
      ]);
      if (active) {
        setReflectionUsage(nextReflectionUsage);
        setNotificationUsage(nextNotificationUsage);
      }
    }).catch((caught: unknown) => {
      if (active) {
        setReflectionUsage(null);
        setNotificationUsage(null);
        setError(caught instanceof Error
          ? caught.message
          : "Reflection Intelligence adoption reporting could not be loaded.");
      }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [isPlatformAdmin, period.end, period.start, portalTarget, session?.access_token]);

  const signals = useMemo(() => {
    if (!reflectionUsage || !notificationUsage) return [] as string[];
    const items: string[] = [];
    if (reflectionUsage.teacher_recaps_generated) {
      items.push(
        `${reflectionUsage.teacher_recap_users} teacher${reflectionUsage.teacher_recap_users === 1 ? " has" : "s have"} generated ${reflectionUsage.teacher_recaps_generated} private recap${reflectionUsage.teacher_recaps_generated === 1 ? "" : "s"}.`,
      );
    }
    if (reflectionUsage.school_plc_briefs_generated) {
      items.push(
        `${reflectionUsage.plc_brief_users} authorized administrator${reflectionUsage.plc_brief_users === 1 ? " has" : "s have"} generated ${reflectionUsage.school_plc_briefs_generated} school PLC brief${reflectionUsage.school_plc_briefs_generated === 1 ? "" : "s"}.`,
      );
    }
    if (reflectionUsage.plc_handouts_viewed) {
      items.push(
        `${reflectionUsage.plc_handouts_viewed} PLC handout view/print event${reflectionUsage.plc_handouts_viewed === 1 ? " is" : "s are"} recorded across ${reflectionUsage.plc_handout_users} authorized user${reflectionUsage.plc_handout_users === 1 ? "" : "s"}.`,
      );
    }
    if (notificationUsage.admin_weekly_digests_sent) {
      items.push(
        `${notificationUsage.admin_weekly_digests_sent} minimized weekly admin digest${notificationUsage.admin_weekly_digests_sent === 1 ? " has" : "s have"} been sent by ${notificationUsage.admin_digest_senders} administrator${notificationUsage.admin_digest_senders === 1 ? "" : "s"}.`,
      );
    }
    return items;
  }, [notificationUsage, reflectionUsage]);

  if (!portalTarget || !session || !isPlatformAdmin) return null;

  return createPortal(
    <section
      className="owner-section owner-reflection-intelligence"
      aria-label="Reflection Intelligence adoption analytics"
    >
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Reflection Intelligence adoption</p>
          <h3>Are the new professional-learning features being used?</h3>
          <p className="supporting">
            Platform Owner only. These are product-adoption signals for private recaps, aggregate PLC
            briefs, handout use, and minimized admin email delivery. They are not teacher performance,
            quality, effort, or productivity measures, and they contain no reflection text or student data.
          </p>
        </div>
      </div>

      <div className="owner-period-control">
        <label>
          Reporting period
          <select
            value={periodKind}
            onChange={(event) => setPeriodKind(event.target.value as PeriodKind)}
          >
            <option value="release_to_date">Reflection Intelligence release to date</option>
            <option value="current_week">Current week</option>
            <option value="last_4_weeks">Last 4 weeks</option>
            <option value="custom">Custom dates</option>
          </select>
        </label>
        {periodKind === "custom" ? (
          <>
            <label>
              Start
              <input
                type="date"
                value={customStart}
                onChange={(event) => setCustomStart(event.target.value)}
              />
            </label>
            <label>
              End
              <input
                type="date"
                value={customEnd}
                onChange={(event) => setCustomEnd(event.target.value)}
              />
            </label>
          </>
        ) : null}
        <span className="owner-period-label">
          {period.label}: {period.start} through {period.end}
        </span>
      </div>

      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {loading ? <p className="working-status" role="status">Updating adoption analytics…</p> : null}

      {reflectionUsage && notificationUsage && !loading ? (
        <>
          <div className="owner-summary-grid ri-owner-grid">
            <Metric
              value={reflectionUsage.teacher_recaps_generated}
              label="private teacher recaps"
              detail={`${reflectionUsage.teacher_recap_users} distinct teacher users`}
            />
            <Metric
              value={reflectionUsage.school_plc_briefs_generated}
              label="school PLC briefs"
              detail={`${reflectionUsage.plc_brief_users} distinct authorized users`}
            />
            <Metric
              value={reflectionUsage.plc_handouts_viewed}
              label="PLC handout uses"
              detail={`${reflectionUsage.plc_handout_users} distinct authorized users`}
            />
            <Metric
              value={notificationUsage.admin_weekly_digests_sent}
              label="admin weekly digests sent"
              detail={`${notificationUsage.admin_digest_senders} distinct admin senders`}
            />
          </div>

          <div className="ri-owner-signals" aria-label="Adoption signals">
            <h4>What the usage is telling us</h4>
            {signals.length ? (
              <ul>{signals.map((signal) => <li key={signal}>{signal}</li>)}</ul>
            ) : (
              <p>
                No Reflection Intelligence adoption events are recorded in this period yet. That is a
                product-usage result, not a judgment about teacher or administrator performance.
              </p>
            )}
          </div>

          <p className="guidance-text">
            Use these counts to decide whether the feature is discoverable and useful enough to keep,
            improve, or simplify. Do not use them to rank staff, infer instructional quality, or create
            participation expectations that are not separately established by school leadership.
          </p>
        </>
      ) : null}
    </section>,
    portalTarget,
  );
}
