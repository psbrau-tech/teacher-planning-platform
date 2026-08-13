export type ProductUsageEventKey =
  | "curriculum_excel_saved"
  | "curriculum_builder_saved"
  | "curriculum_reused"
  | "curriculum_copy_created"
  | "curriculum_exported"
  | "weekly_plan_generated"
  | "lesson_plan_pdf_viewed"
  | "completed_packet_viewed";

export function recordProductUsage(accessToken: string, eventKey: ProductUsageEventKey): void {
  if (!accessToken) return;
  void fetch("/api/v1/product-usage", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ event_key: eventKey }),
  }).catch(() => {
    // Product telemetry must never interrupt or block a teacher workflow.
  });
}
