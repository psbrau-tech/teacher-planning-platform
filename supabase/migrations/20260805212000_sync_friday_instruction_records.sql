create or replace function private.sync_friday_instruction_records()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if jsonb_typeof(new.result_data -> 'validated') <> 'array' then
    raise exception 'Friday validation result_data.validated must be an array';
  end if;

  insert into public.instruction_records (
    scheduled_lesson_id,
    status,
    actual_minutes,
    carry_forward_action,
    reason,
    teacher_notes,
    validated_by,
    validated_at
  )
  select
    (lesson ->> 'scheduled_lesson_id')::uuid,
    case lesson ->> 'status'
      when 'completed' then 'completed'::public.lesson_outcome_status
      when 'modified' then 'modified'::public.lesson_outcome_status
      when 'missed' then 'missed'::public.lesson_outcome_status
      when 'skipped' then 'not_needed'::public.lesson_outcome_status
      else 'planned'::public.lesson_outcome_status
    end,
    null,
    case
      when coalesce((lesson ->> 'carry_forward')::boolean, false)
        then 'carry_forward'::public.carry_forward_action
      when lesson ->> 'status' = 'skipped'
        then 'skip'::public.carry_forward_action
      else 'none'::public.carry_forward_action
    end,
    nullif(lesson ->> 'reason', ''),
    nullif(lesson ->> 'teacher_note', ''),
    new.validated_by,
    new.validated_at
  from jsonb_array_elements(new.result_data -> 'validated') as lesson
  on conflict (scheduled_lesson_id) do update set
    status = excluded.status,
    actual_minutes = excluded.actual_minutes,
    carry_forward_action = excluded.carry_forward_action,
    reason = excluded.reason,
    teacher_notes = excluded.teacher_notes,
    validated_by = excluded.validated_by,
    validated_at = excluded.validated_at;

  delete from public.instruction_records records
  using public.scheduled_lessons scheduled
  where records.scheduled_lesson_id = scheduled.id
    and scheduled.teaching_assignment_id = new.teaching_assignment_id
    and scheduled.school_date between new.week_start and (new.week_start + 6)
    and not exists (
      select 1
      from jsonb_array_elements(new.result_data -> 'validated') as lesson
      where (lesson ->> 'scheduled_lesson_id')::uuid = scheduled.id
    );

  return new;
end;
$$;

revoke all on function private.sync_friday_instruction_records()
  from public, anon, authenticated;

drop trigger if exists sync_friday_instruction_records_trigger
  on public.friday_validation_snapshots;
create trigger sync_friday_instruction_records_trigger
after insert or update of result_data, validated_by
on public.friday_validation_snapshots
for each row execute function private.sync_friday_instruction_records();

notify pgrst, 'reload schema';
