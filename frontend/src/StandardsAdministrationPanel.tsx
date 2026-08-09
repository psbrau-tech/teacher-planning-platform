import { useEffect, useMemo, useState } from "react";
import { ActReferenceAdministrationPanel } from "./ActReferenceAdministrationPanel";

type SourceRow = {
  id: string;
  source_key: string;
  family: string;
  authority: string;
  title: string;
  edition: string;
  source_kind: string;
  provides_standard_entries: boolean;
  discovery_status: string;
  approved_snapshot_id: string | null;
  catalog_category_key: string | null;
  catalog_category_name: string | null;
};

type PendingSnapshot = {
  id: string;
  source_id: string;
  source_key: string;
  source_title: string;
  source_kind: string;
  source_version: string | null;
  parser_version: string | null;
  retrieved_at: string;
  resolved_document_url: string;
  source_sha256: string;
  normalized_sha256: string | null;
  parser_status: string | null;
  parser_error: string | null;
  course_count: number;
  standard_entry_count: number;
};

type CatalogRun = {
  id: string;
  checked_at: string;
  check_month: string | null;
  trigger_kind: string;
  status: string;
  catalog_sha256: string;
  discovered_source_count: number;
  unchanged_count: number;
  changed_count: number;
  new_count: number;
  missing_count: number;
  error_summary: string | null;
};

type CatalogItem = {
  id: string;
  source_key: string;
  result_state: string;
  family: string;
  category_name: string | null;
  authority: string;
  observed_title: string | null;
  observed_edition: string | null;
  observed_document_url: string | null;
  previous_title: string | null;
  previous_edition: string | null;
  previous_document_url: string | null;
};

type CatalogRunDetail = {
  run: CatalogRun;
  items: CatalogItem[];
};

type StandardsAdministrationPanelProps = {
  accessToken: string;
  disabled?: boolean;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Preserve bounded fallback instead of exposing raw response content.
  }
  return fallback;
}

