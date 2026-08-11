-- Gate E: field-level teacher decisions prove AI remains draft-only.
-- Do not persist the AI suggestion text here; saved teacher content remains authoritative.

create table public.ai_suggestion_decisions (
  id uuid primary key default gen_random_uuid(),
  ai_usage_event_id uuid not null references public.ai_usage_events(id) on delete cascade,
  teacher_id uuid not null references public.profiles(id) on delete cascade,
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  field_key text not null,
  decision text not null,
  decided_at timestamptz not null default now(),
  constraint ai_suggestion_decisions_field check (
    field_key in (
      'learning_targets',
      'know',
      'understand',
      'do_statement',
      'activities',
      'assessments',
      'resources',
      'literacy_standards',
      'act_preparation',
      'weekly_reflection'
    )
  ),
  constraint ai_suggestion_decisions_decision check (
    decision in ('accepted', 'edited', 'rejected')
  ),
  unique (ai_usage_event_id, field_key)
);

alter table public.ai_suggestion_decisions enable row level security;

revoke all on table public.ai_suggestion_decisions
  from public, anon, authenticated, service_role;
grant select on table public.ai_suggestion_decisions to authenticated;
grant select, insert, update, delete on table public.ai_suggestion_decisions to service_role;

create policy ai_suggestion_decisions_teacher_read
on public.ai_suggestion_decisions
for select to authenticated
using (
  teacher_id = (select auth.uid())
  or private.has_role('platform_admin'::public.app_role, null)
  or private.has_role('school_admin'::public.app_role, null)
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
    'learning_targets',
    'know',
    'understand',
    'do_statement',
    'activities',
    'assessments',
    'resources',
    'literacy_standards',
    'act_preparation',
    'weekly_reflection'
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
