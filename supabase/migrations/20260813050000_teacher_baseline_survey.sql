-- One-time teacher baseline used to measure planning burden and professional value before TPP.
-- Adult educator professional/product feedback only; never store student-specific information.

create table public.teacher_baseline_responses (
  id uuid primary key default gen_random_uuid(),
  survey_key text not null default 'teacher-baseline-2026-08',
  teacher_id uuid not null references public.profiles(id) on delete cascade,
  school_id uuid not null references public.schools(id) on delete cascade,
  planning_time_before text not null check (
    planning_time_before in ('under_30', '30_60', '61_120', '121_180', 'over_180', 'not_sure')
  ),
  plan_usefulness_before smallint not null check (plan_usefulness_before between 1 and 5),
  submission_burden_before smallint not null check (submission_burden_before between 1 and 5),
  reflection_review_frequency_before text not null check (
    reflection_review_frequency_before in ('never', 'rarely', 'sometimes', 'often', 'very_often')
  ),
  plc_use_frequency_before text not null check (
    plc_use_frequency_before in ('never', 'rarely', 'sometimes', 'often', 'very_often')
  ),
  biggest_burden_before text not null default '' check (
    char_length(biggest_burden_before) <= 1000
  ),
  submitted_at timestamptz not null default now(),
  unique (teacher_id, survey_key)
);

alter table public.teacher_baseline_responses enable row level security;
revoke all on table public.teacher_baseline_responses from public, anon, authenticated;

comment on table public.teacher_baseline_responses is
  'One-time adult educator pre-TPP planning baseline. No student-specific information permitted.';

create or replace function public.teacher_baseline_status()
returns table (
  survey_key text,
  eligible boolean,
  available boolean,
  submitted boolean,
  submitted_at timestamptz
)
language sql
stable
security definer
set search_path = ''
as $$
with governed as (
  select p.id as teacher_id
  from public.profiles p
  where p.id = (select auth.uid())
    and p.is_active
    and exists (
      select 1
      from public.profile_roles pr
      where pr.profile_id = p.id
        and pr.school_id = p.school_id
        and pr.role = 'teacher'::public.app_role
    )
), existing as (
  select r.teacher_id, r.submitted_at
  from public.teacher_baseline_responses r
  where r.teacher_id = (select auth.uid())
    and r.survey_key = 'teacher-baseline-2026-08'
)
select
  'teacher-baseline-2026-08'::text,
  (g.teacher_id is not null),
  (g.teacher_id is not null and e.submitted_at is null),
  (e.submitted_at is not null),
  e.submitted_at
from governed g
left join existing e on e.teacher_id = g.teacher_id;
$$;

revoke all on function public.teacher_baseline_status()
  from public, anon, authenticated, service_role;
grant execute on function public.teacher_baseline_status() to authenticated;

create or replace function public.submit_teacher_baseline(
  target_planning_time_before text,
  target_plan_usefulness_before smallint,
  target_submission_burden_before smallint,
  target_reflection_review_frequency_before text,
  target_plc_use_frequency_before text,
  target_biggest_burden_before text
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

  select * into status_record from public.teacher_baseline_status();
  if not found or status_record.available is not true then
    raise exception 'Teacher baseline is not currently available' using errcode = '42501';
  end if;

  if target_planning_time_before not in ('under_30', '30_60', '61_120', '121_180', 'over_180', 'not_sure') then
    raise exception 'Unsupported planning-time response' using errcode = '22023';
  end if;
  if target_plan_usefulness_before < 1 or target_plan_usefulness_before > 5 then
    raise exception 'Plan usefulness must be between 1 and 5' using errcode = '22023';
  end if;
  if target_submission_burden_before < 1 or target_submission_burden_before > 5 then
    raise exception 'Submission burden must be between 1 and 5' using errcode = '22023';
  end if;
  if target_reflection_review_frequency_before not in ('never', 'rarely', 'sometimes', 'often', 'very_often')
     or target_plc_use_frequency_before not in ('never', 'rarely', 'sometimes', 'often', 'very_often') then
    raise exception 'Unsupported frequency response' using errcode = '22023';
  end if;
  if char_length(coalesce(target_biggest_burden_before, '')) > 1000 then
    raise exception 'Optional baseline comment exceeds the character limit' using errcode = '22023';
  end if;

  select p.id, p.school_id into profile_record
  from public.profiles p
  where p.id = (select auth.uid()) and p.is_active;

  if not found then
    raise exception 'Active governed profile is required' using errcode = '42501';
  end if;

  insert into public.teacher_baseline_responses (
    survey_key,
    teacher_id,
    school_id,
    planning_time_before,
    plan_usefulness_before,
    submission_burden_before,
    reflection_review_frequency_before,
    plc_use_frequency_before,
    biggest_burden_before
  ) values (
    status_record.survey_key,
    profile_record.id,
    profile_record.school_id,
    target_planning_time_before,
    target_plan_usefulness_before,
    target_submission_burden_before,
    target_reflection_review_frequency_before,
    target_plc_use_frequency_before,
    btrim(coalesce(target_biggest_burden_before, ''))
  )
  returning teacher_baseline_responses.id, teacher_baseline_responses.submitted_at
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
    'teacher_baseline_response',
    inserted_record.id,
    'submit_teacher_baseline',
    jsonb_build_object(
      'survey_key', status_record.survey_key,
      'planning_time_before', target_planning_time_before,
      'plan_usefulness_before', target_plan_usefulness_before,
      'submission_burden_before', target_submission_burden_before,
      'submitted_at', inserted_record.submitted_at
    )
  );

  return query select inserted_record.id::uuid, inserted_record.submitted_at::timestamptz;
end;
$$;

revoke all on function public.submit_teacher_baseline(text, smallint, smallint, text, text, text)
  from public, anon, authenticated, service_role;
grant execute on function public.submit_teacher_baseline(text, smallint, smallint, text, text, text)
  to authenticated;

-- Platform Owner results intentionally omit teacher identity. Baseline reporting is for product
-- and school-level impact measurement, not individual teacher evaluation.
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
    r.planning_time_before,
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
