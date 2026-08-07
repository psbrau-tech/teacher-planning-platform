import { useEffect, useMemo, useState } from "react";

type StandardSource = {
  id: string;
  source_key: string;
  authority: string;
  title: string;
  edition: string;
  landing_url: string;
  snapshot_id: string;
  source_version: string | null;
  retrieved_at: string;
  resolved_document_url: string;
};

type StandardCourse = {
  id: string;
  source_id: string;
  course_key: string;
  display_name: string;
  source_course_code: string | null;
  grade_band: string | null;
  is_pilot_allowed: boolean;
};

export type StandardEntry = {
  id: string;
  code: string;
  text: string;
  parent_code: string | null;
  strand: string | null;
  sequence: number;
};

type AssignmentStandards = {
  assignment_id: string;
  week_start: string;
  mapped: boolean;
  source: StandardSource | null;
  course: StandardCourse | null;
  standards: StandardEntry[];
  selected_entry_ids: string[];
};

type StandardsPanelProps = {
  assignmentId: string | null;
  weekStart: string;
  onSelectionSaved?: (selected: StandardEntry[]) => void;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
  } catch {
    // Preserve the bounded fallback rather than surfacing raw response text.
  }
  return fallback;
}

export function StandardsPanel({
  assignmentId,
  weekStart,
  onSelectionSaved,
}: StandardsPanelProps) {
  const [catalog, setCatalog] = useState<AssignmentStandards | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setCatalog(null);
    setSelected(new Set());
    setMessage(null);
    setError(null);

    if (!assignmentId || !weekStart) {
      return () => {
        active = false;
      };
    }

    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}` +
            `?week_start=${encodeURIComponent(weekStart)}`,
        );
        if (!response.ok) {
          throw new Error(await readError(response, "Standards could not be loaded."));
        }
        const body = (await response.json()) as AssignmentStandards;
        if (!active) return;
        setCatalog(body);
        setSelected(new Set(body.selected_entry_ids));
      } catch (caught) {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Standards could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    return () => {
      active = false;
    };
  }, [assignmentId, weekStart]);

  const selectedEntries = useMemo(() => {
    if (!catalog) return [];
    return catalog.standards.filter((standard) => selected.has(standard.id));
  }, [catalog, selected]);

  const toggle = (standardId: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(standardId)) {
        next.delete(standardId);
      } else {
        next.add(standardId);
      }
      return next;
    });
    setMessage(null);
  };

  const save = async () => {
    if (!assignmentId || !catalog?.mapped) return;
    setSaving(true);
    setMessage(null);
    setError(null);
    try {
      const response = await fetch(
        `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}` +
          `/week/${encodeURIComponent(weekStart)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ standard_entry_ids: Array.from(selected) }),
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Standards selection could not be saved."));
      }
      const body = (await response.json()) as { selected_count: number };
      setMessage(`${body.selected_count} standard${body.selected_count === 1 ? "" : "s"} selected.`);
      onSelectionSaved?.(selectedEntries);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards selection could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel standards-panel" aria-labelledby="standards-panel-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Authoritative standards</p>
          <h2 id="standards-panel-heading">Standards for this week</h2>
        </div>
        {catalog?.source ? (
          <a
            className="source-link"
            href={catalog.source.landing_url}
            target="_blank"
            rel="noreferrer"
          >
            View authoritative source
          </a>
        ) : null}
      </div>

      {!assignmentId ? <p>Select a course before choosing standards.</p> : null}
      {loading ? <p>Loading approved standards…</p> : null}
      {error ? <p className="error-message">{error}</p> : null}

      {catalog && !catalog.mapped ? (
        <div className="guidance-card">
          <strong>Standards mapping required.</strong>
          <p>
            A platform administrator must map this teaching assignment to its approved
            authoritative standards course before weekly standards can be selected.
          </p>
        </div>
      ) : null}

      {catalog?.mapped && catalog.source && catalog.course ? (
        <>
          <div className="standards-provenance">
            <strong>{catalog.course.display_name}</strong>
            <span>{catalog.source.authority}</span>
            <span>{catalog.source.edition}</span>
            <span>
              Snapshot retrieved {new Date(catalog.source.retrieved_at).toLocaleDateString()}
            </span>
          </div>

          <p className="guidance-text">
            Select the authoritative standards that apply to this week. The exact source text and
            snapshot are preserved with the selection.
          </p>

          <div className="standard-list">
            {catalog.standards.map((standard) => (
              <label className="standard-option" key={standard.id}>
                <input
                  type="checkbox"
                  checked={selected.has(standard.id)}
                  onChange={() => toggle(standard.id)}
                />
                <span>
                  <strong>{standard.code}</strong>
                  <span className="standard-text">{standard.text}</span>
                </span>
              </label>
            ))}
          </div>

          <div className="button-row">
            <button type="button" onClick={() => void save()} disabled={saving}>
              {saving ? "Saving standards…" : "Save standards for week"}
            </button>
            <span>{selected.size} selected</span>
          </div>
          {message ? <p className="success-message">{message}</p> : null}
        </>
      ) : null}
    </section>
  );
}