export function StandardsAdministrationPanel({ accessToken, disabled = false }: StandardsAdministrationPanelProps) {
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [pending, setPending] = useState<PendingSnapshot[]>([]);
  const [runs, setRuns] = useState<CatalogRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<CatalogRunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [workingSnapshot, setWorkingSnapshot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const headers = useMemo(() => ({ Authorization: `Bearer ${accessToken}` }), [accessToken]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sourceResponse, pendingResponse, runResponse] = await Promise.all([
        fetch("/api/v1/standards-admin/sources", { headers }),
        fetch("/api/v1/standards-admin/pending-snapshots", { headers }),
        fetch("/api/v1/standards-admin/catalog-runs", { headers }),
      ]);
      for (const response of [sourceResponse, pendingResponse, runResponse]) {
        if (!response.ok) throw new Error(await readError(response, "Standards administration could not be loaded."));
      }
      setSources((await sourceResponse.json()) as SourceRow[]);
      setPending((await pendingResponse.json()) as PendingSnapshot[]);
      setRuns((await runResponse.json()) as CatalogRun[]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards administration could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [accessToken]);

  const inspectRun = async (runId: string) => {
    setError(null);
    try {
      const response = await fetch(`/api/v1/standards-admin/catalog-runs/${encodeURIComponent(runId)}`, { headers });
      if (!response.ok) throw new Error(await readError(response, "Catalog discovery run could not be loaded."));
      setSelectedRun((await response.json()) as CatalogRunDetail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Catalog discovery run could not be loaded.");
    }
  };

  const approve = async (snapshot: PendingSnapshot) => {
    const approved = window.confirm(
      `Approve this exact ${snapshot.source_title} snapshot?\n\n` +
      `Parser: ${snapshot.parser_status ?? "unknown"}\nCourses: ${snapshot.course_count}\nStandards: ${snapshot.standard_entry_count}\n\n` +
      "Approval may update the teacher-visible standards catalog. The previous approved snapshot will remain preserved as historical provenance.",
    );
    if (!approved) return;
    setWorkingSnapshot(snapshot.id);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(`/api/v1/standards-admin/snapshots/${encodeURIComponent(snapshot.id)}/approve`, { method: "POST", headers });
      if (!response.ok) throw new Error(await readError(response, "Standards snapshot could not be approved."));
      setMessage(`${snapshot.source_title} snapshot approved.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Standards snapshot could not be approved.");
    } finally {
      setWorkingSnapshot(null);
    }
  };

  return (
    <section className="standards-admin-panel" aria-labelledby="standards-admin-heading">
      <div className="section-heading compact">
        <div><p className="eyebrow">Platform Owner</p><h2 id="standards-admin-heading">Authoritative standards governance</h2><p className="supporting">Review governed sources, source discovery, parser results, and exact pending snapshots. Nothing activates automatically after a source change.</p></div>
        <button type="button" className="secondary" disabled={disabled || loading} onClick={() => void load()}>Refresh standards status</button>
      </div>
      {error ? <p className="error-message">{error}</p> : null}
      {message ? <p className="success-message">{message}</p> : null}
      {loading ? <p>Loading governed standards status…</p> : null}

      <section>
        <div className="section-heading compact"><div><h3>Governed sources</h3><p className="supporting">Compact source list; expand an item when provenance details are needed.</p></div></div>
        <div className="governance-list">
          {sources.map((source) => (
            <details className="governance-source" key={source.id}>
              <summary><span><strong>{source.catalog_category_name ?? source.title}</strong><small>{source.source_kind.replaceAll("_", " ")} · {source.discovery_status}</small></span></summary>
              <div className="guidance-card">
                <p><strong>Source:</strong> {source.title}</p>
                <p><strong>Authority:</strong> {source.authority}</p>
                <p><strong>Edition:</strong> {source.edition}</p>
                <p><strong>Catalog role:</strong> {source.provides_standard_entries ? "Provides teacher-visible standards entries" : "Course/reference listing only"}</p>
                <p><strong>Approved snapshot:</strong> {source.approved_snapshot_id ?? "None approved"}</p>
              </div>
            </details>
          ))}
        </div>
      </section>

      <section>
        <div className="section-heading compact"><div><h3>Pending snapshots</h3><p className="supporting">This is the human-approval queue for a newly detected authoritative source version. A pending snapshot cannot affect teachers until the Platform Owner approves that exact parsed snapshot.</p></div></div>
        {pending.length === 0 ? <div className="empty-state"><p>No authoritative source changes are waiting for approval. Current approved snapshots remain in effect.</p></div> : (
          <div className="governance-list">
            {pending.map((snapshot) => (
              <details className="governance-source" key={snapshot.id} open>
                <summary><span><strong>{snapshot.source_title}</strong><small>{snapshot.parser_status ?? "unknown parser status"} · {snapshot.course_count} courses · {snapshot.standard_entry_count} standards</small></span></summary>
                <div className="guidance-card">
                  <p>Source version: {snapshot.source_version ?? "not published"}</p>
                  <p>Parser: {snapshot.parser_version ?? "not available"}</p>
                  {snapshot.parser_error ? <p className="error-message">{snapshot.parser_error}</p> : null}
                  <a href={snapshot.resolved_document_url} target="_blank" rel="noreferrer">Inspect authoritative document</a>
                  <button type="button" className="primary" disabled={disabled || workingSnapshot !== null || snapshot.parser_status !== "parsed" || snapshot.course_count === 0} onClick={() => void approve(snapshot)}>{workingSnapshot === snapshot.id ? "Approving…" : "Approve exact snapshot"}</button>
                </div>
              </details>
            ))}
          </div>
        )}
      </section>

      <section>
        <div className="section-heading compact"><div><h3>Catalog discovery history</h3><p className="supporting">Monthly and manual checks across the complete Alabama catalog.</p></div></div>
        <div className="grid">
          {runs.map((run) => (
            <article className="card" key={run.id}>
              <div className="card-row"><span className="badge">{run.trigger_kind}</span><span className="status">{run.status}</span></div>
              <h3>{new Date(run.checked_at).toLocaleDateString()}</h3>
              <p>{run.discovered_source_count} discovered · {run.unchanged_count} unchanged</p>
              <p>{run.changed_count} changed · {run.new_count} new · {run.missing_count} missing</p>
              {run.error_summary ? <p className="error-message">{run.error_summary}</p> : null}
              <button type="button" className="link-button" onClick={() => void inspectRun(run.id)}>Review discovery evidence</button>
            </article>
          ))}
        </div>
        {selectedRun ? <div className="guidance-card"><strong>Discovery evidence — {new Date(selectedRun.run.checked_at).toLocaleString()}</strong><div className="standard-list">{selectedRun.items.map((item) => <div className="standard-option" key={item.id}><span className="badge">{item.result_state}</span><span><strong>{item.category_name ?? item.source_key}</strong><span className="standard-text">{item.observed_title ?? item.previous_title ?? item.source_key}</span><small>{item.authority} · {item.observed_edition ?? item.previous_edition ?? "edition unavailable"}</small></span></div>)}</div></div> : null}
      </section>

      <ActReferenceAdministrationPanel accessToken={accessToken} disabled={disabled} />
    </section>
  );
}