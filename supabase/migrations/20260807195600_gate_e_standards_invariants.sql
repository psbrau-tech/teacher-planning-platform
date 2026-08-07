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
  target_source_key text;
  target_status text;
  target_course_count integer;
  target_entry_count integer;
  actor_id uuid := (select auth.uid());
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  select ss.source_id, src.source_key, ss.status
    into target_source_id, target_source_key, target_status
  from public.standard_snapshots ss
  join public.standard_sources src on src.id = ss.source_id
  where ss.id = target_snapshot_id
  for update of ss;

  if target_source_id is null then
    raise exception 'standards snapshot not found';
  end if;

  if target_status <> 'pending' then
    raise exception 'only a pending standards snapshot can be approved';
  end if;

  select count(distinct se.course_id), count(*)
    into target_course_count, target_entry_count
  from public.standard_entries se
  join public.standard_courses sc on sc.id = se.course_id
  where se.snapshot_id = target_snapshot_id
    and sc.source_id = target_source_id;

  if target_course_count = 0 or target_entry_count = 0 then
    raise exception 'standards snapshot has no validated parsed entries';
  end if;

  if target_source_key = 'alabama_ela_2021'
     and not exists (
       select 1
       from public.standard_entries se
       join public.standard_courses sc on sc.id = se.course_id
       where se.snapshot_id = target_snapshot_id
         and sc.source_id = target_source_id
         and sc.course_key = 'english_10'
     ) then
    raise exception 'English 10 standards are missing from the candidate snapshot';
  end if;

  if target_source_key = 'army_jrotc_v12'
     and (
       select count(distinct sc.course_key)
       from public.standard_entries se
       join public.standard_courses sc on sc.id = se.course_id
       where se.snapshot_id = target_snapshot_id
         and sc.source_id = target_source_id
         and sc.course_key in (
           'army_jrotc_let_1',
           'army_jrotc_let_2',
           'army_jrotc_let_3',
           'army_jrotc_let_4'
         )
     ) <> 4 then
    raise exception 'all four Army JROTC LET course standards are required';
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
    jsonb_build_object(
      'source_id', target_source_id,
      'source_key', target_source_key,
      'status', 'approved',
      'course_count', target_course_count,
      'entry_count', target_entry_count
    ),
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
