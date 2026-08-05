create table public.document_templates (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  template_key text not null,
  display_name text not null,
  version text not null,
  storage_path text not null,
  sha256 text not null,
  field_contract jsonb not null,
  is_active boolean not null default true,
  created_by uuid references public.profiles(id),
  created_at timestamptz not null default now(),
  unique (school_id, template_key, version)
);

alter table public.generated_documents
  add column if not exists document_template_id uuid references public.document_templates(id),
  add column if not exists payload_sha256 text,
  add column if not exists is_flattened boolean not null default false;

create table public.ai_budgets (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  monthly_limit_usd numeric(12,2),
  warning_threshold_percent integer not null default 80 check (warning_threshold_percent between 1 and 100),
  hard_stop_enabled boolean not null default false,
  ai_enabled boolean not null default true,
  feature_limits jsonb not null default '{}'::jsonb,
  effective_from date not null,
  effective_to date,
  created_at timestamptz not null default now(),
  check (monthly_limit_usd is null or monthly_limit_usd >= 0),
  check (effective_to is null or effective_to >= effective_from)
);

create index if not exists idx_scheduled_lessons_assignment_date
  on public.scheduled_lessons (teaching_assignment_id, school_date);
create index if not exists idx_instruction_records_status
  on public.instruction_records (status, validated_at);
create index if not exists idx_generated_documents_status
  on public.generated_documents (status, created_at);
create index if not exists idx_ai_usage_school_created
  on public.ai_usage_events (school_id, created_at);

create or replace view public.school_admin_usage_summary as
select
  s.id as school_id,
  count(distinct p.id) filter (where p.role = 'teacher') as teachers_configured,
  count(distinct ta.teacher_id) as teachers_with_assignments,
  count(distinct ta.id) as assignments_configured,
  count(distinct w.id) as weekly_plans_created,
  count(distinct w.id) filter (where w.approved_at is not null) as weekly_plans_approved,
  count(distinct ir.id) as instruction_records_validated,
  count(distinct ir.id) filter (where ir.carry_forward_action = 'carry_forward') as lessons_carried_forward,
  count(distinct gd.id) as documents_requested,
  count(distinct gd.id) filter (where gd.status = 'generated') as documents_generated,
  count(distinct gd.id) filter (where gd.status = 'failed') as document_generation_failures
from public.schools s
left join public.profiles p on p.school_id = s.id
left join public.teaching_assignments ta on ta.school_id = s.id
left join public.weekly_plan_snapshots w on w.teaching_assignment_id = ta.id
left join public.scheduled_lessons sl on sl.teaching_assignment_id = ta.id
left join public.instruction_records ir on ir.scheduled_lesson_id = sl.id
left join public.generated_documents gd on gd.weekly_plan_snapshot_id = w.id
group by s.id;

create or replace view public.school_ai_cost_summary as
select
  school_id,
  date_trunc('month', created_at) as usage_month,
  count(*) as request_count,
  count(*) filter (where succeeded) as successful_requests,
  count(*) filter (where not succeeded) as failed_requests,
  sum(input_tokens) as input_tokens,
  sum(output_tokens) as output_tokens,
  sum(cached_tokens) as cached_tokens,
  sum(estimated_cost_usd) as estimated_cost_usd,
  count(*) filter (where accepted_by_teacher is true) as accepted_outputs,
  count(*) filter (where accepted_by_teacher is false) as discarded_outputs
from public.ai_usage_events
group by school_id, date_trunc('month', created_at);

alter table public.document_templates enable row level security;
alter table public.ai_budgets enable row level security;

create policy document_templates_school_read on public.document_templates
for select using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid() and p.school_id = document_templates.school_id
  )
);

create policy ai_budgets_admin_read on public.ai_budgets
for select using (
  exists (
    select 1 from public.profiles p
    where p.id = auth.uid()
      and p.school_id = ai_budgets.school_id
      and p.role in ('school_admin', 'platform_admin')
  )
);
