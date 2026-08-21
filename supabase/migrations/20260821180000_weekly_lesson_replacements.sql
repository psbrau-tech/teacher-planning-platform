-- Teacher-controlled weekly pacing replacements. Curriculum source rows remain immutable;
-- manual classes live only in the assignment/week schedule and retain the displaced lesson.

alter table public.scheduled_lessons
  alter column lesson_id drop not null;

alter table public.scheduled_lessons
  add column if not exists source_type text not null default 'curriculum',
  add column if not exists manual_unit_title text,
  add column if not exists manual_lesson_title text,
  add column if not exists manual_learning_targets text[] not null default '{}',
  add column if not exists manual_assessment text,
  add column if not exists replaced_lesson_id uuid references public.lessons(id),
  add column if not exists replacement_disposition text;

alter table public.scheduled_lessons
  drop constraint if exists scheduled_lessons_source_type_check,
  add constraint scheduled_lessons_source_type_check
    check (source_type in ('curriculum', 'manual')),
  drop constraint if exists scheduled_lessons_replacement_disposition_check,
  add constraint scheduled_lessons_replacement_disposition_check
    check (replacement_disposition is null or replacement_disposition in ('skip', 'postpone')),
  drop constraint if exists scheduled_lessons_source_content_check,
  add constraint scheduled_lessons_source_content_check check (
    (
      source_type = 'curriculum'
      and lesson_id is not null
      and manual_unit_title is null
      and manual_lesson_title is null
      and replaced_lesson_id is null
      and replacement_disposition is null
    )
    or
    (
      source_type = 'manual'
      and lesson_id is null
      and nullif(btrim(manual_unit_title), '') is not null
      and nullif(btrim(manual_lesson_title), '') is not null
      and replaced_lesson_id is not null
      and replacement_disposition in ('skip', 'postpone')
    )
  ),
  drop constraint if exists scheduled_lessons_manual_content_limits_check,
  add constraint scheduled_lessons_manual_content_limits_check check (
    char_length(coalesce(manual_unit_title, '')) <= 300
    and char_length(coalesce(manual_lesson_title, '')) <= 1000
    and cardinality(manual_learning_targets) <= 20
    and char_length(coalesce(manual_assessment, '')) <= 2000
  );

comment on column public.scheduled_lessons.source_type is
  'Curriculum rows reference governed pacing lessons; manual rows are teacher-authored assignment/week replacements.';
comment on column public.scheduled_lessons.replaced_lesson_id is
  'Original curriculum lesson displaced by a teacher-authored manual class.';
comment on column public.scheduled_lessons.replacement_disposition is
  'Whether the displaced curriculum lesson leaves the class queue or is postponed.';

