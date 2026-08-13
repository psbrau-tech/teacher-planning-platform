-- One-time Pilot teacher feedback survey used to improve TPP before full-staff rollout.
-- Adult professional/product feedback only; no student-specific information is permitted.

create table public.pilot_feedback_responses (
  id uuid primary key default gen_random_uuid(),
  survey_key text not null default 'pilot-rollout-2026-08',
  teacher_id uuid not null references public.profiles(id) on delete cascade,
  school_id uuid not null references public.schools(id) on delete cascade,
  overall_usefulness smallint not null check (overall_usefulness between 1 and 5),
  planning_time_change text not null check (
    planning_time_change in ('much_less', 'somewhat_less', 'about_same', 'somewhat_more', 'much_more')
  ),
  most_useful text not null check (
    char_length(btrim(most_useful)) between 1 and 1500
  ),
  biggest_challenge text not null check (
    char_length(btrim(biggest_challenge)) between 1 and 1500
  ),
  dislike_or_simplify text not null default '' check (
    char_length(dislike_or_simplify) <= 1500
  ),
  recommended_improvement text not null check (
    char_length(btrim(recommended_improvement)) between 1 and 1500
  ),
  rollout_readiness text not null check (
    rollout_readiness in ('ready_now', 'ready_minor_fixes', 'needs_significant_fixes', 'not_ready')
  ),
  submitted_at timestamptz not null default now(),
  unique (teacher_id, survey_key)
);

alter table public.pilot_feedback_responses enable row level security;

revoke all on table public.pilot_feedback_responses from public, anon, authenticated;

comment on table public.pilot_feedback_responses is
  'One-time adult educator Pilot product feedback. Never store student-specific information here.';

