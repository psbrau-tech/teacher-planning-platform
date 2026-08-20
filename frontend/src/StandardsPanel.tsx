import { Fragment, useEffect, useMemo, useRef, useState } from "react";

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

type ProficiencyScale = {
  standard_code: string;
  standard_text: string;
  literacy_type: string | null;
  focus_area: string | null;
  category: string | null;
  levels: Record<string, string>;
};

type ProficiencyGrade = {
  grade_band: string;
  available: boolean;
  authority: string | null;
  source_title: string | null;
  source_version: string | null;
  retrieved_at: string | null;
  landing_url: string | null;
  resolved_document_url: string | null;
  scales: ProficiencyScale[];
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

export type PlannedLessonContext = {
  unit_title: string;
  lesson_title: string;
  lesson_date: string;
};

type StandardsPanelProps = {
  accessToken: string;
  assignmentId: string | null;
  weekStart: string;
  weeklyLessons?: PlannedLessonContext[];
  onSelectionResolved?: (selected: StandardEntry[]) => void;
  onSelectionSaved?: (selected: StandardEntry[]) => void;
};

type RankedStandard = { standard: StandardEntry; score: number };

const STOP_WORDS = new Set([
  "about", "after", "again", "along", "also", "and", "are", "before", "between",
  "course", "demonstrate", "describe", "during", "each", "from", "have", "identify",
  "into", "lesson", "more", "other", "should", "that", "their", "these", "this",
  "through", "using", "what", "when", "where", "which", "with", "your",
]);

const PROFICIENCY_LEVEL_ORDER = ["4.0", "3.5", "3.0", "2.5", "2.0", "1.5", "1.0", "0.5", "0.0"];

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep the bounded fallback; never surface raw provider/server content.
  }
  return fallback;
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
}

