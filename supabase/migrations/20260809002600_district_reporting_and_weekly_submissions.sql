-- District-scoped reporting and explicit teacher weekly-plan submission.
-- This migration stays inside the adult educator/administrator data boundary.

create or replace function private.current_district_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select s.district_id
  from public.profiles p
  join public.schools s on s.id = p.school_id
  where p.id = (select auth.uid())
    and p.is_active
$$;

create or replace function private.can_report_school(target_school_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    private.has_role('platform_admin'::public.app_role, null)
    or private.has_role('school_admin'::public.app_role, target_school_id)
    or (
      private.has_role('district_admin'::public.app_role, null)
      and exists (
        select 1
        from public.schools s
        where s.id = target_school_id
          and s.district_id = private.current_district_id()
      )
    )
$$;

revoke all on function private.current_district_id() from public, anon, authenticated, service_role;
revoke all on function private.can_report_school(uuid) from public, anon, authenticated, service_role;
grant execute on function private.current_district_id() to authenticated;
grant execute on function private.can_report_school(uuid) to authenticated;

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
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated teacher is required'
      using errcode = '42501';
  end if;

  select
    w.id,
    w.revision,
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

  update public.weekly_plan_snapshots w
  set is_draft = false,
      approved_by = (select auth.uid()),
      approved_at = now(),
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
  'Explicit teacher-controlled weekly-plan submission. Submission does not change content or revision; later draft edits mark the plan draft again while retaining prior submission time.';

create or replace function public.admin_weekly_submission_status(
  target_week_start date,
  target_school_id uuid default null
)
returns table (
  school_id uuid,
  school_name text,
  teacher_id uuid,
  teacher_name text,
  assignment_id uuid,
  course_name text,
  week_start date,
  revision integer,
  submission_status text,
  submitted_at timestamptz,
  generated_document_count bigint
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated administrator is required'
      using errcode = '42501';
  end if;

  if not (
    private.has_role('platform_admin'::public.app_role, null)
    or private.has_role('school_admin'::public.app_role, null)
    or private.has_role('district_admin'::public.app_role, null)
  ) then
    raise exception 'Administration reporting is not authorized'
      using errcode = '42501';
  end if;

  return query
  select
    s.id,
    s.name,
    p.id,
    p.display_name,
    ta.id,
    ta.course_name,
    target_week_start,
    w.revision,
    case
      when ta.id is null then 'no_course'
      when w.id is null then 'not_started'
      when w.approved_at is null then 'draft'
      when w.is_draft then 'revised_after_submission'
      else 'submitted'
    end,
    w.approved_at,
    count(gd.id) filter (where gd.status = 'generated')::bigint
  from public.profile_roles pr
  join public.profiles p
    on p.id = pr.profile_id
   and p.is_active
  join public.schools s
    on s.id = pr.school_id
  left join public.teaching_assignments ta
    on ta.teacher_id = p.id
   and ta.school_id = s.id
   and ta.is_active
  left join public.weekly_plan_snapshots w
    on w.teaching_assignment_id = ta.id
   and w.week_start = target_week_start
  left join public.generated_documents gd
    on gd.weekly_plan_snapshot_id = w.id
  where pr.role = 'teacher'::public.app_role
    and private.can_report_school(s.id)
    and (target_school_id is null or s.id = target_school_id)
  group by
    s.id,
    s.name,
    p.id,
    p.display_name,
    ta.id,
    ta.course_name,
    w.id,
    w.revision,
    w.is_draft,
    w.approved_at
  order by s.name, p.display_name, ta.course_name nulls last;
end;
$$;

revoke all on function public.admin_weekly_submission_status(date, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_weekly_submission_status(date, uuid) to authenticated;

comment on function public.admin_weekly_submission_status(date, uuid) is
  'Role-scoped professional weekly-plan submission reporting. School admins are school-scoped; district admins are district-scoped; platform admins may report across governed schools. No student data is returned.';

notify pgrst, 'reload schema';
