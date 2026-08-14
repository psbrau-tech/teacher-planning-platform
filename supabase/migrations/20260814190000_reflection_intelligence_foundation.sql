-- Reflection Intelligence foundation for teacher-authored professional reflections.
--
-- Guardrails:
--   * source only immutable, explicitly submitted completed weekly packets;
--   * no student data is authorized;
--   * private teacher source is available only to that teacher;
--   * school synthesis source is anonymous and school-scoped;
--   * school themes require at least two distinct teacher sources in application logic;
--   * reflection intelligence is instructional synthesis, never teacher evaluation.

alter table public.ai_usage_events
  add column if not exists actor_id uuid references public.profiles(id) on delete set null;

update public.ai_usage_events
set actor_id = teacher_id
where actor_id is null and teacher_id is not null;

comment on column public.ai_usage_events.actor_id is
  'Governed professional user who invoked the AI feature. teacher_id remains populated for teacher planning requests; administrator synthesis requests use actor_id without pretending the administrator is a teacher.';

create table public.reflection_intelligence_events (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  actor_id uuid not null references public.profiles(id) on delete cascade,
  event_key text not null,
  occurred_at timestamptz not null default now(),
  constraint reflection_intelligence_events_key_check check (
    event_key in (
      'teacher_recap_generated',
      'school_plc_brief_generated',
      'plc_handout_viewed'
    )
  )
);

create index reflection_intelligence_events_school_time_idx
  on public.reflection_intelligence_events (school_id, occurred_at desc);
create index reflection_intelligence_events_actor_time_idx
  on public.reflection_intelligence_events (actor_id, occurred_at desc);
create index reflection_intelligence_events_key_time_idx
  on public.reflection_intelligence_events (event_key, occurred_at desc);

alter table public.reflection_intelligence_events enable row level security;
revoke all on table public.reflection_intelligence_events
  from public, anon, authenticated, service_role;

comment on table public.reflection_intelligence_events is
  'Content-free adoption telemetry for Reflection Intelligence. Event keys only; no planning text, reflection text, generated insight text, student data, or teacher-quality score.';

