-- Curriculum pacing normally derives instructional minutes from the teaching
-- assignment's meeting pattern. The Excel pacing template intentionally leaves
-- the optional minutes override blank unless a lesson needs a different duration.
-- Keep the positive-value check for explicit overrides, but allow NULL so a full
-- year workbook can be saved without manufacturing per-lesson times.

alter table public.lessons
  alter column estimated_minutes drop not null;

comment on column public.lessons.estimated_minutes is
  'Optional lesson-specific minutes override. NULL means use the teaching assignment schedule.';