-- Status is derived from governed account/activity data rather than a hard-coded staff list.
-- Preferred trigger: after the week of Aug 17 closeouts are complete and Aug 24 plans are saved.
-- Fallback: beginning Aug 24 so teachers who were blocked or frustrated are still heard.
create or replace function public.pilot_feedback_status()
returns table (
  survey_key text,
  eligible boolean,
  available boolean,
  submitted boolean,
  preferred_ready boolean,
  fallback_ready boolean,
  required_closeouts integer,
  completed_closeouts integer,
  required_next_week_plans integer,
  saved_next_week_plans integer,
  submitted_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
with governed as (
  select
    p.id as teacher_id,
    p.school_id,
    p.created_at,
    coalesce(s.timezone, 'America/Chicago') as timezone,
    ((now() at time zone coalesce(s.timezone, 'America/Chicago'))::date) as local_date
  from public.profiles p
  join public.schools s on s.id = p.school_id
  where p.id = (select auth.uid())
    and p.is_active
    and exists (
      select 1
      from public.profile_roles pr
      where pr.profile_id = p.id
        and pr.school_id = p.school_id
        and pr.role = 'teacher'::public.app_role
    )
), cohort as (
  select
    g.*,
    (
      g.created_at < timestamptz '2026-08-21 05:00:00+00'
      and exists (
        select 1
        from public.weekly_plan_snapshots w
        join public.teaching_assignments ta on ta.id = w.teaching_assignment_id
        where ta.teacher_id = g.teacher_id
          and w.created_at < timestamptz '2026-08-21 05:00:00+00'
      )
    ) as is_eligible
  from governed g
), closeout_assignments as (
  select ta.id, ta.teacher_id
  from public.teaching_assignments ta
  join cohort c on c.teacher_id = ta.teacher_id
  where ta.is_active
    and ta.curriculum_id is not null
    and ta.starts_on <= date '2026-08-21'
    and ta.ends_on >= date '2026-08-17'
), next_week_assignments as (
  select ta.id, ta.teacher_id
  from public.teaching_assignments ta
  join cohort c on c.teacher_id = ta.teacher_id
  where ta.is_active
    and ta.curriculum_id is not null
    and ta.starts_on <= date '2026-08-28'
    and ta.ends_on >= date '2026-08-24'
), counts as (
  select
    c.teacher_id,
    count(distinct ca.id)::integer as required_closeouts,
    count(distinct case when wps.id is not null then ca.id end)::integer as completed_closeouts,
    count(distinct na.id)::integer as required_next_week_plans,
    count(distinct case when w.id is not null then na.id end)::integer as saved_next_week_plans
  from cohort c
  left join closeout_assignments ca on ca.teacher_id = c.teacher_id
  left join public.weekly_plan_submissions wps
    on wps.teaching_assignment_id = ca.id
   and wps.week_start = date '2026-08-17'
   and wps.submission_kind = 'completed_packet'
  left join next_week_assignments na on na.teacher_id = c.teacher_id
  left join public.weekly_plan_snapshots w
    on w.teaching_assignment_id = na.id
   and w.week_start = date '2026-08-24'
  group by c.teacher_id
), existing as (
  select r.teacher_id, r.submitted_at
  from public.pilot_feedback_responses r
  where r.survey_key = 'pilot-rollout-2026-08'
    and r.teacher_id = (select auth.uid())
)
select
  'pilot-rollout-2026-08'::text as survey_key,
  coalesce(c.is_eligible, false) as eligible,
  (
    coalesce(c.is_eligible, false)
    and e.submitted_at is null
    and (
      (
        c.local_date >= date '2026-08-21'
        and coalesce(x.required_closeouts, 0) > 0
        and x.completed_closeouts >= x.required_closeouts
        and coalesce(x.required_next_week_plans, 0) > 0
        and x.saved_next_week_plans >= x.required_next_week_plans
      )
      or c.local_date >= date '2026-08-24'
    )
  ) as available,
  (e.submitted_at is not null) as submitted,
  (
    coalesce(c.local_date >= date '2026-08-21', false)
    and coalesce(x.required_closeouts, 0) > 0
    and x.completed_closeouts >= x.required_closeouts
    and coalesce(x.required_next_week_plans, 0) > 0
    and x.saved_next_week_plans >= x.required_next_week_plans
  ) as preferred_ready,
  coalesce(c.local_date >= date '2026-08-24', false) as fallback_ready,
  coalesce(x.required_closeouts, 0)::integer,
  coalesce(x.completed_closeouts, 0)::integer,
  coalesce(x.required_next_week_plans, 0)::integer,
  coalesce(x.saved_next_week_plans, 0)::integer,
  e.submitted_at
from cohort c
left join counts x on x.teacher_id = c.teacher_id
left join existing e on e.teacher_id = c.teacher_id;
$$;

revoke all on function public.pilot_feedback_status() from public, anon, authenticated, service_role;
grant execute on function public.pilot_feedback_status() to authenticated;

create or replace function public.submit_pilot_feedback(
  target_overall_usefulness smallint,
  target_planning_time_change text,
  target_most_useful text,
  target_biggest_challenge text,
  target_dislike_or_simplify text,
  target_recommended_improvement text,
  target_rollout_readiness text
)
returns table (
  id uuid,
  submitted_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  status_record record;
  profile_record record;
  inserted_record record;
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated teacher is required' using errcode = '42501';
  end if;

  select * into status_record from public.pilot_feedback_status();
  if not found or status_record.available is not true then
    raise exception 'Pilot feedback survey is not currently available' using errcode = '42501';
  end if;

  if target_overall_usefulness < 1 or target_overall_usefulness > 5 then
    raise exception 'Overall usefulness must be between 1 and 5' using errcode = '22023';
  end if;
  if target_planning_time_change not in ('much_less', 'somewhat_less', 'about_same', 'somewhat_more', 'much_more') then
    raise exception 'Unsupported planning time response' using errcode = '22023';
  end if;
  if target_rollout_readiness not in ('ready_now', 'ready_minor_fixes', 'needs_significant_fixes', 'not_ready') then
    raise exception 'Unsupported rollout readiness response' using errcode = '22023';
  end if;
  if char_length(btrim(coalesce(target_most_useful, ''))) not between 1 and 1500
     or char_length(btrim(coalesce(target_biggest_challenge, ''))) not between 1 and 1500
     or char_length(coalesce(target_dislike_or_simplify, '')) > 1500
     or char_length(btrim(coalesce(target_recommended_improvement, ''))) not between 1 and 1500 then
    raise exception 'Pilot feedback text must stay within the allowed character limits' using errcode = '22023';
  end if;

  select p.id, p.school_id into profile_record
  from public.profiles p
  where p.id = (select auth.uid()) and p.is_active;

  if not found then
    raise exception 'Active governed profile is required' using errcode = '42501';
  end if;

  insert into public.pilot_feedback_responses (
    survey_key,
    teacher_id,
    school_id,
    overall_usefulness,
    planning_time_change,
    most_useful,
    biggest_challenge,
    dislike_or_simplify,
    recommended_improvement,
    rollout_readiness
  ) values (
    status_record.survey_key,
    profile_record.id,
    profile_record.school_id,
    target_overall_usefulness,
    target_planning_time_change,
    btrim(target_most_useful),
    btrim(target_biggest_challenge),
    btrim(coalesce(target_dislike_or_simplify, '')),
    btrim(target_recommended_improvement),
    target_rollout_readiness
  )
  returning pilot_feedback_responses.id, pilot_feedback_responses.submitted_at
  into inserted_record;

  insert into public.audit_events (
    school_id,
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data
  ) values (
    profile_record.school_id,
    profile_record.id,
    'pilot_feedback_response',
    inserted_record.id,
    'submit_pilot_feedback',
    jsonb_build_object(
      'survey_key', status_record.survey_key,
      'rollout_readiness', target_rollout_readiness,
      'submitted_at', inserted_record.submitted_at
    )
  );

  return query select inserted_record.id::uuid, inserted_record.submitted_at::timestamptz;
end;
$$;

revoke all on function public.submit_pilot_feedback(smallint, text, text, text, text, text, text)
  from public, anon, authenticated, service_role;
grant execute on function public.submit_pilot_feedback(smallint, text, text, text, text, text, text)
  to authenticated;

create or replace function public.platform_pilot_feedback_results()
returns table (
  id uuid,
  survey_key text,
  school_id uuid,
  school_name text,
  teacher_id uuid,
  teacher_name text,
  overall_usefulness smallint,
  planning_time_change text,
  most_useful text,
  biggest_challenge text,
  dislike_or_simplify text,
  recommended_improvement text,
  rollout_readiness text,
  submitted_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    r.id,
    r.survey_key,
    r.school_id,
    s.name,
    r.teacher_id,
    p.display_name,
    r.overall_usefulness,
    r.planning_time_change,
    r.most_useful,
    r.biggest_challenge,
    r.dislike_or_simplify,
    r.recommended_improvement,
    r.rollout_readiness,
    r.submitted_at
  from public.pilot_feedback_responses r
  join public.schools s on s.id = r.school_id
  join public.profiles p on p.id = r.teacher_id
  where private.has_role('platform_admin'::public.app_role, null)
  order by r.submitted_at desc;
$$;

revoke all on function public.platform_pilot_feedback_results()
  from public, anon, authenticated, service_role;
grant execute on function public.platform_pilot_feedback_results() to authenticated;

notify pgrst, 'reload schema';
