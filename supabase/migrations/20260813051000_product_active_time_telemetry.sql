-- Conservative active-interaction telemetry for Platform Owner product measurement.
-- Records only fixed 30-second heartbeat event keys. No planning/reflection content is stored.
-- School/district administrators receive no access path to these metrics.

alter table public.product_usage_events
  drop constraint product_usage_events_key_check;

alter table public.product_usage_events
  add constraint product_usage_events_key_check check (
    event_key in (
      'curriculum_excel_saved',
      'curriculum_builder_saved',
      'curriculum_reused',
      'curriculum_copy_created',
      'curriculum_exported',
      'weekly_plan_generated',
      'lesson_plan_pdf_viewed',
      'completed_packet_viewed',
      'active_course_setup_30s',
      'active_weekly_planning_30s',
      'active_friday_closeout_30s'
    )
  );

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
    'completed_packet_viewed',
    'active_course_setup_30s',
    'active_weekly_planning_30s',
    'active_friday_closeout_30s'
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

create or replace function public.platform_product_active_time_summary(
  target_start date,
  target_end date
)
returns table (
  period_start date,
  period_end date,
  active_time_teachers integer,
  course_setup_total_seconds integer,
  weekly_planning_total_seconds integer,
  friday_closeout_total_seconds integer,
  median_course_setup_seconds_per_teacher integer,
  median_weekly_planning_seconds_per_teacher_week integer,
  median_friday_closeout_seconds_per_teacher_week integer,
  onboarding_weekly_planning_teacher_weeks integer,
  median_onboarding_weekly_planning_seconds integer,
  steady_state_weekly_planning_teacher_weeks integer,
  median_steady_state_weekly_planning_seconds integer
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
), first_seen as (
  select
    e.actor_id,
    min(e.occurred_at) as first_active_at
  from public.product_usage_events e
  where e.event_key in (
    'active_course_setup_30s',
    'active_weekly_planning_30s',
    'active_friday_closeout_30s'
  )
  group by e.actor_id
), selected as (
  select
    e.actor_id,
    e.event_key,
    e.occurred_at,
    fs.first_active_at,
    e.occurred_at < fs.first_active_at + interval '14 days' as onboarding
  from public.product_usage_events e
  join first_seen fs on fs.actor_id = e.actor_id
  cross join bounds b
  where e.occurred_at >= b.start_ts
    and e.occurred_at < b.end_ts
    and e.event_key in (
      'active_course_setup_30s',
      'active_weekly_planning_30s',
      'active_friday_closeout_30s'
    )
), course_by_teacher as (
  select actor_id, count(*)::integer * 30 as seconds
  from selected
  where event_key = 'active_course_setup_30s'
  group by actor_id
), workflow_by_teacher_week as (
  select
    actor_id,
    date_trunc('week', occurred_at)::date as week_start,
    event_key,
    onboarding,
    count(*)::integer * 30 as seconds
  from selected
  where event_key in ('active_weekly_planning_30s', 'active_friday_closeout_30s')
  group by actor_id, date_trunc('week', occurred_at)::date, event_key, onboarding
), totals as (
  select
    count(distinct actor_id)::integer as active_time_teachers,
    count(*) filter (where event_key = 'active_course_setup_30s')::integer * 30
      as course_setup_total_seconds,
    count(*) filter (where event_key = 'active_weekly_planning_30s')::integer * 30
      as weekly_planning_total_seconds,
    count(*) filter (where event_key = 'active_friday_closeout_30s')::integer * 30
      as friday_closeout_total_seconds
  from selected
), medians as (
  select
    coalesce((select percentile_disc(0.5) within group (order by seconds) from course_by_teacher), 0)::integer
      as median_course_setup_seconds_per_teacher,
    coalesce((
      select percentile_disc(0.5) within group (order by seconds)
      from workflow_by_teacher_week
      where event_key = 'active_weekly_planning_30s'
    ), 0)::integer as median_weekly_planning_seconds_per_teacher_week,
    coalesce((
      select percentile_disc(0.5) within group (order by seconds)
      from workflow_by_teacher_week
      where event_key = 'active_friday_closeout_30s'
    ), 0)::integer as median_friday_closeout_seconds_per_teacher_week,
    (select count(*)::integer from workflow_by_teacher_week
      where event_key = 'active_weekly_planning_30s' and onboarding)
      as onboarding_weekly_planning_teacher_weeks,
    coalesce((
      select percentile_disc(0.5) within group (order by seconds)
      from workflow_by_teacher_week
      where event_key = 'active_weekly_planning_30s' and onboarding
    ), 0)::integer as median_onboarding_weekly_planning_seconds,
    (select count(*)::integer from workflow_by_teacher_week
      where event_key = 'active_weekly_planning_30s' and not onboarding)
      as steady_state_weekly_planning_teacher_weeks,
    coalesce((
      select percentile_disc(0.5) within group (order by seconds)
      from workflow_by_teacher_week
      where event_key = 'active_weekly_planning_30s' and not onboarding
    ), 0)::integer as median_steady_state_weekly_planning_seconds
)
select
  b.start_date,
  b.end_date,
  coalesce(t.active_time_teachers, 0),
  coalesce(t.course_setup_total_seconds, 0),
  coalesce(t.weekly_planning_total_seconds, 0),
  coalesce(t.friday_closeout_total_seconds, 0),
  coalesce(m.median_course_setup_seconds_per_teacher, 0),
  coalesce(m.median_weekly_planning_seconds_per_teacher_week, 0),
  coalesce(m.median_friday_closeout_seconds_per_teacher_week, 0),
  coalesce(m.onboarding_weekly_planning_teacher_weeks, 0),
  coalesce(m.median_onboarding_weekly_planning_seconds, 0),
  coalesce(m.steady_state_weekly_planning_teacher_weeks, 0),
  coalesce(m.median_steady_state_weekly_planning_seconds, 0)
from bounds b
cross join totals t
cross join medians m
where private.has_role('platform_admin'::public.app_role, null);
$$;

revoke all on function public.platform_product_active_time_summary(date, date)
  from public, anon, authenticated, service_role;
grant execute on function public.platform_product_active_time_summary(date, date) to authenticated;

comment on function public.platform_product_active_time_summary(date, date) is
  'Platform Owner-only aggregate active TPP interaction time. Not total planning time and not an administrator teacher-performance measure.';

notify pgrst, 'reload schema';
