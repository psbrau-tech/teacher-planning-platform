-- Progressive Course Setup keeps class/schedule creation independent from Curriculum & Pacing.
-- A teaching assignment may therefore exist briefly without a curriculum until the teacher
-- completes the dedicated Curriculum & Pacing step. Weekly planning remains blocked until
-- a curriculum is attached.

alter table public.teaching_assignments
  alter column curriculum_id drop not null;

comment on column public.teaching_assignments.curriculum_id is
  'Nullable only during Course Setup. A curriculum must be attached before weekly planning can be generated.';