create or replace function public.replace_weekly_scheduled_lesson(
  target_scheduled_lesson_id uuid,
  replacement_kind text,
  target_manual_unit_title text default null,
  target_manual_lesson_title text default null,
  target_manual_learning_targets text[] default '{}',
  target_manual_assessment text default null,
  original_disposition text default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  target public.scheduled_lessons%rowtype;
  shifted public.scheduled_lessons%rowtype;
  previous_date date;
  final_date date;
  final_minutes integer;
  week_start date;
  week_max_sequence integer;
  next_lesson_id uuid;
  next_sequence integer;
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated teacher is required' using errcode = '42501';
  end if;

  select sl.* into target
  from public.scheduled_lessons sl
  join public.teaching_assignments ta on ta.id = sl.teaching_assignment_id
  where sl.id = target_scheduled_lesson_id
    and ta.teacher_id = (select auth.uid())
  for update of sl;

  if target.id is null then
    raise exception 'Scheduled curriculum lesson was not found' using errcode = 'P0002';
  end if;
  if target.source_type <> 'curriculum' or target.lesson_id is null then
    raise exception 'Only a scheduled curriculum lesson can be replaced' using errcode = '22023';
  end if;

  week_start := target.school_date - (extract(isodow from target.school_date)::integer - 1);
  if exists (
    select 1 from public.friday_validation_snapshots fvs
    where fvs.teaching_assignment_id = target.teaching_assignment_id
      and fvs.week_start = week_start
  ) then
    raise exception 'Reopen is unavailable after Friday validation has been finalized'
      using errcode = '23514';
  end if;

  if replacement_kind = 'manual' then
    if nullif(btrim(target_manual_unit_title), '') is null
       or nullif(btrim(target_manual_lesson_title), '') is null
       or original_disposition not in ('skip', 'postpone') then
      raise exception 'Manual replacement details and original-lesson decision are required'
        using errcode = '22023';
    end if;
    if char_length(btrim(target_manual_unit_title)) > 300
       or char_length(btrim(target_manual_lesson_title)) > 1000
       or cardinality(coalesce(target_manual_learning_targets, '{}')) > 20
       or exists (
         select 1 from unnest(coalesce(target_manual_learning_targets, '{}')) item
         where char_length(btrim(item)) > 1000
       )
       or char_length(coalesce(target_manual_assessment, '')) > 2000 then
      raise exception 'Manual replacement content exceeds the permitted limits'
        using errcode = '22023';
    end if;
    update public.scheduled_lessons
    set lesson_id = null,
        source_type = 'manual',
        manual_unit_title = btrim(target_manual_unit_title),
        manual_lesson_title = btrim(target_manual_lesson_title),
        manual_learning_targets = coalesce(target_manual_learning_targets, '{}'),
        manual_assessment = nullif(btrim(target_manual_assessment), ''),
        replaced_lesson_id = target.lesson_id,
        replacement_disposition = original_disposition,
        is_teacher_override = true
    where id = target.id;
    return;
  end if;

  if replacement_kind <> 'next' then
    raise exception 'Replacement kind must be next or manual' using errcode = '22023';
  end if;

  select max(sl.sequence_position)::integer, max(sl.school_date)
    into week_max_sequence, final_date
  from public.scheduled_lessons sl
  where sl.teaching_assignment_id = target.teaching_assignment_id
    and sl.school_date between week_start and week_start + 4;

  select sl.planned_minutes into final_minutes
  from public.scheduled_lessons sl
  where sl.teaching_assignment_id = target.teaching_assignment_id
    and sl.school_date = final_date
  order by sl.segment_index desc
  limit 1;

  previous_date := target.school_date;
  delete from public.scheduled_lessons where id = target.id;
  for shifted in
    select sl.* from public.scheduled_lessons sl
    where sl.teaching_assignment_id = target.teaching_assignment_id
      and sl.school_date > target.school_date
      and sl.school_date <= week_start + 4
    order by sl.school_date, sl.sequence_position, sl.segment_index
    for update
  loop
    update public.scheduled_lessons
      set school_date = previous_date, is_teacher_override = true
      where id = shifted.id;
    previous_date := shifted.school_date;
  end loop;

  with ordered_lessons as (
    select l.id, row_number() over (order by cu.sequence, l.sequence)::integer as global_sequence
    from public.teaching_assignments ta
    join public.curriculum_units cu on cu.curriculum_id = ta.curriculum_id
    join public.lessons l on l.unit_id = cu.id
    where ta.id = target.teaching_assignment_id
  )
  select ol.id, ol.global_sequence into next_lesson_id, next_sequence
  from ordered_lessons ol
  where ol.global_sequence > coalesce(week_max_sequence, 0)
  order by ol.global_sequence
  limit 1;

  if next_lesson_id is not null and final_date is not null then
    insert into public.scheduled_lessons (
      teaching_assignment_id, lesson_id, school_date, segment_index,
      planned_minutes, sequence_position, is_teacher_override, source_type
    ) values (
      target.teaching_assignment_id, next_lesson_id, final_date, 1,
      coalesce(final_minutes, target.planned_minutes), next_sequence, true, 'curriculum'
    );
  end if;
  update public.scheduled_lessons
    set is_teacher_override = true
    where teaching_assignment_id = target.teaching_assignment_id
      and school_date between week_start and week_start + 4;
end;
$$;

revoke all on function public.replace_weekly_scheduled_lesson(
  uuid, text, text, text, text[], text, text
) from public, anon, authenticated, service_role;
grant execute on function public.replace_weekly_scheduled_lesson(
  uuid, text, text, text, text[], text, text
) to authenticated;

notify pgrst, 'reload schema';
