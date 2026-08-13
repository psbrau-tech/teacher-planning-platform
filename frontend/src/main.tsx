import React from "react";
import ReactDOM from "react-dom/client";
import { PilotFeedbackExperience } from "./PilotFeedbackExperience";
import { ProductUsageObserver } from "./ProductUsageObserver";
import { TeacherPlanningShell } from "./TeacherPlanningShell";
import "./workflow-overrides.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TeacherPlanningShell />
    <PilotFeedbackExperience />
    <ProductUsageObserver />
  </React.StrictMode>,
);
