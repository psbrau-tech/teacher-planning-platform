-- Passive Product Owner telemetry for TPP feature adoption.
-- Records bounded event keys only. No teacher-entered planning/reflection text is stored here.

create table public.product_usage_events (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  actor_id uuid not null references public.profiles(id) on delete cascade,
  event_key text not null,
  occurred_at timestamptz not null default now(),
  constraint product_usage_events_key_check check (
    event_key in (
      'curriculum_excel_saved',
      'curriculum_builder_saved',
      'curriculum_reused',
      'curriculum_copy_created',
      'curriculum_exported',
      'weekly_plan_generated',
      'lesson_plan_pdf_viewed',
      'completed_packet_viewed'
    )
  )
);

create index product_usage_events_school_time_idx
  on public.product_usage_events (school_id, occurred_at desc);
create index product_usage_events_actor_time_idx
  on public.product_usage_events (actor_id, occurred_at desc);
create index product_usage_events_key_time_idx
  on public.product_usage_events (event_key, occurred_at desc);

alter table public.product_usage_events enable row level security;
revoke all on table public.product_usage_events from public, anon, authenticated;

comment on table public.product_usage_events is
  'Bounded passive product-adoption events. Stores event keys only; never teacher-entered content or student data.';

create or replace function public.record_product_usage_event(target_event_key text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor uuid := (select auth.uid());
  actor_school uuid;
  inserted_id uuid;
begin
  if actor is null or not private.has_role('teacher'::public.app_role, null) then
    raise exception 'Teacher role is required' using errcode = '42501';
  end if;

  if target_event_key not in (
    'curriculum_excel_saved',
    'curriculum_builder_saved',
    'curriculum_reused',
    'curriculum_copy_created',
    'curriculum_exported',
    'weekly_plan_generated',
    'lesson_plan_pdf_viewed',
    'completed_packet_viewed'
  ) then
    raise exception 'Unsupported product usage event' using errcode = '22023';
  end if;

  select p.school_id into actor_school
  from public.profiles p
  where p.id = actor and p.is_active;

  if actor_school is null then
    raise exception 'Active governed school context is required' using errcode = '42501';
  end if;

  insert into public.product_usage_events (school_id, actor_id, event_key)
  values (actor_school, actor, target_event_key)
  returning id into inserted_id;

  return inserted_id;
end;
$$;

revoke all on function public.record_product_usage_event(text)
  from public, anon, authenticated, service_role;
grant execute on function public.record_product_usage_event(text) to authenticated;

create or replace function public.platform_product_usage_summary(
  target_start date,
  target_end date
)
returns table (
  period_start date,
  period_end date,
  teachers_authorized integer,
  teachers_authenticated integer,
  teachers_pilot_cohort integer,
  teachers_active integer,
  classes_configured integer,
  shared_curriculum_teachers integer,
  shared_curriculum_classes integer,
  curriculum_excel_saves integer,
  curriculum_excel_teachers integer,
  curriculum_builder_saves integer,
  curriculum_builder_teachers integer,
  curriculum_reuse_events integer,
  curriculum_reuse_teachers integer,
  curriculum_copy_events integer,
  curriculum_copy_teachers integer,
  curriculum_export_events integer,
  curriculum_export_teachers integer,
  weekly_plan_generate_events integer,
  weekly_plan_generate_teachers integer,
  weekly_plans_saved integer,
  weekly_plan_teachers integer,
  ai_requests integer,
  ai_teachers integer,
  ai_fields_accepted integer,
  ai_fields_edited integer,
  ai_fields_rejected integer,
  lesson_plan_pdf_views integer,
  lesson_plan_pdf_view_teachers integer,
  lesson_plan_submissions integer,
  lesson_plan_submission_teachers integer,
  completed_packet_submissions integer,
  completed_packet_teachers integer,
  completed_packet_views integer,
  completed_packet_view_teachers integer,
  pilot_feedback_responses integer
)
language sql
stable
security definer
set search_path = ''
as $$
with bounds as (
  select
    target_start::date as start_date,
    target_end::date as end_date,
    target_start::timestamptz as start_ts,
    (target_end + 1)::timestamptz as end_ts
  where target_end >= target_start
), authorized as (
  select count(*)::integer as teachers_authorized
  from private.pilot_access_allowlist pa
  where pa.is_active
    and 'teacher'::public.app_role = any(pa.roles)
), configured as (
  select
    count(distinct p.id)::integer as teachers_authenticated,
    count(distinct p.id) filter (
      where p.created_at < timestamptz '2026-08-21 05:00:00+00'
    )::integer as teachers_pilot_cohort,
    count(distinct ta.id)::integer as classes_configured
  from public.profiles p
  join public.profile_roles pr
    on pr.profile_id = p.id
   and pr.school_id = p.school_id
   and pr.role = 'teacher'::public.app_role
  left join public.teaching_assignments ta
    on ta.teacher_id = p.id
   and ta.school_id = p.school_id
   and ta.is_active
  where p.is_active
), shared as (
  select
    count(distinct grouped.teacher_id)::integer as shared_curriculum_teachers,
    coalesce(sum(grouped.class_count), 0)::integer as shared_curriculum_classes
  from (
    select ta.teacher_id, ta.curriculum_id, count(*)::integer as class_count
    from public.teaching_assignments ta
    where ta.is_active and ta.curriculum_id is not null
    group by ta.teacher_id, ta.curriculum_id
    having count(*) > 1
  ) grouped
), telemetry as (
  select
    count(*) filter (where e.event_key = 'curriculum_excel_saved')::integer as curriculum_excel_saves,
    count(distinct e.actor_id) filter (where e.event_key = 'curriculum_excel_saved')::integer as curriculum_excel_teachers,
    count(*) filter (where e.event_key = 'curriculum_builder_saved')::integer as curriculum_builder_saves,
    count(distinct e.actor_id) filter (where e.event_key = 'curriculum_builder_saved')::integer as curriculum_builder_teachers,
    count(*) filter (where e.event_key = 'curriculum_reused')::integer as curriculum_reuse_events,
    count(distinct e.actor_id) filter (where e.event_key = 'curriculum_reused')::integer as curriculum_reuse_teachers,
    count(*) filter (where e.event_key = 'curriculum_copy_created')::integer as curriculum_copy_events,
    count(distinct e.actor_id) filter (where e.event_key = 'curriculum_copy_created')::integer as curriculum_copy_teachers,
    count(*) filter (where e.event_key = 'curriculum_exported')::integer as curriculum_export_events,
    count(distinct e.actor_id) filter (where e.event_key = 'curriculum_exported')::integer as curriculum_export_teachers,
    count(*) filter (where e.event_key = 'weekly_plan_generated')::integer as weekly_plan_generate_events,
    count(distinct e.actor_id) filter (where e.event_key = 'weekly_plan_generated')::integer as weekly_plan_generate_teachers,
    count(*) filter (where e.event_key = 'lesson_plan_pdf_viewed')::integer as lesson_plan_pdf_views,
    count(distinct e.actor_id) filter (where e.event_key = 'lesson_plan_pdf_viewed')::integer as lesson_plan_pdf_view_teachers,
    count(*) filter (where e.event_key = 'completed_packet_viewed')::integer as completed_packet_views,
    count(distinct e.actor_id) filter (where e.event_key = 'completed_packet_viewed')::integer as completed_packet_view_teachers
  from public.product_usage_events e
  cross join bounds b
  where e.occurred_at >= b.start_ts and e.occurred_at < b.end_ts
), plans as (
  select
    count(*)::integer as weekly_plans_saved,
    count(distinct ta.teacher_id)::integer as weekly_plan_teachers
  from public.weekly_plan_snapshots w
  join public.teaching_assignments ta on ta.id = w.teaching_assignment_id
  cross join bounds b
  where w.updated_at >= b.start_ts and w.updated_at < b.end_ts
), ai as (
  select
    count(*) filter (where a.succeeded)::integer as ai_requests,
    count(distinct a.teacher_id) filter (where a.succeeded)::integer as ai_teachers
  from public.ai_usage_events a
  cross join bounds b
  where a.created_at >= b.start_ts and a.created_at < b.end_ts
), decisions as (
  select
    count(*) filter (where d.decision = 'accepted')::integer as accepted,
    count(*) filter (where d.decision = 'edited')::integer as edited,
    count(*) filter (where d.decision = 'rejected')::integer as rejected
  from public.ai_suggestion_decisions d
  cross join bounds b
  where d.decided_at >= b.start_ts and d.decided_at < b.end_ts
), submissions as (
  select
    count(*) filter (where s.submission_kind = 'lesson_plan')::integer as lesson_plan_submissions,
    count(distinct s.teacher_id) filter (where s.submission_kind = 'lesson_plan')::integer as lesson_plan_submission_teachers,
    count(*) filter (where s.submission_kind = 'completed_packet')::integer as completed_packet_submissions,
    count(distinct s.teacher_id) filter (where s.submission_kind = 'completed_packet')::integer as completed_packet_teachers
  from public.weekly_plan_submissions s
  cross join bounds b
  where s.submitted_at >= b.start_ts and s.submitted_at < b.end_ts
), feedback as (
  select count(*)::integer as responses
  from public.pilot_feedback_responses r
  cross join bounds b
  where r.submitted_at >= b.start_ts and r.submitted_at < b.end_ts
), activity as (
  select count(distinct actor_id)::integer as active_teachers
  from (
    select e.actor_id
    from public.product_usage_events e cross join bounds b
    where e.occurred_at >= b.start_ts and e.occurred_at < b.end_ts
    union all
    select ta.teacher_id
    from public.weekly_plan_snapshots w
    join public.teaching_assignments ta on ta.id = w.teaching_assignment_id
    cross join bounds b
    where w.updated_at >= b.start_ts and w.updated_at < b.end_ts
    union all
    select a.teacher_id
    from public.ai_usage_events a cross join bounds b
    where a.created_at >= b.start_ts and a.created_at < b.end_ts
    union all
    select s.teacher_id
    from public.weekly_plan_submissions s cross join bounds b
    where s.submitted_at >= b.start_ts and s.submitted_at < b.end_ts
  ) actors
)
select
  b.start_date,
  b.end_date,
  coalesce(az.teachers_authorized, 0),
  coalesce(c.teachers_authenticated, 0),
  coalesce(c.teachers_pilot_cohort, 0),
  coalesce(ac.active_teachers, 0),
  coalesce(c.classes_configured, 0),
  coalesce(sh.shared_curriculum_teachers, 0),
  coalesce(sh.shared_curriculum_classes, 0),
  coalesce(t.curriculum_excel_saves, 0),
  coalesce(t.curriculum_excel_teachers, 0),
  coalesce(t.curriculum_builder_saves, 0),
  coalesce(t.curriculum_builder_teachers, 0),
  coalesce(t.curriculum_reuse_events, 0),
  coalesce(t.curriculum_reuse_teachers, 0),
  coalesce(t.curriculum_copy_events, 0),
  coalesce(t.curriculum_copy_teachers, 0),
  coalesce(t.curriculum_export_events, 0),
  coalesce(t.curriculum_export_teachers, 0),
  coalesce(t.weekly_plan_generate_events, 0),
  coalesce(t.weekly_plan_generate_teachers, 0),
  coalesce(p.weekly_plans_saved, 0),
  coalesce(p.weekly_plan_teachers, 0),
  coalesce(ai.ai_requests, 0),
  coalesce(ai.ai_teachers, 0),
  coalesce(d.accepted, 0),
  coalesce(d.edited, 0),
  coalesce(d.rejected, 0),
  coalesce(t.lesson_plan_pdf_views, 0),
  coalesce(t.lesson_plan_pdf_view_teachers, 0),
  coalesce(s.lesson_plan_submissions, 0),
  coalesce(s.lesson_plan_submission_teachers, 0),
  coalesce(s.completed_packet_submissions, 0),
  coalesce(s.completed_packet_teachers, 0),
  coalesce(t.completed_packet_views, 0),
  coalesce(t.completed_packet_view_teachers, 0),
  coalesce(f.responses, 0)
from bounds b
cross join authorized az
cross join configured c
cross join shared sh
cross join telemetry t
cross join plans p
cross join ai
cross join decisions d
cross join submissions s
cross join feedback f
cross join activity ac
where private.has_role('platform_admin'::public.app_role, null);
$$;

revoke all on function public.platform_product_usage_summary(date, date)
  from public, anon, authenticated, service_role;
grant execute on function public.platform_product_usage_summary(date, date) to authenticated;

notify pgrst, 'reload schema';
