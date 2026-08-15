import { useEffect } from "react";
import "./ui-consistency.css";

const TOAST_DISMISS_MS = 5000;

export function UiConsistencyExperience() {
  useEffect(() => {
    const scheduled = new WeakSet<Element>();
    const timers = new Set<number>();

    const scheduleVisibleToasts = () => {
      document.querySelectorAll<HTMLElement>(".toast-alert").forEach((toast) => {
        if (scheduled.has(toast)) return;
        scheduled.add(toast);
        const timer = window.setTimeout(() => {
          timers.delete(timer);
          if (!toast.isConnected) return;
          toast.querySelector<HTMLButtonElement>('button[aria-label="Dismiss"]')?.click();
        }, TOAST_DISMISS_MS);
        timers.add(timer);
      });
    };

    scheduleVisibleToasts();
    const observer = new MutationObserver(scheduleVisibleToasts);
    observer.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      timers.forEach((timer) => window.clearTimeout(timer));
      timers.clear();
    };
  }, []);

  return null;
}
