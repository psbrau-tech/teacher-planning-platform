import React from "react";
import ReactDOM from "react-dom/client";
import { HelpPage } from "./HelpPage";
import { TeacherPlanningShell } from "./TeacherPlanningShell";
import "./workflow-overrides.css";

const helpRequested = window.location.pathname.replace(/\/+$/, "") === "/help";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {helpRequested ? <main className="standalone-help"><HelpPage roles={["teacher", "school_admin"]} /><p className="help-return"><a href="/">Return to Teacher Planning Platform</a></p></main> : <TeacherPlanningShell />}
  </React.StrictMode>,
);
