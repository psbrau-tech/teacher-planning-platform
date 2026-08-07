-- Gate E: tighten course-mapping authority and make weekly standards selection atomic.

-- Course mapping is a governance decision. Teachers may read the mapping for assignments
-- they can access, but only a platform administrator may create/change/remove it.
drop policy if exists assignment_standard_courses_owner_write
  on public.assignment_standard_courses;

create policy assignment_standard_courses_platform_admin_write
on public.assignment_standard_courses
for all to authenticated
using (private.has_role('platform_admin'::public.app_role, null))
with check (
  private.has_role('platform_admin'::public.app_role, null)
  and mapped_by = (select auth.uid())
  and exists (
    select 1
    from public.standard_courses sc
    where sc.id = assignment_standard_courses.course_id
      and sc.source_id = assignment_standard_courses.source_id
      and sc.is_pilot_allowed
  )
);

create or replace function public.set_standard_course_pilot_allowed(
  target_course_id uuid,
  allowed boolean
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
  affected integer;
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  update public.standard_courses
  set is_pilot_allowed = allowed,
      updated_at = now()
  where id = target_course_id;
  get diagnostics affected = row_count;

  if affected <> 1 then
    raise exception 'standards course not found';
  end if;

  insert into public.audit_events (
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data,
    reason
  ) values (
    actor_id,
    'standard_course',
    target_course_id,
    'set_standard_course_pilot_allowed',
    jsonb_build_object('is_pilot_allowed', allowed),
    'Platform owner changed pilot standards-course availability'
  );

  return allowed;
end;
$$;

revoke all on function public.set_standard_course_pilot_allowed(uuid, boolean)
  from public, anon, authenticated, service_role;
grant execute on function public.set_standard_course_pilot_allowed(uuid, boolean)
  to authenticated;

create or replace function public.replace_weekly_standard_selections(
  target_assignment_id uuid,
  target_week_start date,
  target_entry_ids uuid[]
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
  mapped_course_id uuid;
  supplied_count integer;
  valid_count integer;
  inserted_count integer;
begin
  if actor_id is null then
    raise exception 'authenticated teacher is required';
  end if;

  if not private.has_role('teacher'::public.app_role, null) then
    raise exception 'teacher role is required';
  end if;

  if not private.can_access_assignment(target_assignment_id) then
    raise exception 'teaching assignment access denied';
  end if;

  if target_entry_ids is null then
    target_entry_ids := '{}'::uuid[];
  end if;

  select count(distinct entry_id)
    into supplied_count
  from unnest(target_entry_ids) as selected(entry_id);

  if supplied_count > 20 then
    raise exception 'no more than 20 standards may be selected for one week';
  end if;

  select asc_map.course_id
    into mapped_course_id
  from public.assignment_standard_courses asc_map
  where asc_map.teaching_assignment_id = target_assignment_id;

  if mapped_course_id is null then
    raise exception 'teaching assignment has no approved standards-course mapping';
  end if;

  select count(distinct se.id)
    into valid_count
  from public.standard_entries se
  join public.standard_snapshots ss on ss.id = se.snapshot_id
  where se.id = any(target_entry_ids)
    and se.course_id = mapped_course_id
    and ss.status = 'approved';

  if valid_count <> supplied_count then
    raise exception 'one or more selected standards are not approved for this assignment';
  end if;

  delete from public.weekly_standard_selections
  where teaching_assignment_id = target_assignment_id
    and week_start = target_week_start;

  insert into public.weekly_standard_selections (
    teaching_assignment_id,
    week_start,
    standard_entry_id,
    selected_by
  )
  select
    target_assignment_id,
    target_week_start,
    selected.entry_id,
    actor_id
  from (
    select distinct entry_id
    from unnest(target_entry_ids) as entries(entry_id)
  ) as selected;

  get diagnostics inserted_count = row_count;

  insert into public.audit_events (
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data,
    reason
  ) values (
    actor_id,
    'teaching_assignment',
    target_assignment_id,
    'replace_weekly_standard_selections',
    jsonb_build_object(
      'week_start', target_week_start,
      'selection_count', inserted_count,
      'standard_entry_ids', target_entry_ids
    ),
    'Teacher updated weekly authoritative standards selection'
  );

  return inserted_count;
end;
$$;

revoke all on function public.replace_weekly_standard_selections(uuid, date, uuid[])
  from public, anon, authenticated, service_role;
grant execute on function public.replace_weekly_standard_selections(uuid, date, uuid[])
  to authenticated;

notify pgrst, 'reload schema';
