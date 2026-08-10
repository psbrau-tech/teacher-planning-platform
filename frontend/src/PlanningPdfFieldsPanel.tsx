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

export function PlanningPdfFieldsPanel({ draft, disabled = false, onChange }: Props) {
  function setField(key: string, value: string) {
    onChange({ ...draft, [key]: value });
  }

  function prefillMatchingFields() {
    const next = { ...draft };
    for (const [suffix] of DAYS) {
      if (!next[`clt_${suffix}`]?.trim() && draft.learning_targets?.trim()) next[`clt_${suffix}`] = draft.learning_targets;
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
          <h3>Review or edit the working plan</h3>
          <p className="supporting">The Instructional Planning Framework is presented as one continuous section in the same logical order as the district PDF. Week at a Glance begins only after the Framework is complete. AI suggestions remain drafts until you use or edit them.</p>
        </div>
      </div>

      <details className="setup-section" open>
        <summary>Instructional Planning Framework</summary>
        <div className="form-grid framework-continuation-grid">
          <label>Unit / topic<input value={draft.unit_topic ?? ""} disabled={disabled} onChange={(event) => setField("unit_topic", event.target.value)} /></label>
          <label className="full-width">Selected authoritative standards<textarea rows={4} value={draft.standards ?? ""} readOnly aria-readonly="true" placeholder="Save authoritative standards above to populate this field." /></label>
          <label>Know<textarea rows={4} value={draft.know ?? ""} disabled={disabled} onChange={(event) => setField("know", event.target.value)} /></label>
          <label>Understand<textarea rows={4} value={draft.understand ?? ""} disabled={disabled} onChange={(event) => setField("understand", event.target.value)} /></label>
          <label className="full-width">Do<textarea rows={3} value={draft.do ?? ""} disabled={disabled} onChange={(event) => setField("do", event.target.value)} /></label>
          <label className="full-width">Performance-Level Descriptors / Proficiency Scale<textarea rows={3} value={draft.plds ?? ""} disabled={disabled} onChange={(event) => setField("plds", event.target.value)} /></label>
          <label className="full-width">Likely Misconceptions<textarea rows={3} value={draft.misconceptions ?? ""} disabled={disabled} onChange={(event) => setField("misconceptions", event.target.value)} /></label>
          <label>Formative Assessments<textarea rows={3} value={draft.formative ?? ""} disabled={disabled} onChange={(event) => setField("formative", event.target.value)} /></label>
          <label>Summative Assessments<textarea rows={3} value={draft.summative ?? ""} disabled={disabled} onChange={(event) => setField("summative", event.target.value)} /></label>
          <label className="full-width">Performance Task / Authentic Application<textarea rows={3} value={draft.performance_task ?? ""} disabled={disabled} onChange={(event) => setField("performance_task", event.target.value)} /></label>
          <label className="full-width">Resources<textarea rows={4} value={draft.resources ?? ""} disabled={disabled} onChange={(event) => setField("resources", event.target.value)} /></label>
          <label className="full-width required-field">Literacy Standards<textarea rows={3} value={draft.literacy_standards ?? ""} disabled={disabled} onChange={(event) => setField("literacy_standards", event.target.value)} required /></label>
          <label className="full-width required-field">ACT Preparation<textarea rows={3} value={draft.act_preparation ?? ""} disabled={disabled} onChange={(event) => setField("act_preparation", event.target.value)} required /></label>
        </div>
      </details>

      <details className="setup-section">
        <summary>Supporting planning notes</summary>
        <p className="supporting">These teacher planning notes support AI assistance and Week-at-a-Glance development but are not separate weekday boxes in the district Framework.</p>
        <div className="form-grid">
          <label className="full-width">Learning targets<textarea rows={3} value={draft.learning_targets ?? ""} disabled={disabled} onChange={(event) => setField("learning_targets", event.target.value)} /></label>
          <label className="full-width">Activities<textarea rows={4} value={draft.activities ?? ""} disabled={disabled} onChange={(event) => setField("activities", event.target.value)} /></label>
          <label>Assessments<textarea rows={4} value={draft.assessments ?? ""} disabled={disabled} onChange={(event) => setField("assessments", event.target.value)} /></label>
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
                {DAYS.map(([_suffix, dayLabel]) => <th scope="col" key={dayLabel}>{dayLabel}</th>)}
              </tr>
            </thead>
            <tbody>
              {COMPONENTS.map(([prefix, label]) => (
                <tr key={prefix}>
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
