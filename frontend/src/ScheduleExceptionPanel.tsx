import { useEffect, useState, type FormEvent } from "react";

export type ScheduleException = {
  id: string;
  teaching_assignment_id: string;
  exception_date: string;
  is_available: boolean;
  instructional_minutes: number | null;
  reason: string;
};

type Props = {
  accessToken: string;
  assignmentId: string;
  weekStart: string;
  disabled?: boolean;
  onChanged: () => void;
  onExceptionsChanged?: (exceptions: ScheduleException[]) => void;
};

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

async function responseDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string };
    return payload.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export function ScheduleExceptionPanel({
  accessToken,
  assignmentId,
  weekStart,
  disabled = false,
  onChanged,
  onExceptionsChanged,
}: Props) {
  const [exceptions, setExceptions] = useState<ScheduleException[]>([]);
  const [exceptionDate, setExceptionDate] = useState(weekStart);
  const [mode, setMode] = useState<"unavailable" | "reduced">("unavailable");
  const [minutes, setMinutes] = useState("30");
  const [reason, setReason] = useState("");
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function loadExceptions() {
    if (!assignmentId) {
      setExceptions([]);
      onExceptionsChanged?.([]);
      return;
    }
    const response = await fetch(
      `/api/v1/schedule-exceptions?assignment_id=${encodeURIComponent(assignmentId)}&week_start=${weekStart}`,
      { headers: { Authorization: `Bearer ${accessToken}` } },
    );
    if (!response.ok) {
      throw new Error(await responseDetail(response, "Schedule exceptions could not be loaded."));
    }
    const loaded = await response.json() as ScheduleException[];
    setExceptions(loaded);
    onExceptionsChanged?.(loaded);
  }

  useEffect(() => {
    setExceptionDate(weekStart);
    setNotice("");
    setError("");
    void loadExceptions().catch((caught) => {
      setError(caught instanceof Error ? caught.message : "Schedule exceptions could not be loaded.");
    });
  }, [assignmentId, weekStart, accessToken]);

  async function saveException(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assignmentId) return;
    setWorking(true);
    setNotice("");
    setError("");
    try {
      let reducedMinutes: number | null = null;
      if (mode === "reduced") {
        const parsedMinutes = Number(minutes);
        if (!Number.isInteger(parsedMinutes) || parsedMinutes < 1) {
          throw new Error("Reduced instructional minutes must be a positive whole number.");
        }
        reducedMinutes = parsedMinutes;
      }
      const response = await fetch(
        `/api/v1/schedule-exceptions/${encodeURIComponent(assignmentId)}/${exceptionDate}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            is_available: mode === "reduced",
            instructional_minutes: reducedMinutes,
            reason: reason.trim(),
          }),
        },
      );
      if (!response.ok) {
        throw new Error(await responseDetail(response, "Schedule exception could not be saved."));
      }
      await loadExceptions();
      setReason("");
      setNotice("Exception saved. Regenerate the week to apply it.");
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Schedule exception could not be saved.");
    } finally {
      setWorking(false);
    }
  }

  async function removeException(exception: ScheduleException) {
    setWorking(true);
    setNotice("");
    setError("");
    try {
      const response = await fetch(
        `/api/v1/schedule-exceptions/${encodeURIComponent(assignmentId)}/${exception.exception_date}`,
        {
          method: "DELETE",
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (!response.ok) {
        throw new Error(await responseDetail(response, "Schedule exception could not be removed."));
      }
      await loadExceptions();
      setNotice("Exception removed. Regenerate the week to restore the normal schedule.");
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Schedule exception could not be removed.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="card">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Schedule adjustment</p>
          <h3>One-time exception</h3>
          <p className="supporting">Use only for this course and week. Regenerate the week after a change.</p>
        </div>
      </div>
      <form className="form-grid" onSubmit={(event) => void saveException(event)}>
        <label>
          Date
          <input
            type="date"
            value={exceptionDate}
            min={weekStart}
            max={addDays(weekStart, 4)}
            required
            onChange={(event) => setExceptionDate(event.target.value)}
          />
        </label>
        <label>
          Adjustment
          <select value={mode} onChange={(event) => setMode(event.target.value as "unavailable" | "reduced")}>
            <option value="unavailable">Day unavailable</option>
            <option value="reduced">Reduced instructional minutes</option>
          </select>
        </label>
        {mode === "reduced" && (
          <label>
            Instructional minutes
            <input
              type="number"
              min="1"
              max="1440"
              value={minutes}
              required
              onChange={(event) => setMinutes(event.target.value)}
            />
          </label>
        )}
        <label className="full-width">
          Reason
          <input
            value={reason}
            maxLength={240}
            required
            placeholder="Testing, rally, shortened schedule, or other instructional change"
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        <div className="form-actions full-width">
          <button className="secondary" disabled={disabled || working || !assignmentId}>Save exception</button>
        </div>
      </form>
      {notice && <p className="status">{notice}</p>}
      {error && <p className="error-message" role="alert">{error}</p>}
      {exceptions.length > 0 && (
        <div className="grid">
          {exceptions.map((exception) => (
            <article className="card" key={exception.id}>
              <strong>{exception.exception_date}</strong>
              <p>{exception.is_available ? `${exception.instructional_minutes ?? 0} instructional minutes` : "Unavailable"}</p>
              <small>{exception.reason}</small>
              <button
                type="button"
                className="link-button"
                disabled={disabled || working}
                onClick={() => void removeException(exception)}
              >
                Remove exception
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
