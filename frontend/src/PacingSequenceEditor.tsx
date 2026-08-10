import { useMemo, useState } from "react";
import { readPacingWorkbook } from "./pacingWorkbookImport";

type PacingRow = {
  id: number;
  unit: string;
  lesson: string;
  targets: string;
  assessment: string;
  minutes: string;
};

type Props = { disabled?: boolean };

function blankRow(id: number): PacingRow {
  return { id, unit: "", lesson: "", targets: "", assessment: "", minutes: "" };
}

function serialize(rows: PacingRow[]): string {
  return rows
    .filter((row) => row.unit.trim() || row.lesson.trim() || row.targets.trim() || row.assessment.trim() || row.minutes.trim())
    .map((row) => [row.unit, row.lesson, row.targets, row.assessment, row.minutes].map((value) => value.trim()).join(" | "))
    .join("\n");
}

export function PacingSequenceEditor({ disabled = false }: Props) {
  const [nextId, setNextId] = useState(4);
  const [rows, setRows] = useState<PacingRow[]>([blankRow(1), blankRow(2), blankRow(3)]);
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const serialized = useMemo(() => serialize(rows), [rows]);

  function update(id: number, field: keyof Omit<PacingRow, "id">, value: string) {
    setRows((current) => current.map((row) => row.id === id ? { ...row, [field]: value } : row));
  }

  function addRow() {
    setRows((current) => [...current, blankRow(nextId)]);
    setNextId((current) => current + 1);
  }

  function removeRow(id: number) {
    setRows((current) => current.length > 1 ? current.filter((row) => row.id !== id) : [blankRow(current[0]?.id ?? 1)]);
  }

  async function importWorkbook(file: File | null) {
    if (!file) return;
    setImporting(true);
    setImportMessage(null);
    setImportError(null);
    try {
      const imported = await readPacingWorkbook(file);
      const nextRows = imported.map((row, index) => ({ id: index + 1, ...row }));
      setRows(nextRows);
      setNextId(nextRows.length + 1);
      setImportMessage(`${nextRows.length} pacing lesson${nextRows.length === 1 ? "" : "s"} loaded from Excel. Review the lesson cards, then save Curriculum & Pacing.`);
    } catch (caught) {
      setImportError(caught instanceof Error ? caught.message : "The Excel pacing workbook could not be read.");
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="full-width pacing-sequence-editor">
      <input type="hidden" name="lesson_rows" value={serialized} />
      <div className="section-heading compact">
        <div>
          <strong>Pacing sequence</strong>
          <p className="supporting">Enter the longer-term instructional sequence in teaching order. Authoritative standards are selected later in Weekly Plan; you do not need standards codes here.</p>
        </div>
        <div className="button-row">
          <label className={`secondary file-upload-label ${disabled || importing ? "disabled" : ""}`}>
            {importing ? "Reading Excel…" : "Load Excel pacing file"}
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              disabled={disabled || importing}
              style={{ display: "none" }}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0] ?? null;
                void importWorkbook(file);
                event.currentTarget.value = "";
              }}
            />
          </label>
          <button type="button" className="secondary" disabled={disabled || importing} onClick={addRow}>Add lesson</button>
        </div>
      </div>
      {importMessage ? <p className="success-message" role="status">{importMessage}</p> : null}
      {importError ? <p className="error-message" role="alert">{importError}</p> : null}
      <div className="pacing-row-list">
        {rows.map((row, index) => (
          <article className="pacing-row-card" key={row.id}>
            <div className="card-row"><strong>Lesson {index + 1}</strong><button type="button" className="link-button danger-link" disabled={disabled} onClick={() => removeRow(row.id)}>Remove</button></div>
            <div className="form-grid pacing-row-fields">
              <label>Unit / Topic<input value={row.unit} disabled={disabled} placeholder="Chapter 1" onChange={(event) => update(row.id, "unit", event.target.value)} /></label>
              <label>Lesson / Focus<input value={row.lesson} disabled={disabled} placeholder="Facing movements" onChange={(event) => update(row.id, "lesson", event.target.value)} /></label>
              <label className="full-width">Learning target(s)<textarea rows={2} value={row.targets} disabled={disabled} placeholder="Conduct left face, right face, and about face" onChange={(event) => update(row.id, "targets", event.target.value)} /></label>
              <label>Assessment / Evidence<input value={row.assessment} disabled={disabled} placeholder="Individual performance check" onChange={(event) => update(row.id, "assessment", event.target.value)} /></label>
              <label>Optional minutes override<input type="number" min="1" value={row.minutes} disabled={disabled} placeholder="Leave blank for normal class time" onChange={(event) => update(row.id, "minutes", event.target.value)} /></label>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
