-- A teacher-facing "Edit current curriculum" operation creates a new immutable
-- curriculum snapshot first, then atomically moves every active class owned by
-- that teacher from the prior snapshot to the revised snapshot. Historical
-- inactive classes, scheduled lessons, weekly plans, and submitted packets keep
-- their original references.

create or replace function public.replace_teacher_curriculum_version(
  prior_curriculum_id uuid,
  revised_curriculum_id uuid
)
returns integer
language plpgsql
security invoker
set search_path = ''
as $$
declare
  affected_count integer := 0;
  target_school_id uuid;
begin
  if (select auth.uid()) is null then
    raise exception 'authentication required';
  end if;

  select c.school_id into target_school_id
  from public.curricula c
  where c.id = prior_curriculum_id
    and c.created_by = (select auth.uid())
    and c.is_active;

  if target_school_id is null then
    raise exception 'active teacher-owned curriculum not found';
  end if;

  if not exists (
    select 1
    from public.curricula c
    where c.id = revised_curriculum_id
      and c.created_by = (select auth.uid())
      and c.school_id = target_school_id
      and c.is_active
  ) then
    raise exception 'revised teacher-owned curriculum not found';
  end if;

  update public.teaching_assignments
  set curriculum_id = revised_curriculum_id
  where teacher_id = (select auth.uid())
    and curriculum_id = prior_curriculum_id
    and is_active;

  get diagnostics affected_count = row_count;

  update public.curricula
  set is_active = false
  where id = prior_curriculum_id
    and created_by = (select auth.uid());

  insert into public.audit_events (
    school_id,
    actor_id,
    entity_type,
    entity_id,
    action,
    before_data,
    after_data,
    reason
  ) values (
    target_school_id,
    (select auth.uid()),
    'curriculum',
    revised_curriculum_id,
    'teacher_curriculum_revision_activated',
    jsonb_build_object('curriculum_id', prior_curriculum_id),
    jsonb_build_object(
      'curriculum_id', revised_curriculum_id,
      'active_classes_updated', affected_count
    ),
    'Teacher saved an in-year curriculum and pacing revision'
  );

  return affected_count;
end;
$$;

revoke all on function public.replace_teacher_curriculum_version(uuid, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.replace_teacher_curriculum_version(uuid, uuid)
  to authenticated;

comment on function public.replace_teacher_curriculum_version(uuid, uuid) is
  'Atomically moves the authenticated teacher active classes from one owned curriculum snapshot to a revised owned snapshot while preserving historical references.';
