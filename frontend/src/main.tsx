import React from "react";
import ReactDOM from "react-dom/client";
import { AdminSelectedTeacherUsagePortal } from "./AdminSelectedTeacherUsagePortal";
import { BaselineSurveyExperience } from "./BaselineSurveyExperience";
import { OwnerActiveTimeBreakout } from "./OwnerActiveTimeBreakout";
import { PilotFeedbackExperience } from "./PilotFeedbackExperience";
import { ProductUsageObserver } from "./ProductUsageObserver";
import { TeacherPlanningShell } from "./TeacherPlanningShell";
import "./workflow-overrides.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TeacherPlanningShell />
    <BaselineSurveyExperience />
    <PilotFeedbackExperience />
    <ProductUsageObserver />
    <OwnerActiveTimeBreakout />
    <AdminSelectedTeacherUsagePortal />
  </React.StrictMode>,
);