create or replace function public.teacher_reflection_intelligence_source(
  target_week_start date,
  target_lookback_weeks integer default 12
)
returns table (
  source_ref integer,
  course_name text,
  week_start date,
  reflection_text text,
  submitted_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  with authorized as (
    select (select auth.uid()) as actor
    where (select auth.uid()) is not null
      and private.has_role('teacher'::public.app_role, null)
      and target_lookback_weeks between 4 and 12
  ), latest as (
    select distinct on (wps.teaching_assignment_id, wps.week_start)
      wps.teacher_id,
      ta.course_name,
      wps.week_start,
      wps.source_data ->> 'reflection' as reflection_text,
      wps.submitted_at,
      wps.revision
    from public.weekly_plan_submissions wps
    join public.teaching_assignments ta on ta.id = wps.teaching_assignment_id
    join authorized a on a.actor = wps.teacher_id
    where wps.submission_kind = 'completed_packet'
      and wps.week_start between
        (target_week_start - ((target_lookback_weeks - 1) * 7))
        and target_week_start
      and nullif(btrim(coalesce(wps.source_data ->> 'reflection', '')), '') is not null
    order by wps.teaching_assignment_id, wps.week_start, wps.revision desc, wps.submitted_at desc
  )
  select
    row_number() over (order by latest.week_start, latest.course_name)::integer as source_ref,
    latest.course_name,
    latest.week_start,
    latest.reflection_text,
    latest.submitted_at
  from latest
  order by latest.week_start, latest.course_name
$$;

revoke all on function public.teacher_reflection_intelligence_source(date, integer)
  from public, anon, authenticated, service_role;
grant execute on function public.teacher_reflection_intelligence_source(date, integer)
  to authenticated;

comment on function public.teacher_reflection_intelligence_source(date, integer) is
  'Returns only the authenticated teacher own immutable completed-packet reflections for a bounded 4-12 week private recap window.';

create or replace function public.school_reflection_intelligence_source(
  target_school_id uuid,
  target_week_start date
)
returns table (
  source_ref integer,
  week_start date,
  reflection_text text,
  submitted_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  with authorized as (
    select 1
    where (select auth.uid()) is not null
      and private.can_report_school(target_school_id)
  ), latest as (
    select distinct on (wps.teacher_id, wps.teaching_assignment_id, wps.week_start)
      wps.teacher_id,
      wps.teaching_assignment_id,
      wps.week_start,
      wps.source_data ->> 'reflection' as reflection_text,
      wps.submitted_at,
      wps.revision
    from public.weekly_plan_submissions wps
    join authorized on true
    where wps.school_id = target_school_id
      and wps.submission_kind = 'completed_packet'
      and wps.week_start = target_week_start
      and nullif(btrim(coalesce(wps.source_data ->> 'reflection', '')), '') is not null
    order by
      wps.teacher_id,
      wps.teaching_assignment_id,
      wps.week_start,
      wps.revision desc,
      wps.submitted_at desc
  ), anonymous as (
    select
      dense_rank() over (order by latest.teacher_id)::integer as source_ref,
      latest.week_start,
      latest.reflection_text,
      latest.submitted_at,
      latest.teaching_assignment_id
    from latest
  )
  select
    anonymous.source_ref,
    anonymous.week_start,
    anonymous.reflection_text,
    anonymous.submitted_at
  from anonymous
  order by anonymous.source_ref, anonymous.teaching_assignment_id
$$;

revoke all on function public.school_reflection_intelligence_source(uuid, date)
  from public, anon, authenticated, service_role;
grant execute on function public.school_reflection_intelligence_source(uuid, date)
  to authenticated;

comment on function public.school_reflection_intelligence_source(uuid, date) is
  'Returns school-scoped immutable completed-packet reflections to an authorized reporting administrator using anonymous per-teacher source references; teacher identity is not returned.';

create or replace function public.record_reflection_intelligence_event(
  target_event_key text,
  target_school_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor uuid := (select auth.uid());
  actor_school uuid;
  effective_school uuid;
  inserted_id uuid;
begin
  if actor is null then
    raise exception 'Authenticated professional user is required' using errcode = '42501';
  end if;

  if target_event_key not in (
    'teacher_recap_generated',
    'school_plc_brief_generated',
    'plc_handout_viewed'
  ) then
    raise exception 'Unsupported Reflection Intelligence event' using errcode = '22023';
  end if;

  select p.school_id into actor_school
  from public.profiles p
  where p.id = actor and p.is_active;

  if actor_school is null then
    raise exception 'Active governed school context is required' using errcode = '42501';
  end if;

  if target_event_key = 'teacher_recap_generated' then
    if not private.has_role('teacher'::public.app_role, actor_school) then
      raise exception 'Teacher role is required' using errcode = '42501';
    end if;
    effective_school := actor_school;
  else
    effective_school := coalesce(target_school_id, actor_school);
    if not private.can_report_school(effective_school) then
      raise exception 'School reporting access is required' using errcode = '42501';
    end if;
  end if;

  insert into public.reflection_intelligence_events (school_id, actor_id, event_key)
  values (effective_school, actor, target_event_key)
  returning id into inserted_id;

  return inserted_id;
end;
$$;

revoke all on function public.record_reflection_intelligence_event(text, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.record_reflection_intelligence_event(text, uuid)
  to authenticated;

create or replace function public.platform_reflection_intelligence_usage(
  target_start date,
  target_end date
)
returns table (
  period_start date,
  period_end date,
  teacher_recaps_generated integer,
  teacher_recap_users integer,
  school_plc_briefs_generated integer,
  plc_brief_users integer,
  plc_handouts_viewed integer,
  plc_handout_users integer
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    target_start,
    target_end,
    count(*) filter (where e.event_key = 'teacher_recap_generated')::integer,
    count(distinct e.actor_id) filter (where e.event_key = 'teacher_recap_generated')::integer,
    count(*) filter (where e.event_key = 'school_plc_brief_generated')::integer,
    count(distinct e.actor_id) filter (where e.event_key = 'school_plc_brief_generated')::integer,
    count(*) filter (where e.event_key = 'plc_handout_viewed')::integer,
    count(distinct e.actor_id) filter (where e.event_key = 'plc_handout_viewed')::integer
  from public.reflection_intelligence_events e
  where e.occurred_at >= target_start::timestamptz
    and e.occurred_at < (target_end + 1)::timestamptz
    and target_end >= target_start
    and private.has_role('platform_admin'::public.app_role, null)
$$;

revoke all on function public.platform_reflection_intelligence_usage(date, date)
  from public, anon, authenticated, service_role;
grant execute on function public.platform_reflection_intelligence_usage(date, date)
  to authenticated;

notify pgrst, 'reload schema';
