import React, { useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

type ValidationStatus = "Pending" | "Completed" | "Modified" | "Missed" | "Skipped";

type Assignment = {
  name: string;
  schedule: string;
  progress: string;
  curriculum: string;
};

type DayRecord = {
  day: string;
  lesson: string;
  minutes: number;
  status: ValidationStatus;
  reason: string;
  carryForward: boolean;
};

const assignments: Assignment[] = [
  { name: "LET 1", schedule: "1st Period · 50 minutes", progress: "Week 1", curriculum: "Army JROTC LET 1" },
  { name: "LET 2", schedule: "2nd Period · 50 minutes", progress: "Week 1", curriculum: "Army JROTC LET 2" },
  { name: "LET 3", schedule: "3rd Period · 50 minutes", progress: "Week 1", curriculum: "Army JROTC LET 3" },
  { name: "LET 4", schedule: "Afternoon Block · 90 minutes", progress: "Week 1", curriculum: "Army JROTC LET 4" },
];

const initialDays: DayRecord[] = [
  { day: "Monday", lesson: "JROTC introduction and expectations", minutes: 50, status: "Pending", reason: "", carryForward: false },
  { day: "Tuesday", lesson: "Attention; Parade Rest; At Ease; Rest", minutes: 50, status: "Pending", reason: "", carryForward: false },
  { day: "Wednesday", lesson: "Physical readiness foundations", minutes: 50, status: "Pending", reason: "", carryForward: false },
  { day: "Thursday", lesson: "Range safety rules and emergency procedures", minutes: 50, status: "Pending", reason: "", carryForward: false },
  { day: "Friday", lesson: "Application, assessment, and reflection", minutes: 50, status: "Pending", reason: "", carryForward: false },
];

function App() {
  const [view, setView] = useState<"dashboard" | "validation" | "admin">("dashboard");
  const [days, setDays] = useState<DayRecord[]>(initialDays);

  const pendingCount = useMemo(() => days.filter((day) => day.status === "Pending").length, [days]);
  const carryForwardCount = useMemo(() => days.filter((day) => day.carryForward).length, [days]);

  function updateDay(index: number, patch: Partial<DayRecord>) {
    setDays((current) => current.map((day, dayIndex) => dayIndex === index ? { ...day, ...patch } : day));
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Anniston City Schools Pilot</p>
          <h1>Teacher Planning Platform</h1>
        </div>
        <nav className="nav-actions" aria-label="Primary navigation">
          <button className="secondary" onClick={() => setView("dashboard")}>Teacher dashboard</button>
          <button className="secondary" onClick={() => setView("admin")}>Administrator report</button>
        </nav>
      </header>

      <main>
        {view === "dashboard" && (
          <>
            <section className="hero">
              <div>
                <p className="eyebrow">Week of August 10, 2026</p>
                <h2>Validate this week. Prepare the next one.</h2>
                <p>
                  Four independent curricula are scheduled against your mixed period and block day.
                  Missed instruction stays in sequence until you decide otherwise.
                </p>
              </div>
              <button className="primary" onClick={() => setView("validation")}>Start Friday validation</button>
            </section>

            <section aria-labelledby="assignments-heading">
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Teaching assignments</p>
                  <h2 id="assignments-heading">Your courses</h2>
                </div>
                <button className="secondary">Add assignment</button>
              </div>
              <div className="grid">
                {assignments.map((assignment) => (
                  <article className="card" key={assignment.name}>
                    <div className="card-row">
                      <span className="badge">{assignment.progress}</span>
                      <span className="status">Ready</span>
                    </div>
                    <h3>{assignment.name}</h3>
                    <p>{assignment.schedule}</p>
                    <small>{assignment.curriculum}</small>
                    <div className="card-actions">
                      <button className="link-button" onClick={() => setView("validation")}>Open weekly plan</button>
                      <button className="link-button muted">Curriculum</button>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="summary" aria-label="Pilot summary">
              <div><strong>4</strong><span>courses configured</span></div>
              <div><strong>{carryForwardCount}</strong><span>carry-forward alerts</span></div>
              <div><strong>1</strong><span>AI action this month</span></div>
              <div><strong>$0.0042</strong><span>estimated AI cost</span></div>
            </section>
          </>
        )}

        {view === "validation" && (
          <section className="panel" aria-labelledby="validation-heading">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">LET 1 · Friday validation</p>
                <h2 id="validation-heading">Confirm what actually happened</h2>
                <p className="supporting">Every scheduled lesson must be validated before the next week is generated.</p>
              </div>
              <button className="secondary" onClick={() => setView("dashboard")}>Back</button>
            </div>

            <div className="validation-list">
              {days.map((day, index) => (
                <article className="validation-row" key={day.day}>
                  <div className="day-block">
                    <strong>{day.day}</strong>
                    <span>{day.minutes} minutes</span>
                  </div>
                  <div className="lesson-block">
                    <strong>{day.lesson}</strong>
                    <label>
                      Status
                      <select
                        value={day.status}
                        onChange={(event) => {
                          const status = event.target.value as ValidationStatus;
                          updateDay(index, {
                            status,
                            carryForward: status === "Missed" ? true : day.carryForward,
                          });
                        }}
                      >
                        {(["Pending", "Completed", "Modified", "Missed", "Skipped"] as ValidationStatus[]).map((status) => (
                          <option key={status}>{status}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Reason or note
                      <input
                        value={day.reason}
                        onChange={(event) => updateDay(index, { reason: event.target.value })}
                        placeholder={day.status === "Missed" ? "Required for a missed lesson" : "Optional"}
                      />
                    </label>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={day.carryForward}
                        disabled={day.status === "Completed" || day.status === "Skipped"}
                        onChange={(event) => updateDay(index, { carryForward: event.target.checked })}
                      />
                      Carry this lesson forward
                    </label>
                  </div>
                </article>
              ))}
            </div>

            <div className="action-bar">
              <div>
                <strong>{pendingCount} lessons still pending</strong>
                <span>{carryForwardCount} lesson{carryForwardCount === 1 ? "" : "s"} will lead next week's queue</span>
              </div>
              <button className="primary" disabled={pendingCount > 0}>Generate next week</button>
            </div>
          </section>
        )}

        {view === "admin" && (
          <section className="panel" aria-labelledby="admin-heading">
            <div className="section-heading compact">
              <div>
                <p className="eyebrow">Synthetic pilot reporting</p>
                <h2 id="admin-heading">Administrator and cost report</h2>
                <p className="supporting">Aggregate workflow visibility without student data.</p>
              </div>
              <button className="secondary" onClick={() => setView("dashboard")}>Back</button>
            </div>

            <div className="report-grid">
              <article className="report-card"><strong>1</strong><span>teacher active</span></article>
              <article className="report-card"><strong>4</strong><span>assignments configured</span></article>
              <article className="report-card"><strong>1</strong><span>plan generated</span></article>
              <article className="report-card"><strong>1</strong><span>Friday validation complete</span></article>
              <article className="report-card"><strong>{carryForwardCount}</strong><span>lessons carried forward</span></article>
              <article className="report-card"><strong>0</strong><span>generation failures</span></article>
            </div>

            <div className="cost-panel">
              <h3>AI cost activity</h3>
              <dl>
                <div><dt>Requests</dt><dd>1</dd></div>
                <div><dt>Input tokens</dt><dd>420</dd></div>
                <div><dt>Output tokens</dt><dd>160</dd></div>
                <div><dt>Estimated cost</dt><dd>$0.0042</dd></div>
                <div><dt>Accepted by teacher</dt><dd>1</dd></div>
              </dl>
              <p>Core scheduling, validation, standards selection, and PDF generation remain available with AI disabled.</p>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
