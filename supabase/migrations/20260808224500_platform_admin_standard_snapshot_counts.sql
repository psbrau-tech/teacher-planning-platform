-- Gate E: exact Platform Administrator counts for pending Alabama and ACT review.
-- Pending authoritative rows remain protected by their existing table RLS. The
-- administration APIs use these authenticated, role-gated aggregates instead of
-- inferring counts from RLS-filtered or row-limited REST reads.

create or replace function public.platform_admin_standard_snapshot_counts()
returns table (
  snapshot_id uuid,
  course_count bigint,
  standard_entry_count bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  return query
  select
    ss.id as snapshot_id,
    (
      select count(*)
      from public.standard_snapshot_courses ssc
      where ssc.snapshot_id = ss.id
    )::bigint as course_count,
    (
      select count(*)
      from public.standard_entries se
      where se.snapshot_id = ss.id
    )::bigint as standard_entry_count
  from public.standard_snapshots ss
  where ss.status = 'pending'
  order by ss.retrieved_at desc, ss.id;
end;
$$;

revoke all on function public.platform_admin_standard_snapshot_counts()
  from public, anon, authenticated, service_role;
grant execute on function public.platform_admin_standard_snapshot_counts()
  to authenticated;

create or replace function public.platform_admin_act_reference_snapshot_counts()
returns table (
  snapshot_id uuid,
  entry_count bigint,
  benchmark_count bigint
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  return query
  select
    ars.id as snapshot_id,
    (
      select count(*)
      from public.act_reference_entries aref
      where aref.snapshot_id = ars.id
    )::bigint as entry_count,
    (
      select count(*)
      from public.act_readiness_benchmarks arb
      where arb.snapshot_id = ars.id
    )::bigint as benchmark_count
  from public.act_reference_snapshots ars
  where ars.status = 'pending'
  order by ars.retrieved_at desc, ars.id;
end;
$$;

revoke all on function public.platform_admin_act_reference_snapshot_counts()
  from public, anon, authenticated, service_role;
grant execute on function public.platform_admin_act_reference_snapshot_counts()
  to authenticated;

notify pgrst, 'reload schema';
