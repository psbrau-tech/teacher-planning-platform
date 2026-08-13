import React from "react";
import ReactDOM from "react-dom/client";
import { PilotFeedbackExperience } from "./PilotFeedbackExperience";
import { TeacherPlanningShell } from "./TeacherPlanningShell";
import "./workflow-overrides.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TeacherPlanningShell />
    <PilotFeedbackExperience />
  </React.StrictMode>,
);
