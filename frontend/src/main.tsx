import React from "react";
import ReactDOM from "react-dom/client";
import { AdminWeeklyDigestAction } from "./AdminWeeklyDigestAction";
import { BaselineSurveyExperience } from "./BaselineSurveyExperience";
import { OwnerActiveTimeBreakout } from "./OwnerActiveTimeBreakout";
import { OwnerReflectionIntelligenceAnalytics } from "./OwnerReflectionIntelligenceAnalytics";
import { PilotFeedbackExperience } from "./PilotFeedbackExperience";
import { ProductUsageObserver } from "./ProductUsageObserver";
import { ReflectionIntelligenceExperience } from "./ReflectionIntelligenceExperience";
import { TeacherPlanningShell } from "./TeacherPlanningShell";
import "./workflow-overrides.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <TeacherPlanningShell />
    <BaselineSurveyExperience />
    <PilotFeedbackExperience />
    <ProductUsageObserver />
    <OwnerActiveTimeBreakout />
    <OwnerReflectionIntelligenceAnalytics />
    <ReflectionIntelligenceExperience />
    <AdminWeeklyDigestAction />
  </React.StrictMode>,
);
