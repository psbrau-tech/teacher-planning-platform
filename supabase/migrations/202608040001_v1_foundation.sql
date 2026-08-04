create extension if not exists pgcrypto;

create type public.app_role as enum ('teacher', 'school_admin', 'platform_admin');
create type public.schedule_pattern_type as enum ('daily_period', 'daily_block', 'alternating_ab', 'selected_weekdays', 'custom');
create type public.lesson_outcome_status as enum ('planned', 'completed', 'modified', 'missed', 'not_needed');
create type public.carry_forward_action as enum ('none', 'carry_forward', 'skip', 'combine', 'manual_resequence');
create type public.document_status as enum ('queued', 'generated', 'failed');

create table public.districts (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table public.schools (
  id uuid primary key default gen_random_uuid(),
  district_id uuid not null references public.districts(id) on delete cascade,
  name text not null,
  timezone text not null default 'America/Chicago',
  created_at timestamptz not null default now()
);

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  school_id uuid references public.schools(id),
  display_name text not null,
  role public.app_role not null default 'teacher',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.academic_years (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  name text not null,
  starts_on date not null,
  ends_on date not null,
  is_active boolean not null default false,
  check (ends_on >= starts_on)
);

create table public.calendar_days (
  id uuid primary key default gen_random_uuid(),
  academic_year_id uuid not null references public.academic_years(id) on delete cascade,
  school_date date not null,
  is_instructional boolean not null default true,
  event_type text,
  event_name text,
  unique (academic_year_id, school_date)
);

create table public.curricula (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  name text not null,
  version text not null,
  standards_family text,
  is_active boolean not null default true,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now()
);

create table public.curriculum_units (
  id uuid primary key default gen_random_uuid(),
  curriculum_id uuid not null references public.curricula(id) on delete cascade,
  sequence integer not null,
  title text not null,
  unique (curriculum_id, sequence)
);

create table public.lessons (
  id uuid primary key default gen_random_uuid(),
  unit_id uuid not null references public.curriculum_units(id) on delete cascade,
  sequence integer not null,
  title text not null,
  estimated_minutes integer not null check (estimated_minutes > 0),
  minimum_minutes integer check (minimum_minutes is null or minimum_minutes > 0),
  can_split boolean not null default true,
  can_compress boolean not null default false,
  standards jsonb not null default '[]'::jsonb,
  learning_targets jsonb not null default '[]'::jsonb,
  know text,
  understand text,
  do_statement text,
  activities jsonb not null default '[]'::jsonb,
  assessments jsonb not null default '[]'::jsonb,
  resources jsonb not null default '[]'::jsonb,
  unique (unit_id, sequence)
);

create table public.teaching_assignments (
  id uuid primary key default gen_random_uuid(),
  teacher_id uuid not null references public.profiles(id) on delete cascade,
  school_id uuid not null references public.schools(id) on delete cascade,
  academic_year_id uuid not null references public.academic_years(id) on delete cascade,
  curriculum_id uuid not null references public.curricula(id),
  course_name text not null,
  course_code text,
  grade_levels text[] not null default '{}',
  section_name text,
  starts_on date not null,
  ends_on date not null,
  is_active boolean not null default true,
  check (ends_on >= starts_on)
);

create table public.meeting_patterns (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  pattern_type public.schedule_pattern_type not null,
  label text not null,
  weekdays smallint[] not null default '{}',
  cycle_day text,
  starts_at time,
  ends_at time,
  instructional_minutes integer not null check (instructional_minutes > 0),
  effective_from date not null,
  effective_to date not null,
  metadata jsonb not null default '{}'::jsonb,
  check (effective_to >= effective_from)
);

create table public.schedule_exceptions (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  exception_date date not null,
  is_available boolean not null default false,
  instructional_minutes integer,
  reason text not null,
  created_by uuid not null references public.profiles(id),
  unique (teaching_assignment_id, exception_date)
);

create table public.scheduled_lessons (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  lesson_id uuid not null references public.lessons(id),
  school_date date not null,
  segment_index integer not null default 1,
  planned_minutes integer not null check (planned_minutes > 0),
  sequence_position numeric(12,4) not null,
  is_teacher_override boolean not null default false,
  created_at timestamptz not null default now(),
  unique (teaching_assignment_id, lesson_id, school_date, segment_index)
);

create table public.instruction_records (
  id uuid primary key default gen_random_uuid(),
  scheduled_lesson_id uuid not null unique references public.scheduled_lessons(id) on delete cascade,
  status public.lesson_outcome_status not null,
  actual_minutes integer check (actual_minutes is null or actual_minutes >= 0),
  carry_forward_action public.carry_forward_action not null default 'none',
  reason text,
  teacher_notes text,
  validated_by uuid not null references public.profiles(id),
  validated_at timestamptz not null default now()
);

create table public.weekly_plan_snapshots (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  week_start date not null,
  week_end date not null,
  source_data jsonb not null,
  approved_by uuid references public.profiles(id),
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  unique (teaching_assignment_id, week_start)
);

create table public.generated_documents (
  id uuid primary key default gen_random_uuid(),
  weekly_plan_snapshot_id uuid not null references public.weekly_plan_snapshots(id) on delete cascade,
  template_key text not null default 'anniston_hqi_v1',
  status public.document_status not null default 'queued',
  editable_storage_path text,
  flattened_storage_path text,
  error_message text,
  generated_by uuid not null references public.profiles(id),
  created_at timestamptz not null default now()
);

create table public.ai_usage_events (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  teacher_id uuid references public.profiles(id),
  teaching_assignment_id uuid references public.teaching_assignments(id),
  feature text not null,
  model text not null,
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  cached_tokens integer not null default 0,
  estimated_cost_usd numeric(12,6) not null default 0,
  retry_count integer not null default 0,
  succeeded boolean not null,
  accepted_by_teacher boolean,
  created_at timestamptz not null default now()
);

create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  school_id uuid references public.schools(id),
  actor_id uuid references public.profiles(id),
  entity_type text not null,
  entity_id uuid,
  action text not null,
  before_data jsonb,
  after_data jsonb,
  reason text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
alter table public.teaching_assignments enable row level security;
alter table public.scheduled_lessons enable row level security;
alter table public.instruction_records enable row level security;
alter table public.weekly_plan_snapshots enable row level security;
alter table public.generated_documents enable row level security;
alter table public.ai_usage_events enable row level security;

create policy profiles_self_read on public.profiles for select using (id = auth.uid());
create policy assignments_teacher_access on public.teaching_assignments for all using (teacher_id = auth.uid()) with check (teacher_id = auth.uid());
create policy scheduled_lessons_teacher_read on public.scheduled_lessons for select using (
  exists (select 1 from public.teaching_assignments a where a.id = teaching_assignment_id and a.teacher_id = auth.uid())
);
create policy instruction_records_teacher_access on public.instruction_records for all using (
  exists (
    select 1 from public.scheduled_lessons s
    join public.teaching_assignments a on a.id = s.teaching_assignment_id
    where s.id = scheduled_lesson_id and a.teacher_id = auth.uid()
  )
) with check (
  exists (
    select 1 from public.scheduled_lessons s
    join public.teaching_assignments a on a.id = s.teaching_assignment_id
    where s.id = scheduled_lesson_id and a.teacher_id = auth.uid()
  )
);
create policy weekly_plans_teacher_access on public.weekly_plan_snapshots for all using (
  exists (select 1 from public.teaching_assignments a where a.id = teaching_assignment_id and a.teacher_id = auth.uid())
) with check (
  exists (select 1 from public.teaching_assignments a where a.id = teaching_assignment_id and a.teacher_id = auth.uid())
);
create policy generated_documents_teacher_access on public.generated_documents for all using (
  exists (
    select 1 from public.weekly_plan_snapshots w
    join public.teaching_assignments a on a.id = w.teaching_assignment_id
    where w.id = weekly_plan_snapshot_id and a.teacher_id = auth.uid()
  )
) with check (
  exists (
    select 1 from public.weekly_plan_snapshots w
    join public.teaching_assignments a on a.id = w.teaching_assignment_id
    where w.id = weekly_plan_snapshot_id and a.teacher_id = auth.uid()
  )
);
