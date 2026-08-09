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
  relationship?: string;
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

export type StandardEntry = {
  id: string;
  code: string;
  text: string;
  parent_code: string | null;
  strand: string | null;
  sequence: number;
  authority?: string | null;
  relationship?: string | null;
};

type AssignmentStandards = {
  assignment_id: string;
  week_start: string;
  mapped: boolean;
  source: StandardSource | null;
  sources?: StandardSource[];
  course: StandardCourse | null;
  catalog_category?: CatalogCategory | null;
  catalog_course?: CatalogCourse | null;
  standards: StandardEntry[];
  selected_entry_ids: string[];
};

type PlannedLessonContext = {
  unit_title: string;
  lesson_title: string;
  lesson_date: string;
};

type StandardsPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  onSelectionResolved?: (selected: StandardEntry[]) => void;
};

type RankedStandard = {
  standard: StandardEntry;
  score: number;
};

const STOP_WORDS = new Set([
  "about", "after", "again", "along", "also", "and", "are", "before", "between",
  "course", "demonstrate", "describe", "during", "each", "from", "have", "identify",
  "into", "lesson", "more", "other", "should", "that", "their", "these", "this",
  "through", "using", "what", "when", "where", "which", "with", "your",
]);

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep the bounded fallback; never surface raw provider/server content.
  }
  return fallback;
}

