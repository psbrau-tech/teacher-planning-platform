type Props = {
  draft: Record<string, string>;
  disabled?: boolean;
  onChange: (next: Record<string, string>) => void;
};

const DAYS = [
  ["mon", "monday", "Monday"],
  ["tue", "tuesday", "Tuesday"],
  ["wed", "wednesday", "Wednesday"],
  ["thu", "thursday", "Thursday"],
  ["fri", "friday", "Friday"],
] as const;

const COMPONENTS = [
  ["clt", "Clear learning target & success criteria"],
  ["rrt", "Rigorous & relevant task"],
  ["cfu", "Checks for understanding"],
  ["ri", "Responsive instruction"],
  ["sic", "Strong instructional culture"],
  ["esl", "Evidence of student learning"],
] as const;

export function PlanningPdfFieldsPanel({ draft, disabled = false, onChange }: Props) {
  function setField(key: string, value: string) {
    onChange({ ...draft, [key]: value });
  }

  function prefillMatchingFields() {
    const next = { ...draft };
    for (const [suffix, dayKey] of DAYS) {
      if (!next[`clt_${suffix}`]?.trim() && draft.learning_targets?.trim()) next[`clt_${suffix}`] = draft.learning_targets;
      if (!next[`rrt_${suffix}`]?.trim() && draft[dayKey]?.trim()) next[`rrt_${suffix}`] = draft[dayKey];
      if (!next[`cfu_${suffix}`]?.trim() && (draft.formative?.trim() || draft.assessments?.trim())) next[`cfu_${suffix}`] = draft.formative?.trim() || draft.assessments;
      if (!next[`ri_${suffix}`]?.trim() && draft.activities?.trim()) next[`ri_${suffix}`] = draft.activities;
      if (!next[`esl_${suffix}`]?.trim() && draft.assessments?.trim()) next[`esl_${suffix}`] = draft.assessments;
    }
    onChange(next);
  }

  return (
    <section className="district-pdf-fields">
      <div className="section-heading compact">
        <div>
          <p className="eyebrow">District planning document details</p>
          <h3>Complete the fields that feed the official weekly lesson plan PDF</h3>
          <p className="supporting">These fields map directly to the Instructional Planning Framework and Week at a Glance. TPP never invents missing district-required content.</p>
        </div>
      </div>

      <details className="setup-section" open>
        <summary>Instructional Planning Framework details</summary>
        <div className="form-grid">
          <label className="full-width">Performance-Level Descriptors / Proficiency Scale<textarea rows={3} value={draft.plds ?? ""} disabled={disabled} onChange={(event) => setField("plds", event.target.value)} /></label>
          <label className="full-width">Likely Misconceptions<textarea rows={3} value={draft.misconceptions ?? ""} disabled={disabled} onChange={(event) => setField("misconceptions", event.target.value)} /></label>
          <label>Formative Assessments<textarea rows={3} value={draft.formative ?? ""} disabled={disabled} onChange={(event) => setField("formative", event.target.value)} /></label>
          <label>Summative Assessments<textarea rows={3} value={draft.summative ?? ""} disabled={disabled} onChange={(event) => setField("summative", event.target.value)} /></label>
          <label className="full-width">Performance Task / Authentic Application<textarea rows={3} value={draft.performance_task ?? ""} disabled={disabled} onChange={(event) => setField("performance_task", event.target.value)} /></label>
        </div>
      </details>

      <details className="setup-section" open>
        <summary>Week at a Glance</summary>
        <div className="section-heading compact">
          <p className="supporting">Complete the six instructional components for each scheduled day. Use the prefill button to copy only content that already has an equivalent in the working plan.</p>
          <button type="button" className="secondary" disabled={disabled} onClick={prefillMatchingFields}>Prefill matching fields</button>
        </div>
        <div className="week-at-glance-editor">
          {DAYS.map(([suffix, _dayKey, dayLabel]) => (
            <article className="week-at-glance-day" key={suffix}>
              <h4>{dayLabel}</h4>
              {COMPONENTS.map(([prefix, label]) => {
                const key = `${prefix}_${suffix}`;
                return <label key={key}>{label}<textarea rows={2} value={draft[key] ?? ""} disabled={disabled} onChange={(event) => setField(key, event.target.value)} /></label>;
              })}
            </article>
          ))}
        </div>
      </details>
    </section>
  );
}
