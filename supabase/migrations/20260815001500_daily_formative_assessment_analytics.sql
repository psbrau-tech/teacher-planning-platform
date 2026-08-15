-- School-level daily formative-assessment analytics source.
--
-- The source is limited to immutable, explicitly submitted lesson-plan records. It returns only
-- anonymous teacher references plus the ten daily Week-at-a-Glance CFU/evidence fields needed for
-- local deterministic classification. It does not return teacher identity, reflection content,
-- student data, or any teacher-quality/performance score.

create or replace function public.school_daily_assessment_source(
  target_start date,
  target_end date,
  target_school_id uuid default null
)
returns table (
  source_ref integer,
  anonymous_teacher_ref integer,
  week_start date,
  daily_assessment_data jsonb
)
language sql
stable
security definer
set search_path = ''
as $$
  with actor_school as (
    select p.school_id
    from public.profiles p
    where p.id = (select auth.uid())
      and p.is_active
    limit 1
  ), effective_school as (
    select coalesce(target_school_id, actor_school.school_id) as school_id
    from actor_school
  ), authorized as (
    select effective_school.school_id
    from effective_school
    where (select auth.uid()) is not null
      and target_end >= target_start
      and private.can_report_school(effective_school.school_id)
  ), latest as (
    select distinct on (wps.teaching_assignment_id, wps.week_start)
      wps.teacher_id,
      wps.teaching_assignment_id,
      wps.week_start,
      wps.source_data,
      wps.revision,
      wps.submitted_at
    from public.weekly_plan_submissions wps
    join authorized a on a.school_id = wps.school_id
    where wps.submission_kind = 'lesson_plan'
      and wps.week_start between target_start and target_end
    order by
      wps.teaching_assignment_id,
      wps.week_start,
      wps.revision desc,
      wps.submitted_at desc
  ), ranked as (
    select
      row_number() over (
        order by latest.week_start, latest.teaching_assignment_id
      )::integer as source_ref,
      dense_rank() over (order by latest.teacher_id)::integer as anonymous_teacher_ref,
      latest.week_start,
      latest.source_data
    from latest
  )
  select
    ranked.source_ref,
    ranked.anonymous_teacher_ref,
    ranked.week_start,
    jsonb_build_object(
      'cfu_mon', ranked.source_data ->> 'cfu_mon',
      'cfu_tue', ranked.source_data ->> 'cfu_tue',
      'cfu_wed', ranked.source_data ->> 'cfu_wed',
      'cfu_thu', ranked.source_data ->> 'cfu_thu',
      'cfu_fri', ranked.source_data ->> 'cfu_fri',
      'esl_mon', ranked.source_data ->> 'esl_mon',
      'esl_tue', ranked.source_data ->> 'esl_tue',
      'esl_wed', ranked.source_data ->> 'esl_wed',
      'esl_thu', ranked.source_data ->> 'esl_thu',
      'esl_fri', ranked.source_data ->> 'esl_fri'
    ) as daily_assessment_data
  from ranked
  order by ranked.week_start, ranked.source_ref
$$;

revoke all on function public.school_daily_assessment_source(date, date, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.school_daily_assessment_source(date, date, uuid)
  to authenticated;

comment on function public.school_daily_assessment_source(date, date, uuid) is
  'Returns anonymous school-scoped daily CFU/evidence fields from the latest immutable submitted lesson-plan revision for deterministic formative-assessment analytics.';

notify pgrst, 'reload schema';
