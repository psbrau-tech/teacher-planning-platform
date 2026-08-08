-- Gate E: platform-admin approval for deterministic public ACT reference snapshots.

create or replace function public.approve_act_reference_snapshot(target_snapshot_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
  target_source_id uuid;
  target_status text;
  target_sha text;
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  select ars.source_id, ars.status, ars.source_sha256
    into target_source_id, target_status, target_sha
  from public.act_reference_snapshots ars
  where ars.id = target_snapshot_id
  for update;

  if target_source_id is null then
    raise exception 'ACT reference snapshot not found';
  end if;

  if target_status = 'approved' then
    return jsonb_build_object(
      'snapshot_id', target_snapshot_id,
      'source_id', target_source_id,
      'status', 'approved',
      'changed', false
    );
  end if;

  if target_status <> 'pending' then
    raise exception 'only pending ACT reference snapshots may be approved';
  end if;

  if not exists (
    select 1 from public.act_reference_entries are
    where are.snapshot_id = target_snapshot_id
  ) then
    raise exception 'ACT reference snapshot has no parsed entries';
  end if;

  update public.act_reference_snapshots
  set status = 'superseded'
  where source_id = target_source_id
    and status = 'approved'
    and id <> target_snapshot_id;

  update public.act_reference_snapshots
  set status = 'approved',
      approved_by = actor_id,
      approved_at = now()
  where id = target_snapshot_id;

  update public.act_reference_sources
  set retrieved_at = now(),
      source_sha256 = target_sha,
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
    'act_reference_snapshot',
    target_snapshot_id,
    'approve_act_reference_snapshot',
    jsonb_build_object('source_id', target_source_id, 'status', 'approved'),
    'Platform administrator approved deterministic public first-party ACT reference snapshot'
  );

  return jsonb_build_object(
    'snapshot_id', target_snapshot_id,
    'source_id', target_source_id,
    'status', 'approved',
    'changed', true
  );
end;
$$;

revoke all on function public.approve_act_reference_snapshot(uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.approve_act_reference_snapshot(uuid)
  to authenticated;
