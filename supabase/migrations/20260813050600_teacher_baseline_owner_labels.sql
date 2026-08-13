-- Keep baseline response storage normalized while returning human-readable planning-time labels
-- to the Platform Owner reporting surface. Teacher identity remains intentionally omitted.

create or replace function public.platform_teacher_baseline_results()
returns table (
  id uuid,
  survey_key text,
  school_id uuid,
  school_name text,
  planning_time_before text,
  plan_usefulness_before smallint,
  submission_burden_before smallint,
  reflection_review_frequency_before text,
  plc_use_frequency_before text,
  biggest_burden_before text,
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
    case r.planning_time_before
      when 'under_30' then 'Less than 30 minutes'
      when '30_60' then '30–60 minutes'
      when '61_90' then '61–90 minutes'
      when '91_120' then '91–120 minutes'
      when '121_180' then '121–180 minutes'
      when 'over_180' then 'More than 3 hours'
      when 'not_sure' then 'Not sure'
      else r.planning_time_before
    end,
    r.plan_usefulness_before,
    r.submission_burden_before,
    r.reflection_review_frequency_before,
    r.plc_use_frequency_before,
    r.biggest_burden_before,
    r.submitted_at
  from public.teacher_baseline_responses r
  join public.schools s on s.id = r.school_id
  where private.has_role('platform_admin'::public.app_role, null)
  order by s.name, r.submitted_at;
$$;

revoke all on function public.platform_teacher_baseline_results()
  from public, anon, authenticated, service_role;
grant execute on function public.platform_teacher_baseline_results() to authenticated;

notify pgrst, 'reload schema';
