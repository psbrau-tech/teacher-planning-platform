-- Make retries of the same explicit weekly-plan submission idempotent.
-- A repeated request for an already submitted revision returns the original
-- submission timestamp and does not create a second immutable record or audit event.

create or replace function public.submit_weekly_plan(
  target_snapshot_id uuid,
  expected_revision integer
)
returns table (
  id uuid,
  revision integer,
  is_draft boolean,
  submitted_at timestamptz,
  updated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_record record;
  updated_record record;
  existing_submitted_at timestamptz;
  effective_submitted_at timestamptz;
  created_submission boolean := false;
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated teacher is required'
      using errcode = '42501';
  end if;

  select
    w.id,
    w.revision,
    w.source_data,
    w.week_start,
    ta.teacher_id,
    ta.school_id,
    w.teaching_assignment_id
  into current_record
  from public.weekly_plan_snapshots w
  join public.teaching_assignments ta on ta.id = w.teaching_assignment_id
  where w.id = target_snapshot_id;

  if not found or current_record.teacher_id <> (select auth.uid()) then
    raise exception 'Weekly plan submission is not authorized'
      using errcode = '42501';
  end if;

  if current_record.revision <> expected_revision then
    raise exception 'Weekly plan revision conflict'
      using errcode = '40001';
  end if;

  select wps.submitted_at
    into existing_submitted_at
  from public.weekly_plan_submissions wps
  where wps.weekly_plan_snapshot_id = current_record.id
    and wps.revision = current_record.revision
  limit 1;

  if existing_submitted_at is null then
    insert into public.weekly_plan_submissions (
      weekly_plan_snapshot_id,
      teaching_assignment_id,
      school_id,
      teacher_id,
      week_start,
      revision,
      source_data,
      submitted_by
    ) values (
      current_record.id,
      current_record.teaching_assignment_id,
      current_record.school_id,
      current_record.teacher_id,
      current_record.week_start,
      current_record.revision,
      current_record.source_data,
      (select auth.uid())
    )
    returning weekly_plan_submissions.submitted_at into effective_submitted_at;
    created_submission := true;
  else
    effective_submitted_at := existing_submitted_at;
  end if;

  update public.weekly_plan_snapshots w
  set is_draft = false,
      approved_by = (select auth.uid()),
      approved_at = effective_submitted_at,
      updated_by = (select auth.uid()),
      updated_at = now()
  where w.id = target_snapshot_id
    and w.revision = expected_revision
  returning w.id, w.revision, w.is_draft, w.approved_at, w.updated_at
  into updated_record;

  if not found then
    raise exception 'Weekly plan revision conflict'
      using errcode = '40001';
  end if;

  if created_submission then
    insert into public.audit_events (
      school_id,
      actor_id,
      entity_type,
      entity_id,
      action,
      after_data
    ) values (
      current_record.school_id,
      (select auth.uid()),
      'weekly_plan_snapshot',
      target_snapshot_id,
      'submit_weekly_plan',
      jsonb_build_object(
        'revision', updated_record.revision,
        'submitted_at', updated_record.approved_at
      )
    );
  end if;

  return query
  select
    updated_record.id::uuid,
    updated_record.revision::integer,
    updated_record.is_draft::boolean,
    updated_record.approved_at::timestamptz,
    updated_record.updated_at::timestamptz;
end;
$$;

revoke all on function public.submit_weekly_plan(uuid, integer)
  from public, anon, authenticated, service_role;
grant execute on function public.submit_weekly_plan(uuid, integer) to authenticated;

comment on function public.submit_weekly_plan(uuid, integer) is
  'Explicit teacher-controlled weekly-plan submission. Same-revision retries are idempotent and preserve the original immutable submission timestamp.';

notify pgrst, 'reload schema';
