-- Canonical weekly identity: every persisted planning week begins on Monday.
-- Live pilot audit before this migration found zero non-Monday rows in all four tables.

alter table public.weekly_plan_snapshots
  drop constraint if exists weekly_plan_snapshots_week_start_monday;
alter table public.weekly_plan_snapshots
  add constraint weekly_plan_snapshots_week_start_monday
  check (extract(isodow from week_start) = 1);

alter table public.weekly_plan_submissions
  drop constraint if exists weekly_plan_submissions_week_start_monday;
alter table public.weekly_plan_submissions
  add constraint weekly_plan_submissions_week_start_monday
  check (extract(isodow from week_start) = 1);

alter table public.friday_validation_snapshots
  drop constraint if exists friday_validation_snapshots_week_start_monday;
alter table public.friday_validation_snapshots
  add constraint friday_validation_snapshots_week_start_monday
  check (extract(isodow from week_start) = 1);

alter table public.weekly_standard_selections
  drop constraint if exists weekly_standard_selections_week_start_monday;
alter table public.weekly_standard_selections
  add constraint weekly_standard_selections_week_start_monday
  check (extract(isodow from week_start) = 1);

comment on constraint weekly_plan_snapshots_week_start_monday on public.weekly_plan_snapshots is
  'TPP canonical week identity requires Monday week_start.';
comment on constraint weekly_plan_submissions_week_start_monday on public.weekly_plan_submissions is
  'Immutable weekly submissions preserve the same Monday-starting week identity as their plan.';
comment on constraint friday_validation_snapshots_week_start_monday on public.friday_validation_snapshots is
  'Friday validation belongs to the Monday-starting week being closed.';
comment on constraint weekly_standard_selections_week_start_monday on public.weekly_standard_selections is
  'Weekly governed standards selection belongs to a Monday-starting planning week.';
