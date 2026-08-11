-- Gate E: ACT snapshot approval accepts either skill-framework entries or benchmark rows.

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
  target_source_type text;
  entry_count integer := 0;
  benchmark_count integer := 0;
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  select ars.source_id, ars.status, ars.source_sha256, src.source_type
    into target_source_id, target_status, target_sha, target_source_type
  from public.act_reference_snapshots ars
  join public.act_reference_sources src on src.id = ars.source_id
  where ars.id = target_snapshot_id
  for update of ars;

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

  select count(*) into entry_count
  from public.act_reference_entries aref
  where aref.snapshot_id = target_snapshot_id;

  select count(*) into benchmark_count
  from public.act_readiness_benchmarks arb
  where arb.snapshot_id = target_snapshot_id;

  if target_source_type = 'readiness_benchmark' then
    if benchmark_count = 0 or entry_count <> 0 then
      raise exception 'ACT benchmark snapshot must contain benchmark rows only';
    end if;
  elsif target_source_type = 'assessment_skill_framework' then
    if entry_count = 0 or benchmark_count <> 0 then
      raise exception 'ACT skill-framework snapshot must contain reference entries only';
    end if;
  else
    raise exception 'ACT source type is not yet eligible for structured snapshot approval';
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
    jsonb_build_object(
      'source_id', target_source_id,
      'source_type', target_source_type,
      'status', 'approved',
      'reference_entry_count', entry_count,
      'benchmark_count', benchmark_count
    ),
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
