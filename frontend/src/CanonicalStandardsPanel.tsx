import { useEffect, useMemo, useState } from "react";

type CatalogCategory = {
  id: string;
  category_key: string;
  display_name: string;
  category_type: string;
  sort_order: number;
};

type CatalogCourse = {
  id: string;
  category_id: string;
  course_key: string;
  display_name: string;
  source_course_code: string | null;
  grade_band: string | null;
};

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
  relationship: "primary" | "supplemental_authority" | string;
};

export type CanonicalStandardEntry = {
  id: string;
  code: string;
  text: string;
  parent_code: string | null;
  strand: string | null;
  sequence: number;
  source_id: string | null;
  snapshot_id: string | null;
  authority: string | null;
  source_title: string | null;
  relationship: string | null;
};

type AssignmentStandards = {
  assignment_id: string;
  week_start: string;
  mapped: boolean;
  sources: StandardSource[];
  catalog_category: CatalogCategory | null;
  catalog_course: CatalogCourse | null;
  standards: CanonicalStandardEntry[];
  selected_entry_ids: string[];
};

type CanonicalStandardsPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  disabled?: boolean;
  onSelectionSaved?: (selected: CanonicalStandardEntry[]) => void;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep bounded fallback; do not expose raw server content.
  }
  return fallback;
}

function sourceLabel(source: StandardSource): string {
  return source.relationship === "supplemental_authority"
    ? `${source.authority} · supplemental authoritative curriculum`
    : source.authority;
}

export function CanonicalStandardsPanel({
  accessToken,
  assignmentId,
  weekStart,
  disabled = false,
  onSelectionSaved,
}: CanonicalStandardsPanelProps) {
  const [catalog, setCatalog] = useState<AssignmentStandards | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setCatalog(null);
    setSelected(new Set());
    setQuery("");
    setMessage(null);
    setError(null);

    if (!assignmentId || !weekStart) return () => { active = false; };

    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}` +
            `?week_start=${encodeURIComponent(weekStart)}`,
          { headers: { Authorization: `Bearer ${accessToken}` } },
        );
        if (!response.ok) {
          throw new Error(await readError(response, "Authoritative standards could not be loaded."));
        }
        const body = (await response.json()) as AssignmentStandards;
        if (!active) return;
        setCatalog(body);
        setSelected(new Set(body.selected_entry_ids));
        if (body.selected_entry_ids.length > 0) {
          const selectedIds = new Set(body.selected_entry_ids);
          onSelectionSaved?.(body.standards.filter((item) => selectedIds.has(item.id)));
        }
      } catch (caught) {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Authoritative standards could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    };

    void load();
    return () => { active = false; };
  }, [accessToken, assignmentId, weekStart, onSelectionSaved]);

  const visibleStandards = useMemo(() => {
    if (!catalog) return [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) return catalog.standards;
    return catalog.standards.filter((standard) =>
      [standard.code, standard.text, standard.strand, standard.authority]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalized)),
    );
  }, [catalog, query]);

  const selectedEntries = useMemo(() => {
    if (!catalog) return [];
    return catalog.standards.filter((standard) => selected.has(standard.id));
  }, [catalog, selected]);

  const toggle = (standardId: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(standardId)) next.delete(standardId);
      else next.add(standardId);
      return next;
    });
    setMessage(null);
  };

  const save = async () => {
    if (!assignmentId || !catalog?.mapped) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(
        `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}` +
          `/week/${encodeURIComponent(weekStart)}`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ standard_entry_ids: Array.from(selected) }),
        },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "Weekly standards selection could not be saved."));
      }
      const result = (await response.json()) as { selected_count: number };
      setMessage(
        `${result.selected_count} authoritative standard${result.selected_count === 1 ? "" : "s"} selected for this week.`,
      );
      onSelectionSaved?.(selectedEntries);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Weekly standards selection could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="panel standards-panel" aria-labelledby="canonical-standards-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Authoritative standards</p>
          <h2 id="canonical-standards-heading">Standards for this week</h2>
          {catalog?.mapped && catalog.catalog_category && catalog.catalog_course ? (
            <p className="supporting">
              {catalog.catalog_category.display_name} → {catalog.catalog_course.display_name}
            </p>
          ) : null}
        </div>
      </div>

      {!assignmentId ? <p>Select a course before choosing standards.</p> : null}
      {loading ? <p>Loading approved standards…</p> : null}
      {error ? <p className="error-message">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}

      {catalog && !catalog.mapped ? (
        <div className="guidance-card">
          <strong>Standards mapping required.</strong>
          <p>
            Choose the Subject / Career Cluster and Grade / Course for this teaching assignment
            before selecting weekly standards.
          </p>
        </div>
      ) : null}

      {catalog?.mapped ? (
        <>
          <div className="standards-provenance">
            {catalog.sources.map((source) => (
              <div key={`${source.id}-${source.snapshot_id}`} className="provenance-row">
                <strong>{sourceLabel(source)}</strong>
                <span>{source.title}</span>
                <span>{source.edition}{source.source_version ? ` · ${source.source_version}` : ""}</span>
                <a href={source.landing_url} target="_blank" rel="noreferrer">
                  View authoritative source
                </a>
              </div>
            ))}
          </div>

          <label className="full-width">
            Search standards
            <input
              type="search"
              value={query}
              placeholder="Search by code, wording, strand, or source"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>

          <p className="guidance-text">
            Select the standards that apply to this week. TPP stores the exact standard entry and
            source snapshot used; AI cannot rewrite authoritative wording.
          </p>

          <div className="standard-list">
            {visibleStandards.length === 0 ? (
              <div className="empty-state"><p>No standards match this search.</p></div>
            ) : visibleStandards.map((standard) => (
              <label className="standard-option" key={standard.id}>
                <input
                  type="checkbox"
                  checked={selected.has(standard.id)}
                  disabled={disabled || saving}
                  onChange={() => toggle(standard.id)}
                />
                <span>
                  <span className="standard-heading-row">
                    <strong>{standard.code}</strong>
                    {standard.strand ? <span className="badge">{standard.strand}</span> : null}
                    {standard.relationship === "supplemental_authority" ? (
                      <span className="badge">Supplemental authority</span>
                    ) : null}
                  </span>
                  <span className="standard-text">{standard.text}</span>
                  {standard.authority ? <small>{standard.authority}</small> : null}
                </span>
              </label>
            ))}
          </div>

          <div className="button-row">
            <button
              type="button"
              className="primary"
              disabled={disabled || saving}
              onClick={() => void save()}
            >
              {saving ? "Saving standards…" : "Save standards for week"}
            </button>
            <span>{selected.size} selected</span>
          </div>
        </>
      ) : null}
    </section>
  );
}
