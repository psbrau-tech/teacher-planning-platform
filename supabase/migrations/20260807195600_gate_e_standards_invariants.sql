-- Gate E invariant hardening: prevent cross-source standards data and make
-- snapshot approval an explicit platform-owner action.

create or replace function private.enforce_standard_entry_source()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  snapshot_source_id uuid;
  course_source_id uuid;
begin
  select ss.source_id into snapshot_source_id
  from public.standard_snapshots ss
  where ss.id = new.snapshot_id;

  select sc.source_id into course_source_id
  from public.standard_courses sc
  where sc.id = new.course_id;

  if snapshot_source_id is null
     or course_source_id is null
     or snapshot_source_id <> course_source_id then
    raise exception 'standards entry snapshot and course must belong to the same source';
  end if;
  return new;
end;
$$;

drop trigger if exists standard_entry_source_trigger on public.standard_entries;
create trigger standard_entry_source_trigger
before insert or update of snapshot_id, course_id on public.standard_entries
for each row execute function private.enforce_standard_entry_source();

create or replace function private.enforce_approved_standard_snapshot_pointer()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  snapshot_source_id uuid;
  snapshot_status text;
begin
  if new.approved_snapshot_id is null then
    return new;
  end if;

  select ss.source_id, ss.status
    into snapshot_source_id, snapshot_status
  from public.standard_snapshots ss
  where ss.id = new.approved_snapshot_id;

  if snapshot_source_id is null
     or snapshot_source_id <> new.id
     or snapshot_status <> 'approved' then
    raise exception 'approved standards snapshot must be approved and belong to the source';
  end if;
  return new;
end;
$$;

drop trigger if exists approved_standard_snapshot_pointer_trigger
  on public.standard_sources;
create trigger approved_standard_snapshot_pointer_trigger
before insert or update of approved_snapshot_id on public.standard_sources
for each row execute function private.enforce_approved_standard_snapshot_pointer();

create or replace function public.approve_standard_snapshot(target_snapshot_id uuid)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_source_id uuid;
  target_status text;
  actor_id uuid := (select auth.uid());
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  select ss.source_id, ss.status
    into target_source_id, target_status
  from public.standard_snapshots ss
  where ss.id = target_snapshot_id
  for update;

  if target_source_id is null then
    raise exception 'standards snapshot not found';
  end if;

  if target_status <> 'pending' then
    raise exception 'only a pending standards snapshot can be approved';
  end if;

  update public.standard_snapshots
  set status = 'superseded'
  where source_id = target_source_id
    and status = 'approved';

  update public.standard_snapshots
  set status = 'approved',
      approved_by = actor_id,
      approved_at = now()
  where id = target_snapshot_id;

  update public.standard_sources
  set approved_snapshot_id = target_snapshot_id,
      updated_at = now()
  where id = target_source_id;

  insert into public.audit_events (
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data,
    reason
  ) values (
    actor_id,
    'standard_snapshot',
    target_snapshot_id,
    'approve_standard_snapshot',
    jsonb_build_object('source_id', target_source_id, 'status', 'approved'),
    'Platform owner approved authoritative standards snapshot'
  );

  return target_snapshot_id;
end;
$$;

revoke all on function public.approve_standard_snapshot(uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.approve_standard_snapshot(uuid)
  to authenticated;

notify pgrst, 'reload schema';
