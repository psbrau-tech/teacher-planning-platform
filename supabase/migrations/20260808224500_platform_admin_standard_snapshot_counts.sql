-- Gate E: exact Platform Administrator counts for pending standards review.
-- Pending standard entries remain protected by their existing table RLS. The
-- administration API uses this authenticated, role-gated aggregate instead of
-- inferring counts from potentially RLS-filtered or row-limited REST reads.

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

notify pgrst, 'reload schema';