function selectedEntriesFor(catalog: AssignmentStandards): StandardEntry[] {
  const selectedIds = new Set(catalog.selected_entry_ids);
  return catalog.standards.filter((standard) => selectedIds.has(standard.id));
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokens(value: string): string[] {
  return normalize(value)
    .split(" ")
    .filter((token) => token.length >= 4 && !STOP_WORDS.has(token));
}

function relevanceScore(standard: StandardEntry, lessons: PlannedLessonContext[]): number {
  if (lessons.length === 0) return 0;
  const standardText = normalize(`${standard.code} ${standard.strand ?? ""} ${standard.text}`);
  let score = 0;

  for (const lesson of lessons) {
    const unit = normalize(lesson.unit_title);
    const title = normalize(lesson.lesson_title);
    if (unit.length >= 5 && standardText.includes(unit)) score += 8;
    if (title.length >= 8 && standardText.includes(title)) score += 14;

    for (const token of new Set(tokens(lesson.unit_title))) {
      if (standardText.includes(token)) score += 2;
    }
    for (const token of new Set(tokens(lesson.lesson_title))) {
      if (standardText.includes(token)) score += 3;
    }
  }
  return score;
}

function standardGroup(standard: StandardEntry): string {
  if (standard.strand?.trim()) return standard.strand.trim();
  const match = standard.code.match(/^U(\d+)C(\d+)/i);
  if (match) return `Unit ${match[1]} · Chapter ${match[2]}`;
  const unit = standard.code.match(/^U(\d+)/i);
  if (unit) return `Unit ${unit[1]}`;
  return "Additional standards";
}

function sourceLabel(source: StandardSource): string {
  return source.relationship === "supplemental_authority"
    ? `${source.authority} · supplemental authoritative curriculum`
    : source.authority;
}

export function StandardsPanel({
  accessToken,
  assignmentId,
  weekStart,
  onSelectionResolved,
}: StandardsPanelProps) {
  const [catalog, setCatalog] = useState<AssignmentStandards | null>(null);
  const [weeklyLessons, setWeeklyLessons] = useState<PlannedLessonContext[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [browseOpen, setBrowseOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setCatalog(null);
    setWeeklyLessons([]);
    setSelected(new Set());
    setQuery("");
    setBrowseOpen(false);
    setMessage(null);
    setError(null);

    if (!accessToken || !assignmentId || !weekStart) {
      return () => {
        active = false;
      };
    }

    const load = async () => {
      setLoading(true);
      try {
        const headers = { Authorization: `Bearer ${accessToken}` };
        const [standardsResponse, planResponse] = await Promise.all([
          fetch(
            `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}` +
              `?week_start=${encodeURIComponent(weekStart)}`,
            { headers },
          ),
          fetch(
            `/api/v1/plans?assignment_id=${encodeURIComponent(assignmentId)}` +
              `&week_start=${encodeURIComponent(weekStart)}`,
            { headers },
          ),
        ]);
        if (!standardsResponse.ok) {
          throw new Error(await readError(standardsResponse, "Standards could not be loaded."));
        }
        const body = (await standardsResponse.json()) as AssignmentStandards;
        const lessons = planResponse.ok
          ? ((await planResponse.json()) as PlannedLessonContext[])
          : [];
        if (!active) return;
        setCatalog(body);
        setWeeklyLessons(lessons);
        setSelected(new Set(body.selected_entry_ids));
        onSelectionResolved?.(selectedEntriesFor(body));
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
  }, [accessToken, assignmentId, onSelectionResolved, weekStart]);

  const selectedEntries = useMemo(() => {
    if (!catalog) return [];
    return catalog.standards.filter((standard) => selected.has(standard.id));
  }, [catalog, selected]);

  const ranked = useMemo<RankedStandard[]>(() => {
    if (!catalog) return [];
    return catalog.standards
      .map((standard) => ({ standard, score: relevanceScore(standard, weeklyLessons) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || a.standard.sequence - b.standard.sequence);
  }, [catalog, weeklyLessons]);

  const suggestedStandards = useMemo(() => {
    if (!catalog) return [];
    const byId = new Map<string, StandardEntry>();
    for (const standard of selectedEntries) byId.set(standard.id, standard);
    for (const item of ranked.slice(0, 8)) byId.set(item.standard.id, item.standard);
    return Array.from(byId.values());
  }, [catalog, ranked, selectedEntries]);

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

  const groupedStandards = useMemo(() => {
    const groups = new Map<string, StandardEntry[]>();
    for (const standard of visibleStandards) {
      const group = standardGroup(standard);
      groups.set(group, [...(groups.get(group) ?? []), standard]);
    }
    return Array.from(groups.entries());
  }, [visibleStandards]);

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
    if (!accessToken || !assignmentId || !catalog?.mapped) return;
    setSaving(true);
    setMessage(null);
    setError(null);
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
        throw new Error(await readError(response, "Standards selection could not be saved."));
      }
      const body = (await response.json()) as { selected_count: number };
      setMessage(
        `${body.selected_count} authoritative standard${body.selected_count === 1 ? "" : "s"} saved. ` +
          "A planning draft will be prepared below for teacher review.",
      );
      onSelectionResolved?.(selectedEntries);
      window.dispatchEvent(
        new CustomEvent("tpp:standards-saved", {
          detail: { assignmentId, weekStart },
        }),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards selection could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const renderStandard = (standard: StandardEntry) => (
    <label className="standard-option" key={standard.id}>
      <input
        type="checkbox"
        checked={selected.has(standard.id)}
        onChange={() => toggle(standard.id)}
      />
      <span>
        <span className="standard-heading-row">
          <strong>{standard.code}</strong>
          {standard.strand ? <span className="badge">{standard.strand}</span> : null}
        </span>
        <span className="standard-text">{standard.text}</span>
      </span>
    </label>
  );

  const sources = catalog?.sources?.length
    ? catalog.sources
    : catalog?.source
      ? [catalog.source]
      : [];

  return (
    <section className="panel standards-panel" aria-labelledby="standards-panel-heading">
      <div className="section-heading-row">
        <div>
          <p className="eyebrow">Authoritative standards</p>
          <h2 id="standards-panel-heading">Standards for this week</h2>
          {catalog?.catalog_category && catalog.catalog_course ? (
            <p className="supporting">
              {catalog.catalog_category.display_name} → {catalog.catalog_course.display_name}
            </p>
          ) : null}
        </div>
      </div>

      {!assignmentId ? <p>Select a course before choosing standards.</p> : null}
      {loading ? <p>Loading approved standards and this week&apos;s lessons…</p> : null}
      {error ? <p className="error-message" role="alert">{error}</p> : null}

      {catalog && !catalog.mapped ? (
        <div className="guidance-card">
          <strong>Standards mapping required.</strong>
          <p>
            Select the Subject / Career Cluster and Grade / Course for this teaching assignment
            above. You control the course mapping; the platform administrator governs which
            authoritative source snapshots are approved for use.
          </p>
        </div>
      ) : null}

      {catalog?.mapped ? (
        <>
          <div className="standards-provenance">
            {sources.map((source) => (
              <div className="provenance-row" key={`${source.id}-${source.snapshot_id}`}>
                <strong>{sourceLabel(source)}</strong>
                <span>{source.edition}</span>
                <span>Snapshot retrieved {new Date(source.retrieved_at).toLocaleDateString()}</span>
                <a className="source-link" href={source.landing_url} target="_blank" rel="noreferrer">
                  View authoritative source
                </a>
              </div>
            ))}
          </div>

          <div className="guidance-card">
            <strong>Suggested for this week</strong>
            <p>
              TPP compares the imported unit and lesson titles scheduled this week with the exact
              approved course standards. This is a deterministic relevance aid, not AI rewriting.
              The complete approved course remains available below.
            </p>
          </div>

          {weeklyLessons.length > 0 ? (
            <div className="weekly-context-chips" aria-label="Scheduled lesson context">
              {weeklyLessons.map((lesson) => (
                <span className="badge" key={`${lesson.lesson_date}-${lesson.lesson_title}`}>
                  {lesson.unit_title}: {lesson.lesson_title}
                </span>
              ))}
            </div>
          ) : (
            <p className="guidance-text">
              Generate or reopen the week to receive lesson-based standard suggestions.
            </p>
          )}

          <div className="standard-list suggested-standard-list">
            {suggestedStandards.length > 0 ? suggestedStandards.map(renderStandard) : (
              <div className="empty-state">
                <p>No strong wording match was found. Search or browse the complete approved course.</p>
              </div>
            )}
          </div>

          <details
            className="standards-browser"
            open={browseOpen}
            onToggle={(event) => setBrowseOpen(event.currentTarget.open)}
          >
            <summary>Browse all approved standards ({catalog.standards.length})</summary>
            <label className="standards-search">
              Search standards
              <input
                type="search"
                value={query}
                placeholder="Search by code, wording, strand, or source"
                onChange={(event) => {
                  setQuery(event.target.value);
                  if (event.target.value.trim()) setBrowseOpen(true);
                }}
              />
            </label>
            {groupedStandards.length === 0 ? (
              <div className="empty-state"><p>No standards match this search.</p></div>
            ) : groupedStandards.map(([group, standards]) => (
              <section className="standard-group" key={group} aria-label={group}>
                <h3>{group}</h3>
                <div className="standard-list">{standards.map(renderStandard)}</div>
              </section>
            ))}
          </details>

          <p className="guidance-text">
            Select only the standards that apply to this week. The exact approved source text and
            snapshot are preserved; AI cannot rewrite authoritative wording.
          </p>

          <div className="button-row">
            <button type="button" onClick={() => void save()} disabled={saving}>
              {saving ? "Saving standards…" : "Save standards for week"}
            </button>
            <span>{selected.size} selected</span>
          </div>
          {message ? <p className="success-message" role="status">{message}</p> : null}
        </>
      ) : null}
    </section>
  );
}
