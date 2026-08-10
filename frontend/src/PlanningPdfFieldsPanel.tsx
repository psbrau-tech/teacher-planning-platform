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
          <p className="eyebrow">Weekly Lesson Plan document</p>
          <h3>Complete the planning document in PDF order</h3>
          <p className="supporting">The fields below follow the same sequence as the Weekly Lesson Plan PDF: finish the Instructional Planning Framework first, then review the Week at a Glance matrix. AI suggestions remain drafts until you use or edit them.</p>
        </div>
      </div>

      <details className="setup-section" open>
        <summary>Instructional Planning Framework — remaining fields</summary>
        <p className="supporting">These fields continue directly from the Framework fields above and appear before the Week at a Glance in the PDF.</p>
        <div className="form-grid framework-continuation-grid">
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
          <p className="supporting">Rows match the district matrix and columns represent Monday through Friday. AI recommends cells only for scheduled instructional days. Use Prefill matching fields only when you want to copy equivalent content already present in the working plan without another AI request.</p>
          <button type="button" className="secondary" disabled={disabled} onClick={prefillMatchingFields}>Prefill matching fields</button>
        </div>
        <div className="week-at-glance-matrix-wrap">
          <table className="week-at-glance-matrix">
            <thead>
              <tr>
                <th scope="col">Instructional component</th>
                {DAYS.map(([_suffix, _dayKey, dayLabel]) => <th scope="col" key={dayLabel}>{dayLabel}</th>)}
              </tr>
            </thead>
            <tbody>
              {COMPONENTS.map(([prefix, label]) => (
                <tr key={prefix}>
                  <th scope="row">{label}</th>
                  {DAYS.map(([suffix, _dayKey, dayLabel]) => {
                    const key = `${prefix}_${suffix}`;
                    return (
                      <td key={key}>
                        <textarea
                          aria-label={`${dayLabel} — ${label}`}
                          rows={4}
                          value={draft[key] ?? ""}
                          disabled={disabled}
                          onChange={(event) => setField(key, event.target.value)}
                        />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </section>
  );
}
