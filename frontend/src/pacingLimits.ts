export const PACING_LIMITS = {
  unit: 300,
  lesson: 1000,
  targets: 3000,
  assessment: 2000,
} as const;

export type PacingTextField = keyof typeof PACING_LIMITS;

type PacingTextRow = {
  unit: string;
  lesson: string;
  targets: string;
  assessment: string;
};

const FIELD_LABELS: Record<PacingTextField, string> = {
  unit: "Unit / Topic",
  lesson: "Lesson / Focus",
  targets: "Learning Target(s)",
  assessment: "Assessment / Evidence",
};

export function validatePacingRowLimits(row: PacingTextRow, rowNumber: number): void {
  (Object.keys(PACING_LIMITS) as PacingTextField[]).forEach((field) => {
    const limit = PACING_LIMITS[field];
    if (row[field].length > limit) {
      throw new Error(
        `Lesson ${rowNumber} — ${FIELD_LABELS[field]} exceeds the ${limit.toLocaleString()} character limit.`,
      );
    }
  });
}
