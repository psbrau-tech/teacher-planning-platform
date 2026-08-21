import { useState, type PointerEvent as ReactPointerEvent } from "react";

type Props = {
  draft: Record<string, string>;
  disabled?: boolean;
  onChange: (next: Record<string, string>) => void;
};

const DAYS = [
  ["mon", "Monday"],
  ["tue", "Tuesday"],
  ["wed", "Wednesday"],
  ["thu", "Thursday"],
  ["fri", "Friday"],
] as const;

const COMPONENTS = [
  ["clt", "Clear learning target & success criteria"],
  ["rrt", "Rigorous & relevant task"],
  ["cfu", "Checks for understanding"],
  ["ri", "Responsive instruction"],
  ["sic", "Strong instructional culture"],
  ["esl", "Evidence of student learning"],
] as const;

const MIN_MATRIX_ROW_HEIGHT = 92;
const RESIZE_GRIP_SIZE = 20;

type WeekAtGlanceRowProps = Props & {
  label: string;
  prefix: string;
};

function WeekAtGlanceRow({ draft, disabled = false, label, onChange, prefix }: WeekAtGlanceRowProps) {
  const [rowHeight, setRowHeight] = useState<number | null>(null);

  function setField(key: string, value: string) {
    onChange({ ...draft, [key]: value });
  }

  function beginRowResize(event: ReactPointerEvent<HTMLTextAreaElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const isResizeGrip = bounds.right - event.clientX <= RESIZE_GRIP_SIZE
      && bounds.bottom - event.clientY <= RESIZE_GRIP_SIZE;
    if (!isResizeGrip) return;

    const startY = event.clientY;
    const startHeight = bounds.height;
    const resizeRow = (pointerEvent: PointerEvent) => {
      setRowHeight(Math.max(MIN_MATRIX_ROW_HEIGHT, startHeight + pointerEvent.clientY - startY));
    };
    const finishResize = () => {
      window.removeEventListener("pointermove", resizeRow);
      window.removeEventListener("pointerup", finishResize);
      window.removeEventListener("pointercancel", finishResize);
    };

    window.addEventListener("pointermove", resizeRow);
    window.addEventListener("pointerup", finishResize);
    window.addEventListener("pointercancel", finishResize);
  }

  return (
    <tr className="week-at-glance-component-row" style={rowHeight ? { height: `${rowHeight}px` } : undefined}>
      <th scope="row">{label}</th>
      {DAYS.map(([suffix, dayLabel]) => {
        const key = `${prefix}_${suffix}`;
        return (
          <td key={key}>
            <textarea
              aria-label={`${dayLabel} — ${label}`}
              rows={4}
              value={draft[key] ?? ""}
              disabled={disabled}
              style={rowHeight ? { height: `${rowHeight}px` } : undefined}
              onPointerDown={beginRowResize}
              onChange={(event) => setField(key, event.target.value)}
            />
          </td>
        );
      })}
    </tr>
  );
}

export function PlanningPdfFieldsPanel({ draft, disabled = false, onChange }: Props) {
  function setField(key: string, value: string) {
    onChange({ ...draft, [key]: value });
  }

  return (
    <section className="district-pdf-fields">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">Weekly Lesson Plan document</p>
          <h3>Review or edit the working plan</h3>
          <p className="supporting">The fields below mirror the approved district PDF in order. Complete the Instructional Planning Framework first, then review the Week at a Glance matrix. AI suggestions remain drafts until you use or edit them.</p>
        </div>
      </div>

      <details className="setup-section" open>
        <summary>Instructional Planning Framework</summary>
        <div className="form-grid framework-continuation-grid">
          <label>Unit / topic<input value={draft.unit_topic ?? ""} disabled={disabled} onChange={(event) => setField("unit_topic", event.target.value)} /></label>
          <label className="full-width">Selected authoritative standards<textarea rows={4} value={draft.standards ?? ""} readOnly aria-readonly="true" placeholder="Save authoritative standards above to populate this field." /></label>
          <label className="full-width required-field">Literacy Standards<textarea rows={3} value={draft.literacy_standards ?? ""} disabled={disabled} onChange={(event) => setField("literacy_standards", event.target.value)} required /></label>
          <label className="full-width required-field">ACT Preparation<textarea rows={3} value={draft.act_preparation ?? ""} disabled={disabled} onChange={(event) => setField("act_preparation", event.target.value)} required /></label>
          <label>Know<textarea rows={4} value={draft.know ?? ""} disabled={disabled} onChange={(event) => setField("know", event.target.value)} /></label>
          <label>Understand<textarea rows={4} value={draft.understand ?? ""} disabled={disabled} onChange={(event) => setField("understand", event.target.value)} /></label>
          <label className="full-width">Do<textarea rows={3} value={draft.do ?? ""} disabled={disabled} onChange={(event) => setField("do", event.target.value)} /></label>
          <label className="full-width">Performance-Level Descriptors / Proficiency Scale<textarea rows={3} value={draft.plds ?? ""} disabled={disabled} onChange={(event) => setField("plds", event.target.value)} /></label>
          <label className="full-width">Likely Misconceptions<textarea rows={3} value={draft.misconceptions ?? ""} disabled={disabled} onChange={(event) => setField("misconceptions", event.target.value)} /></label>
          <label>Formative Assessments<textarea rows={3} value={draft.formative ?? ""} disabled={disabled} onChange={(event) => setField("formative", event.target.value)} /></label>
          <label>Summative Assessments<textarea rows={3} value={draft.summative ?? ""} disabled={disabled} onChange={(event) => setField("summative", event.target.value)} /></label>
          <label className="full-width">Performance Task / Authentic Application<textarea rows={3} value={draft.performance_task ?? ""} disabled={disabled} onChange={(event) => setField("performance_task", event.target.value)} /></label>
          <label className="full-width">Resources<textarea rows={4} value={draft.resources ?? ""} disabled={disabled} onChange={(event) => setField("resources", event.target.value)} /></label>
        </div>
      </details>

      <details className="setup-section" open>
        <summary>Week at a Glance</summary>
        <p className="supporting">Rows match the district matrix and columns represent Monday through Friday. AI recommends cells only for scheduled instructional days.</p>
        <div className="week-at-glance-matrix-wrap">
          <table className="week-at-glance-matrix">
            <thead>
              <tr>
                <th scope="col">Instructional component</th>
                {DAYS.map(([_suffix, dayLabel]) => <th scope="col" key={dayLabel}>{dayLabel}</th>)}
              </tr>
            </thead>
            <tbody>
              {COMPONENTS.map(([prefix, label]) => (
                <WeekAtGlanceRow
                  key={prefix}
                  draft={draft}
                  disabled={disabled}
                  label={label}
                  prefix={prefix}
                  onChange={onChange}
                />
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
