-- Teacher-owned immutable completed-packet review.
-- The table remains non-readable directly; authenticated teachers receive only their own
-- latest completed packet for the requested assignment/week through this narrow RPC.

create or replace function public.teacher_completed_weekly_submission_document(
  target_assignment_id uuid,
  target_week_start date
)
returns table (
  revision integer,
  submitted_at timestamptz,
  source_data jsonb
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated teacher is required' using errcode = '42501';
  end if;

  if extract(isodow from target_week_start) <> 1 then
    raise exception 'Week of must be a Monday' using errcode = '22023';
  end if;

  return query
  select
    wps.revision,
    wps.submitted_at,
    wps.source_data
  from public.weekly_plan_submissions wps
  where wps.teaching_assignment_id = target_assignment_id
    and wps.teacher_id = (select auth.uid())
    and wps.week_start = target_week_start
    and wps.submission_kind = 'completed_packet'
  order by wps.revision desc, wps.submitted_at desc
  limit 1;
end;
$$;

revoke all on function public.teacher_completed_weekly_submission_document(uuid, date)
  from public, anon, authenticated, service_role;
grant execute on function public.teacher_completed_weekly_submission_document(uuid, date)
  to authenticated;

comment on function public.teacher_completed_weekly_submission_document(uuid, date) is
  'Returns only the authenticated teacher''s latest immutable completed weekly packet source for one assignment and Monday-starting week.';

notify pgrst, 'reload schema';
