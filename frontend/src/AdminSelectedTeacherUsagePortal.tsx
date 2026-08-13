import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AdminSelectedTeacherUsageReport } from "./AdminSelectedTeacherUsageReport";
import "./admin-selected-teacher-usage.css";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const adminReportSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

export function AdminSelectedTeacherUsagePortal() {
  const [session, setSession] = useState<Session | null>(null);
  const [portalTarget, setPortalTarget] = useState<Element | null>(null);

  useEffect(() => {
    if (!adminReportSupabase) return;
    void adminReportSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = adminReportSupabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession));
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const updateTarget = () => {
      const panel = document.querySelector('[role="tabpanel"][aria-label="Administration reporting"]');
      if (!panel) {
        setPortalTarget(null);
        return;
      }
      let slot = panel.querySelector(".admin-selected-usage-slot");
      if (!slot) {
        slot = document.createElement("div");
        slot.className = "admin-selected-usage-slot";
        const oldPeriodControl = panel.querySelector(".report-period-control");
        panel.insertBefore(slot, oldPeriodControl ?? panel.firstChild);
      }
      setPortalTarget(slot);
    };
    updateTarget();
    const observer = new MutationObserver(updateTarget);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  if (!session?.access_token || !portalTarget) return null;
  return createPortal(
    <AdminSelectedTeacherUsageReport accessToken={session.access_token} />,
    portalTarget,
  );
}
