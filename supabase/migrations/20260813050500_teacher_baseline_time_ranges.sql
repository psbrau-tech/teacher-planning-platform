-- Refine the pre-TPP planning-time baseline before the survey is deployed.
-- The baseline table is created by the immediately preceding migration; no responses exist yet.

alter table public.teacher_baseline_responses
  drop constraint teacher_baseline_responses_planning_time_before_check;

alter table public.teacher_baseline_responses
  add constraint teacher_baseline_responses_planning_time_before_check check (
    planning_time_before in (
      'under_30',
      '30_60',
      '61_90',
      '91_120',
      '121_180',
      'over_180',
      'not_sure'
    )
  );

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

  if target_planning_time_before not in (
    'under_30',
    '30_60',
    '61_90',
    '91_120',
    '121_180',
    'over_180',
    'not_sure'
  ) then
    raise exception 'Unsupported planning-time response' using errcode = '22023';
  end if;
  if target_plan_usefulness_before < 1 or target_plan_usefulness_before > 5 then
    raise exception 'Plan usefulness must be between 1 and 5' using errcode = '22023';
  end if;
  if target_submission_burden_before < 1 or target_submission_burden_before > 5 then
    raise exception 'Submission burden must be between 1 and 5' using errcode = '22023';
  end if;
  if target_reflection_review_frequency_before not in (
    'never', 'rarely', 'sometimes', 'often', 'very_often'
  ) or target_plc_use_frequency_before not in (
    'never', 'rarely', 'sometimes', 'often', 'very_often'
  ) then
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

notify pgrst, 'reload schema';
