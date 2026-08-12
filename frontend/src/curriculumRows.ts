import { validatePacingRowLimits } from "./pacingLimits";

export type CurriculumLessonPayload = {
  sequence: number;
  unit_title: string;
  lesson_title: string;
  estimated_minutes: number | null;
  standards: string[];
  learning_targets: string[];
  assessment: string;
  can_split: boolean;
};

function splitList(value: string): string[] {
  return value
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
}

function optionalMinutes(value: string, rowNumber: number): number | null {
  if (!value.trim()) return null;
  const minutes = Number(value);
  if (!Number.isInteger(minutes) || minutes < 1) {
    throw new Error(`Curriculum row ${rowNumber} has an invalid optional minutes override.`);
  }
  return minutes;
}

export function parseCurriculumRows(value: string): CurriculumLessonPayload[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const parts = line.split("|").map((item) => item.trim());
      const rowNumber = index + 1;
      const unit = parts[0] ?? "";
      const lesson = parts[1] ?? "";
      if (!unit || !lesson) {
        throw new Error(`Curriculum row ${rowNumber} must include a unit/topic and lesson/focus.`);
      }

      // Teacher-facing pilot format:
      // Unit / Topic | Lesson / Focus | Learning targets | Assessment / Evidence | Optional minutes override
      //
      // Continue accepting both earlier pilot formats so existing pacing content remains usable:
      // Unit | Lesson | Standards | Learning targets | Assessment | Optional minutes override
      // Unit | Lesson | Minutes | Standards | Learning targets | Assessment
      const legacyMinutes = parts.length >= 6 && /^\d+$/.test(parts[2] ?? "");
      const earlierSixColumn = parts.length >= 6 && !legacyMinutes;
      const standards = legacyMinutes ? parts[3] ?? "" : earlierSixColumn ? parts[2] ?? "" : "";
      const targets = legacyMinutes ? parts[4] ?? "" : earlierSixColumn ? parts[3] ?? "" : parts[2] ?? "";
      const assessment = legacyMinutes ? parts[5] ?? "" : earlierSixColumn ? parts[4] ?? "" : parts[3] ?? "";
      const minutesOverride = legacyMinutes ? parts[2] ?? "" : earlierSixColumn ? parts[5] ?? "" : parts[4] ?? "";

      validatePacingRowLimits({ unit, lesson, targets, assessment }, rowNumber);

      return {
        sequence: rowNumber,
        unit_title: unit,
        lesson_title: lesson,
        estimated_minutes: optionalMinutes(minutesOverride, rowNumber),
        standards: standards ? splitList(standards) : [],
        learning_targets: targets ? splitList(targets) : [],
        assessment,
        can_split: false,
      };
    });
}
