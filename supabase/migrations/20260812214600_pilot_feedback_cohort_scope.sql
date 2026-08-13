-- Broaden the one-time feedback cohort to every governed Pilot teacher who
-- authenticated and configured at least one teaching assignment before the survey opens.
-- A teacher who was blocked before successfully saving a weekly plan is valuable feedback,
-- not someone to exclude from the survey.

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
        from public.teaching_assignments ta
        where ta.teacher_id = g.teacher_id
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

revoke all on function public.pilot_feedback_status()
  from public, anon, authenticated, service_role;
grant execute on function public.pilot_feedback_status() to authenticated;

notify pgrst, 'reload schema';
