import { createClient, type Session } from "@supabase/supabase-js";
import { useEffect, useRef, useState } from "react";
import type { ProductUsageEventKey } from "./productUsage";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? "";
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? "";
const usageSupabase = supabaseUrl && supabaseAnonKey
  ? createClient(supabaseUrl, supabaseAnonKey, {
      auth: { persistSession: true, autoRefreshToken: false, detectSessionInUrl: false },
    })
  : null;

const PENDING_WINDOW_MS = 20_000;

type PendingAction = {
  key: "curriculum_upload" | "curriculum_build" | "curriculum_reuse" | "lesson_pdf" | "packet_pdf";
  at: number;
};

function requestUrl(input: RequestInfo | URL): URL | null {
  try {
    if (input instanceof Request) return new URL(input.url, window.location.origin);
    return new URL(String(input), window.location.origin);
  } catch {
    return null;
  }
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase();
  if (input instanceof Request) return input.method.toUpperCase();
  return "GET";
}

function buttonText(target: EventTarget | null): { button: HTMLButtonElement; text: string } | null {
  if (!(target instanceof Element)) return null;
  const button = target.closest("button");
  if (!(button instanceof HTMLButtonElement) || button.disabled) return null;
  return { button, text: (button.textContent ?? "").replace(/\s+/g, " ").trim() };
}

export function ProductUsageObserver() {
  const [session, setSession] = useState<Session | null>(null);
  const tokenRef = useRef("");
  const pendingRef = useRef<PendingAction | null>(null);

  useEffect(() => {
    tokenRef.current = session?.access_token ?? "";
  }, [session?.access_token]);

  useEffect(() => {
    if (!usageSupabase) return;
    void usageSupabase.auth.getSession().then(({ data }) => setSession(data.session));
    const { data } = usageSupabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });
    return () => data.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const originalFetch = window.fetch.bind(window);

    const record = (eventKey: ProductUsageEventKey) => {
      const token = tokenRef.current;
      if (!token) return;
      void originalFetch("/api/v1/product-usage", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ event_key: eventKey }),
      }).catch(() => {
        // Passive Product Owner telemetry must never interrupt teacher work.
      });
    };

    const pending = (key: PendingAction["key"]): boolean => {
      const current = pendingRef.current;
      if (!current || current.key !== key) return false;
      if (Date.now() - current.at > PENDING_WINDOW_MS) {
        pendingRef.current = null;
        return false;
      }
      pendingRef.current = null;
      return true;
    };

    const onClick = (event: MouseEvent) => {
      const clicked = buttonText(event.target);
      if (!clicked) return;
      const { button, text } = clicked;

      if (text === "Save Curriculum & Pacing & Continue") {
        const step = button.closest(".setup-step-card");
        const selectedMode = step?.querySelector(".choice-card.selected strong")?.textContent?.trim();
        if (selectedMode === "Upload Excel") {
          pendingRef.current = { key: "curriculum_upload", at: Date.now() };
        } else if (selectedMode === "Build in TPP") {
          pendingRef.current = { key: "curriculum_build", at: Date.now() };
        }
        return;
      }

      if (text === "Use this curriculum & continue") {
        pendingRef.current = { key: "curriculum_reuse", at: Date.now() };
        return;
      }

      const context = button.closest("section")?.textContent ?? "";
      if (text === "View PDF" && context.includes("Weekly Lesson Plan")) {
        pendingRef.current = { key: "lesson_pdf", at: Date.now() };
        return;
      }
      if ((text === "View completed packet" || text === "View packet") && context.includes("Completed Weekly Packet")) {
        pendingRef.current = { key: "packet_pdf", at: Date.now() };
      }
    };

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      const response = await originalFetch(input, init);
      if (!response.ok || !url || url.origin !== window.location.origin) return response;

      const path = url.pathname;
      if (method === "POST" && path === "/api/v1/curricula") {
        if (pending("curriculum_upload")) record("curriculum_excel_saved");
        else if (pending("curriculum_build")) record("curriculum_builder_saved");
      } else if (
        method === "PUT"
        && /^\/api\/v1\/teaching-assignments\/[^/]+$/.test(path)
        && pending("curriculum_reuse")
      ) {
        record("curriculum_reused");
      } else if (method === "POST" && /^\/api\/v1\/curricula\/[^/]+\/copy$/.test(path)) {
        record("curriculum_copy_created");
      } else if (method === "GET" && /^\/api\/v1\/curricula\/[^/]+\/export\.xlsx$/.test(path)) {
        record("curriculum_exported");
      } else if (method === "POST" && path === "/api/v1/plans/generate") {
        record("weekly_plan_generated");
      } else if (
        method === "POST"
        && path === "/api/v1/documents/anniston-lesson-plan-packet"
        && pending("lesson_pdf")
      ) {
        record("lesson_plan_pdf_viewed");
      } else if (
        method === "GET"
        && /^\/api\/v1\/teacher-submissions\/[^/]+\/completed-packet$/.test(path)
        && pending("packet_pdf")
      ) {
        record("completed_packet_viewed");
      }
      return response;
    };

    document.addEventListener("click", onClick, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      window.fetch = originalFetch;
    };
  }, []);

  return null;
}
