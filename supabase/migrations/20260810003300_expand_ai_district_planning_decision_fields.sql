-- The district planning assistant now recommends every teacher-editable field that feeds the
-- Instructional Planning Framework and Week at a Glance. Preserve explicit teacher
-- accept/edit/reject evidence before any of that generated text is added to the working plan.

alter table public.ai_suggestion_decisions
  drop constraint if exists ai_suggestion_decisions_field;

alter table public.ai_suggestion_decisions
  add constraint ai_suggestion_decisions_field check (
    field_key in (
      'unit_topic',
      'learning_targets',
      'know',
      'understand',
      'do_statement',
      'activities',
      'assessments',
      'resources',
      'literacy_standards',
      'act_preparation',
      'monday',
      'tuesday',
      'wednesday',
      'thursday',
      'friday',
      'weekly_reflection',
      'plds',
      'misconceptions',
      'formative',
      'summative',
      'performance_task',
      'clt_mon', 'clt_tue', 'clt_wed', 'clt_thu', 'clt_fri',
      'rrt_mon', 'rrt_tue', 'rrt_wed', 'rrt_thu', 'rrt_fri',
      'cfu_mon', 'cfu_tue', 'cfu_wed', 'cfu_thu', 'cfu_fri',
      'ri_mon', 'ri_tue', 'ri_wed', 'ri_thu', 'ri_fri',
      'sic_mon', 'sic_tue', 'sic_wed', 'sic_thu', 'sic_fri',
      'esl_mon', 'esl_tue', 'esl_wed', 'esl_thu', 'esl_fri'
    )
  );

create or replace function public.record_ai_suggestion_decision(
  target_event_id uuid,
  target_field_key text,
  target_decision text
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
  target_assignment_id uuid;
  decision_count integer;
  accepted_or_edited_count integer;
begin
  if actor_id is null
     or not private.has_role('teacher'::public.app_role, null) then
    raise exception 'teacher role is required';
  end if;

  if target_field_key not in (
    'unit_topic',
    'learning_targets',
    'know',
    'understand',
    'do_statement',
    'activities',
    'assessments',
    'resources',
    'literacy_standards',
    'act_preparation',
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'weekly_reflection',
    'plds',
    'misconceptions',
    'formative',
    'summative',
    'performance_task',
    'clt_mon', 'clt_tue', 'clt_wed', 'clt_thu', 'clt_fri',
    'rrt_mon', 'rrt_tue', 'rrt_wed', 'rrt_thu', 'rrt_fri',
    'cfu_mon', 'cfu_tue', 'cfu_wed', 'cfu_thu', 'cfu_fri',
    'ri_mon', 'ri_tue', 'ri_wed', 'ri_thu', 'ri_fri',
    'sic_mon', 'sic_tue', 'sic_wed', 'sic_thu', 'sic_fri',
    'esl_mon', 'esl_tue', 'esl_wed', 'esl_thu', 'esl_fri'
  ) then
    raise exception 'unsupported AI suggestion field';
  end if;

  if target_decision not in ('accepted', 'edited', 'rejected') then
    raise exception 'unsupported AI suggestion decision';
  end if;

  select aue.teaching_assignment_id
    into target_assignment_id
  from public.ai_usage_events aue
  where aue.id = target_event_id
    and aue.teacher_id = actor_id
    and aue.succeeded = true;

  if target_assignment_id is null then
    raise exception 'AI usage event is unavailable for teacher decision';
  end if;

  insert into public.ai_suggestion_decisions (
    ai_usage_event_id,
    teacher_id,
    teaching_assignment_id,
    field_key,
    decision
  ) values (
    target_event_id,
    actor_id,
    target_assignment_id,
    target_field_key,
    target_decision
  )
  on conflict (ai_usage_event_id, field_key)
  do update set
    decision = excluded.decision,
    decided_at = now();

  select count(*),
         count(*) filter (where decision in ('accepted', 'edited'))
    into decision_count, accepted_or_edited_count
  from public.ai_suggestion_decisions
  where ai_usage_event_id = target_event_id;

  update public.ai_usage_events
  set accepted_by_teacher = case
    when accepted_or_edited_count > 0 then true
    when decision_count > 0 then false
    else null
  end
  where id = target_event_id
    and teacher_id = actor_id;

  insert into public.audit_events (
    school_id,
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data,
    reason
  )
  select
    aue.school_id,
    actor_id,
    'ai_usage_event',
    target_event_id,
    'record_ai_suggestion_decision',
    jsonb_build_object(
      'field_key', target_field_key,
      'decision', target_decision
    ),
    'Teacher reviewed AI planning suggestion'
  from public.ai_usage_events aue
  where aue.id = target_event_id;

  return target_decision;
end;
$$;

revoke all on function public.record_ai_suggestion_decision(uuid, text, text)
  from public, anon, authenticated, service_role;
grant execute on function public.record_ai_suggestion_decision(uuid, text, text)
  to authenticated;

notify pgrst, 'reload schema';
