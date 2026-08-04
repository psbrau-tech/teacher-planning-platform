import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

const assignments = [
  { name: "LET 1", schedule: "1st Period · 50 minutes", progress: "Week 1" },
  { name: "LET 2", schedule: "2nd Period · 50 minutes", progress: "Week 1" },
  { name: "LET 3", schedule: "3rd Period · 50 minutes", progress: "Week 1" },
  { name: "LET 4", schedule: "Afternoon Block · 90 minutes", progress: "Week 1" },
];

function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Anniston City Schools Pilot</p>
          <h1>Teacher Planning Platform</h1>
        </div>
        <button className="secondary">Administrator report</button>
      </header>

      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">Week of August 10, 2026</p>
            <h2>Validate this week. Prepare the next one.</h2>
            <p>
              Four independent curricula are scheduled against your mixed period and block day.
              Missed instruction stays in sequence until you decide otherwise.
            </p>
          </div>
          <button className="primary">Start Friday validation</button>
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
                <div className="card-actions">
                  <button className="link-button">Open weekly plan</button>
                  <button className="link-button muted">Curriculum</button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="summary" aria-label="Pilot summary">
          <div><strong>4</strong><span>courses configured</span></div>
          <div><strong>0</strong><span>carry-forward alerts</span></div>
          <div><strong>0</strong><span>AI actions this month</span></div>
          <div><strong>$0.00</strong><span>estimated AI cost</span></div>
        </section>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
