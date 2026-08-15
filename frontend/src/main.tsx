import React from "react";
import ReactDOM from "react-dom/client";
import { BaselineSurveyExperience } from "./BaselineSurveyExperience";
import { DailyAssessmentAnalyticsExperience } from "./DailyAssessmentAnalyticsExperience";
import { FridayStatusExperience } from "./FridayStatusExperience";
import { OwnerActiveTimeBreakout } from "./OwnerActiveTimeBreakout";
import { OwnerReflectionIntelligenceAnalytics } from "./OwnerReflectionIntelligenceAnalytics";
import { PilotFeedbackExperience } from "./PilotFeedbackExperience";
import { PlcFacilitationArtifactExperience } from "./PlcFacilitationArtifactExperience";
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
    <DailyAssessmentAnalyticsExperience />
    <FridayStatusExperience />
    <PlcFacilitationArtifactExperience />
    <ReflectionIntelligenceExperience />
  </React.StrictMode>,
);
