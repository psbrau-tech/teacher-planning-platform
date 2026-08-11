import { useEffect, useMemo, useState } from "react";

type ActReferenceSnapshot = {
  id: string;
  source_id: string;
  source_key: string;
  source_title: string;
  source_type: string;
  source_document_url: string;
  source_edition: string | null;
  source_effective_date: string | null;
  retrieved_at: string;
  parser_version: string;
  source_sha256: string;
  normalized_sha256: string;
  entry_count: number;
  benchmark_count: number;
  status: string;
};

type ActReferenceAdministrationPanelProps = {
  accessToken: string;
  disabled?: boolean;
};

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) return body.detail;
  } catch {
    // Keep the bounded fallback rather than exposing raw response content.
  }
  return fallback;
}

function isApprovable(snapshot: ActReferenceSnapshot): boolean {
  if (snapshot.status !== "pending") return false;
  if (snapshot.source_type === "assessment_skill_framework") {
    return snapshot.entry_count > 0 && snapshot.benchmark_count === 0;
  }
  if (snapshot.source_type === "readiness_benchmark") {
    return snapshot.benchmark_count > 0 && snapshot.entry_count === 0;
  }
  return false;
}

export function ActReferenceAdministrationPanel({
  accessToken,
  disabled = false,
}: ActReferenceAdministrationPanelProps) {
  const [pending, setPending] = useState<ActReferenceSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [workingSnapshot, setWorkingSnapshot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const headers = useMemo(
    () => ({ Authorization: `Bearer ${accessToken}` }),
    [accessToken],
  );

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/act-reference-admin/pending", { headers });
      if (!response.ok) {
        throw new Error(await readError(response, "ACT reference administration could not be loaded."));
      }
      setPending((await response.json()) as ActReferenceSnapshot[]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "ACT reference administration could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [accessToken]);

  const approve = async (snapshot: ActReferenceSnapshot) => {
    const approved = window.confirm(
      `Approve this exact ${snapshot.source_title} snapshot?\n\n` +
        `Source type: ${snapshot.source_type.replaceAll("_", " ")}\n` +
        `CCR references: ${snapshot.entry_count}\n` +
        `Readiness benchmarks: ${snapshot.benchmark_count}\n\n` +
        "Approval activates only this deterministic public first-party ACT snapshot. Prior approved snapshots remain preserved as historical provenance.",
    );
    if (!approved) return;

    setWorkingSnapshot(snapshot.id);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch(
        `/api/v1/act-reference-admin/snapshots/${encodeURIComponent(snapshot.id)}/approve`,
        { method: "POST", headers },
      );
      if (!response.ok) {
        throw new Error(await readError(response, "ACT reference snapshot could not be approved."));
      }
      setMessage(`${snapshot.source_title} snapshot approved.`);
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "ACT reference snapshot could not be approved.");
    } finally {
      setWorkingSnapshot(null);
    }
  };

  return (
    <section className="standards-admin-panel" aria-labelledby="act-reference-admin-heading">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Platform Administrator</p>
          <h2 id="act-reference-admin-heading">ACT reference governance</h2>
          <p className="supporting">
            Review deterministic public first-party ACT reference snapshots before activation.
            Nothing is approved automatically.
          </p>
        </div>
        <button type="button" className="secondary" disabled={disabled || loading} onClick={() => void load()}>
          Refresh ACT status
        </button>
      </div>

      {error ? <p className="error-message" role="alert">{error}</p> : null}
      {message ? <p className="success-message" role="status" aria-live="polite">{message}</p> : null}
      {loading ? <p role="status" aria-live="polite">Loading governed ACT status…</p> : null}

      {pending.length === 0 ? (
        <div className="empty-state"><p>No pending ACT reference snapshots.</p></div>
      ) : (
        <div className="grid">
          {pending.map((snapshot) => {
            const approvable = isApprovable(snapshot);
            return (
              <article className="card" key={snapshot.id}>
                <div className="card-row">
                  <span className="badge">{snapshot.source_type.replaceAll("_", " ")}</span>
                  <span className="status">{snapshot.status}</span>
                </div>
                <h3>{snapshot.source_title}</h3>
                <p>
                  {snapshot.entry_count} CCR reference{snapshot.entry_count === 1 ? "" : "s"} · {snapshot.benchmark_count} readiness benchmark{snapshot.benchmark_count === 1 ? "" : "s"}
                </p>
                <small>Edition: {snapshot.source_edition ?? "not published"}</small>
                <small>Effective date: {snapshot.source_effective_date ?? "not separately published"}</small>
                <small>Parser: {snapshot.parser_version}</small>
                <a href={snapshot.source_document_url} target="_blank" rel="noreferrer">Inspect authoritative ACT source</a>
                {!approvable ? (
                  <p className="error-message">Snapshot contents do not satisfy the governed approval shape for this ACT source type.</p>
                ) : null}
                <button
                  type="button"
                  className="primary"
                  disabled={disabled || workingSnapshot !== null || !approvable}
                  onClick={() => void approve(snapshot)}
                >
                  {workingSnapshot === snapshot.id ? "Approving…" : "Approve exact ACT snapshot"}
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