function tokens(value: string): string[] {
  return normalize(value).split(" ").filter((token) => token.length >= 4 && !STOP_WORDS.has(token));
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
    for (const token of new Set(tokens(lesson.unit_title))) if (standardText.includes(token)) score += 2;
    for (const token of new Set(tokens(lesson.lesson_title))) if (standardText.includes(token)) score += 3;
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

function mappedStandardsLabel(catalog: AssignmentStandards): string | null {
  const courseName = (catalog.catalog_course?.display_name ?? catalog.course?.display_name ?? "").trim();
  if (!courseName) return null;
  return /standards$/i.test(courseName) ? courseName : `${courseName} Standards`;
}

function sourceLabel(source: StandardSource): string {
  return source.relationship === "supplemental_authority"
    ? `${source.authority} · supplemental authoritative curriculum`
    : source.authority;
}

function eligibleElaGrade(catalog: AssignmentStandards): number | null {
  if (catalog.catalog_category?.category_key !== "english_language_arts") return null;
  const grade = Number(catalog.catalog_course?.grade_band ?? catalog.course?.grade_band ?? "");
  return Number.isInteger(grade) && grade >= 6 && grade <= 12 ? grade : null;
}

function isContentStandard(standard: StandardEntry): boolean {
  return standard.strand?.trim().toLowerCase() === "content standards";
}

export function StandardsPanel({
  accessToken,
  assignmentId,
  weekStart,
  weeklyLessons = [],
  onSelectionResolved,
  onSelectionSaved,
}: StandardsPanelProps) {
  const [catalog, setCatalog] = useState<AssignmentStandards | null>(null);
  const [proficiency, setProficiency] = useState<ProficiencyGrade | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [browseOpen, setBrowseOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resolvedCallback = useRef(onSelectionResolved);
  const savedCallback = useRef(onSelectionSaved);

  useEffect(() => {
    resolvedCallback.current = onSelectionResolved;
    savedCallback.current = onSelectionSaved;
  }, [onSelectionResolved, onSelectionSaved]);

  useEffect(() => {
    let active = true;
    setCatalog(null);
    setProficiency(null);
    setSelected(new Set());
    setQuery("");
    setBrowseOpen(false);
    setMessage(null);
    setError(null);
    if (!accessToken || !assignmentId || !weekStart) return () => { active = false; };

    const load = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}?week_start=${encodeURIComponent(weekStart)}`,
          { headers: { Authorization: `Bearer ${accessToken}` } },
        );
        if (!response.ok) throw new Error(await readError(response, "Standards could not be loaded."));
        const body = await response.json() as AssignmentStandards;
        if (!active) return;
        const validIds = new Set(body.standards.map((standard) => standard.id));
        const savedIds = body.selected_entry_ids.filter((id) => validIds.has(id));
        const savedEntries = body.standards.filter((standard) => savedIds.includes(standard.id));
        setCatalog(body);
        setSelected(new Set(savedIds));
        resolvedCallback.current?.(savedEntries);
        savedCallback.current?.(savedEntries);

        const elaGrade = eligibleElaGrade(body);
        if (elaGrade !== null) {
          try {
            const proficiencyResponse = await fetch(
              `/api/v1/standards/proficiency/grade/${elaGrade}`,
              { headers: { Authorization: `Bearer ${accessToken}` } },
            );
            if (proficiencyResponse.ok) {
              const proficiencyBody = await proficiencyResponse.json() as ProficiencyGrade;
              if (active) setProficiency(proficiencyBody.available ? proficiencyBody : null);
            }
          } catch {
            // Supplemental guidance must never block authoritative standards selection.
            if (active) setProficiency(null);
          }
        }
      } catch (caught) {
        if (active) setError(caught instanceof Error ? caught.message : "Standards could not be loaded.");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [accessToken, assignmentId, weekStart]);

  const proficiencyScalesForCourse = useMemo(() => {
    if (!catalog || !proficiency) return [];
    const sequenceByCode = new Map(catalog.standards.map((standard) => [standard.code, standard.sequence]));
    return proficiency.scales
      .filter((scale) => sequenceByCode.has(scale.standard_code))
      .sort((a, b) => (sequenceByCode.get(a.standard_code) ?? 0) - (sequenceByCode.get(b.standard_code) ?? 0));
  }, [catalog, proficiency]);

  const selectedEntries = useMemo(() => {
    if (!catalog) return [];
    return catalog.standards.filter((standard) => selected.has(standard.id));
  }, [catalog, selected]);

  const suggestedStandards = useMemo(() => {
    if (!catalog || weeklyLessons.length === 0) return [];
    const ranked: RankedStandard[] = catalog.standards
      .map((standard) => ({ standard, score: relevanceScore(standard, weeklyLessons) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || a.standard.sequence - b.standard.sequence);
    const representedCodes = new Set<string>();
    const suggestions: StandardEntry[] = [];
    for (const item of ranked) {
      const code = item.standard.code.toLowerCase();
      if (representedCodes.has(code)) continue;
      representedCodes.add(code);
      suggestions.push(item.standard);
      if (suggestions.length >= 5) break;
    }
    return suggestions;
  }, [catalog, weeklyLessons]);

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

  const standardsCourseLabel = useMemo(
    () => (catalog ? mappedStandardsLabel(catalog) : null),
    [catalog],
  );

  const toggle = (standardId: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(standardId)) next.delete(standardId); else next.add(standardId);
      if (catalog) resolvedCallback.current?.(catalog.standards.filter((standard) => next.has(standard.id)));
      return next;
    });
    setMessage(null);
  };

  const save = async () => {
    if (!accessToken || !assignmentId || !catalog?.mapped) return;
    setSaving(true); setMessage(null); setError(null);
    try {
      const validIds = new Set(catalog.standards.map((standard) => standard.id));
      const selectedIds = Array.from(selected).filter((id) => validIds.has(id));
      const savedEntries = catalog.standards.filter((standard) => selectedIds.includes(standard.id));
      const response = await fetch(
        `/api/v1/standards/assignment/${encodeURIComponent(assignmentId)}/week/${encodeURIComponent(weekStart)}`,
        {
          method: "PUT",
          headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
          body: JSON.stringify({ standard_entry_ids: selectedIds }),
        },
      );
      if (!response.ok) throw new Error(await readError(response, "Standards selection could not be saved."));
      const body = await response.json() as { selected_count: number };
      setSelected(new Set(selectedIds));
      resolvedCallback.current?.(savedEntries);
      savedCallback.current?.(savedEntries);
      setMessage(body.selected_count > 0
        ? `${body.selected_count} authoritative standard${body.selected_count === 1 ? "" : "s"} saved. Your planning draft will be prepared below.`
        : "Weekly standards selection cleared.");
      if (body.selected_count > 0) {
        window.dispatchEvent(new CustomEvent("tpp:standards-saved", { detail: { assignmentId, weekStart } }));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards selection could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const renderStandard = (standard: StandardEntry) => (
    <label className="standard-option" key={standard.id}>
      <input type="checkbox" checked={selected.has(standard.id)} onChange={() => toggle(standard.id)} />
      <span>
        <span className="standard-heading-row"><strong>{standard.code}</strong>{standard.strand ? <span className="badge">{standard.strand}</span> : null}</span>
        <span className="standard-text">{standard.text}</span>
      </span>
    </label>
  );

  const renderProficiencyCollection = () => {
    if (!proficiency || proficiencyScalesForCourse.length === 0) return null;
    const sourceUrl = proficiency.resolved_document_url ?? proficiency.landing_url ?? undefined;
    return (
      <details className="guidance-card proficiency-scale proficiency-scale-collection">
        <summary><strong>View ALSDE proficiency scale</strong></summary>
        <p className="guidance-text">Supplemental instructional guidance for this mapped ELA course. The Course of Study standards below remain authoritative.</p>
        <div className="proficiency-scale-list">
          {proficiencyScalesForCourse.map((scale) => (
            <section className="proficiency-standard-block" key={scale.standard_code}>
              <h4>Standard {scale.standard_code}</h4>
              <p className="guidance-text">{[scale.literacy_type, scale.focus_area, scale.category].filter(Boolean).join(" · ")}</p>
              <dl className="proficiency-levels">
                {PROFICIENCY_LEVEL_ORDER.filter((level) => scale.levels[level]).map((level) => (
                  <div className="proficiency-level" key={level}>
                    <dt><strong>Level {level}</strong></dt>
                    <dd>{scale.levels[level]}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
        {sourceUrl ? <a className="source-link" href={sourceUrl} target="_blank" rel="noreferrer">View current ALSDE proficiency source</a> : null}
        {proficiency.source_version ? <p className="guidance-text">Source version: {proficiency.source_version}</p> : null}
      </details>
    );
  };

  const renderMappedStandards = (standards: StandardEntry[]) => {
    const proficiencyInsertIndex = proficiencyScalesForCourse.length > 0
      ? standards.findIndex(isContentStandard)
      : -1;
    return standards.map((standard, index) => (
      <Fragment key={standard.id}>
        {index === proficiencyInsertIndex ? renderProficiencyCollection() : null}
        {renderStandard(standard)}
      </Fragment>
    ));
  };

  const sources = catalog?.sources?.length ? catalog.sources : catalog?.source ? [catalog.source] : [];

  return (
    <section className="panel standards-panel" aria-labelledby="standards-panel-heading">
      <div className="section-heading-row"><div><p className="eyebrow">Authoritative standards</p><h2 id="standards-panel-heading">Standards for this week</h2>{catalog?.catalog_category && catalog.catalog_course ? <p className="supporting">{catalog.catalog_category.display_name} → {catalog.catalog_course.display_name}</p> : null}</div></div>
      {!assignmentId ? <p>Select a course before choosing standards.</p> : null}
      {loading ? <p role="status" aria-live="polite">Loading approved standards…</p> : null}
      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {catalog && !catalog.mapped ? <div className="guidance-card"><strong>Standards mapping required.</strong><p>Set the authoritative standards mapping in Course Setup.</p></div> : null}
      {catalog?.mapped ? <>
        <div className="standards-provenance">{sources.map((source) => <div className="provenance-row" key={`${source.id}-${source.snapshot_id}`}><strong>{sourceLabel(source)}</strong><span>{source.edition}</span><span>Snapshot retrieved {new Date(source.retrieved_at).toLocaleDateString()}</span><a className="source-link" href={source.landing_url} target="_blank" rel="noreferrer">View authoritative source</a></div>)}</div>
        {proficiency ? <div className="guidance-card"><strong>ALSDE Grade {proficiency.grade_band} proficiency guidance available</strong><p>Open the single proficiency scale control before the content standards for mastery levels and instructional guidance. This supplemental source is tracked separately from authoritative standard text.</p></div> : null}
        <div className="guidance-card"><strong>Suggested for this week</strong><p>TPP compares this week&apos;s scheduled unit and lesson titles with the exact approved course standards. This is deterministic relevance matching, not AI-generated standards.</p></div>
        {weeklyLessons.length === 0 ? <p className="guidance-text">Build or reopen the week to receive lesson-based suggestions.</p> : suggestedStandards.length > 0 ? <div className="standard-list suggested-standard-list">{suggestedStandards.map(renderStandard)}</div> : <div className="empty-state"><p>No strong wording match was found. Browse or search the approved catalog below.</p></div>}
        {selectedEntries.length > 0 ? <p className="guidance-text"><strong>Selected for this week:</strong> {selectedEntries.map((item) => item.code).join(", ")}</p> : null}
        <details className="standards-browser" open={browseOpen} onToggle={(event) => setBrowseOpen(event.currentTarget.open)}>
          <summary>Browse all approved standards ({catalog.standards.length})</summary>
          {browseOpen ? <>
            <label className="standards-search">Search standards<input type="search" value={query} placeholder="Search by code, wording, strand, or source" onChange={(event) => setQuery(event.target.value)} /></label>
            {visibleStandards.length === 0 ? <div className="empty-state"><p>No standards match this search.</p></div> : standardsCourseLabel ? <details className="standard-group" open><summary>{standardsCourseLabel} ({visibleStandards.length})</summary><div className="standard-list">{renderMappedStandards(visibleStandards)}</div></details> : groupedStandards.map(([group, standards]) => <details className="standard-group" key={group} open={Boolean(query.trim())}><summary>{group} ({standards.length})</summary><div className="standard-list">{standards.map(renderStandard)}</div></details>)}
          </> : null}
        </details>
        <p className="guidance-text">Select only the standards that apply this week. Exact approved wording and source provenance are preserved.</p>
        <div className="button-row"><button type="button" className="primary" onClick={() => void save()} disabled={saving}>{saving ? "Saving standards…" : "Save standards and continue"}</button><span>{selectedEntries.length} selected</span></div>
        {message ? <p className="success-message" role="status">{message}</p> : null}
      </> : null}
    </section>
  );
}
