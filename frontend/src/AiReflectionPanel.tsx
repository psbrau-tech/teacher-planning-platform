import { useEffect, useMemo, useState } from "react";

type AiReflectionPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  disabled?: boolean;
  onApplyReflection: (value: string) => void;
};

type ReflectionFields = Record<string, string>;

type WeeklyDraftRead = {
  content: Record<string, string>;
};

const REFLECTION_PROMPTS = [
  "What knowledge has been building this week?",
  "What understandings are being developed?",
  "What evidence is demonstrating mastery?",
  "What misconceptions emerged?",
  "What standard(s) or parts of the standard need reteaching?",
  "Which students need intervention?",
  "What is the plan for intervention (Tier 2 and Tier 3)?",
  "Which students need enrichment?",
  "What is the plan for enrichment?",
  "Which instructional moves worked?",
  "What instructional adjustments will I make next week?",
  "What are next week's instructional priorities?",
] as const;

function emptyReflection(): ReflectionFields {
  return Object.fromEntries(REFLECTION_PROMPTS.map((_prompt, index) => [`reflect_${index + 1}`, ""]));
}

function parseReflection(value: string | undefined): ReflectionFields {
  if (!value) return emptyReflection();
  try {
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return emptyReflection();
    const source = parsed as Record<string, unknown>;
    return Object.fromEntries(REFLECTION_PROMPTS.map((_prompt, index) => {
      const key = `reflect_${index + 1}`;
      return [key, typeof source[key] === "string" ? source[key] : ""];
    }));
  } catch {
    return emptyReflection();
  }
}

async function responseDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    return typeof body.detail === "string" && body.detail.trim() ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

export function AiReflectionPanel({
  accessToken,
  assignmentId,
  weekStart,
  disabled = false,
  onApplyReflection,
}: AiReflectionPanelProps) {
  const [responses, setResponses] = useState<ReflectionFields>(emptyReflection);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [previewWorking, setPreviewWorking] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setResponses(emptyReflection());
    setMessage(null);
    if (!accessToken || !assignmentId || !weekStart) return () => { active = false; };

    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/v1/weekly-drafts?assignment_id=${encodeURIComponent(assignmentId)}&week_start=${encodeURIComponent(weekStart)}`,
          { headers: { Authorization: `Bearer ${accessToken}` } },
        );
        if (!response.ok) return;
        const draft = await response.json() as WeeklyDraftRead;
        if (!active) return;
        setResponses(parseReflection(draft.content.reflection));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [accessToken, assignmentId, weekStart]);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const answeredCount = useMemo(
    () => REFLECTION_PROMPTS.filter((_prompt, index) => (responses[`reflect_${index + 1}`] ?? "").length > 0).length,
    [responses],
  );

  const updateResponse = (key: string, value: string) => {
    setResponses((current) => {
      const next = { ...current, [key]: value };
      onApplyReflection(JSON.stringify(next));
      return next;
    });
    setMessage("Reflection updated in the working plan. Save the Friday closeout to keep your changes.");
  };

  async function viewSavedReflection() {
    if (!assignmentId || !accessToken) return;
    setPreviewWorking(true);
    setPreviewError(null);
    try {
      const draftResponse = await fetch(
        `/api/v1/weekly-drafts?assignment_id=${encodeURIComponent(assignmentId)}&week_start=${encodeURIComponent(weekStart)}`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!draftResponse.ok) throw new Error(await responseDetail(draftResponse, "Save the Friday closeout before previewing the reflection PDF."));
      const saved = await draftResponse.json() as WeeklyDraftRead;
      if (!saved.content.reflection?.trim()) throw new Error("Save the Friday closeout before previewing the reflection PDF.");
      const pdfResponse = await fetch("/api/v1/documents/anniston-hqi/weekly-reflection", {
        method: "POST",
        headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
        body: JSON.stringify(saved.content),
      });
      if (!pdfResponse.ok) throw new Error(await responseDetail(pdfResponse, "The reflection PDF could not be generated."));
      const blob = await pdfResponse.blob();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(blob));
    } catch (caught) {
      setPreviewError(caught instanceof Error ? caught.message : "The reflection PDF could not be generated.");
    } finally {
      setPreviewWorking(false);
    }
  }

  function closePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  }

  return (
    <section className="panel ai-reflection-panel" aria-labelledby="weekly-reflection-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Required teacher reflection</p>
          <h2 id="weekly-reflection-heading">Weekly Reflection / PLC Discussion</h2>
          <p className="supporting">
            This reflection is your professional judgment. TPP does not generate or rewrite these responses.
          </p>
        </div>
        <span className="badge">{answeredCount} of {REFLECTION_PROMPTS.length} completed</span>
      </div>

      <div className="guidance-card" role="note" aria-label="Reflection data boundary">
        <strong>Use class- or group-level observations only.</strong>
        <p>
          Do not enter student names, identifiers, grades, identifiable student work, IEP/504,
          health, discipline, or other student-specific information. For intervention and enrichment
          prompts, describe groups or instructional needs rather than individual students.
        </p>
      </div>

      {!assignmentId ? <p>Select a course before completing the reflection.</p> : null}
      {loading ? <p>Loading saved reflection…</p> : null}

      <div className="reflection-question-list">
        {REFLECTION_PROMPTS.map((prompt, index) => {
          const key = `reflect_${index + 1}`;
          return (
            <label className="reflection-question" key={key}>
              <span><strong>{index + 1}.</strong> {prompt}</span>
              {(index === 5 || index === 7) ? (
                <small>Respond at the class or group level. Do not identify individual students.</small>
              ) : null}
              <textarea
                rows={4}
                value={responses[key] ?? ""}
                disabled={disabled}
                required
                onChange={(event) => updateResponse(key, event.target.value)}
              />
            </label>
          );
        })}
      </div>

      {disabled ? (
        <p className="guidance-text">Complete Friday validation before entering the required weekly reflection.</p>
      ) : (
        <>
          <p className="guidance-text">
            All 12 district prompts are required for the normal weekly closeout. TPP does not evaluate the substance of your response.
          </p>
          <div className="button-row">
            <button type="button" className="secondary" disabled={previewWorking} onClick={() => void viewSavedReflection()}>
              {previewWorking ? "Preparing reflection…" : "View saved reflection PDF"}
            </button>
          </div>
        </>
      )}
      {previewError ? <p className="error-message" role="alert">{previewError}</p> : null}
      {message ? <p className="success-message" role="status">{message}</p> : null}
      {previewUrl ? (
        <div className="pdf-modal-backdrop" role="presentation">
          <section className="pdf-modal" role="dialog" aria-modal="true" aria-label="Weekly Reflection PDF preview">
            <div className="pdf-modal-header"><h3>Weekly Reflection / PLC Discussion</h3><button type="button" className="secondary" onClick={closePreview}>Close preview</button></div>
            <iframe className="pdf-preview-frame" src={previewUrl} title="Weekly Reflection / PLC Discussion PDF" />
          </section>
        </div>
      ) : null}
    </section>
  );
}
