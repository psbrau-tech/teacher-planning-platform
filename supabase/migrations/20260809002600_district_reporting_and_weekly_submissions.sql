-- District-scoped reporting and explicit teacher weekly-plan submission.
-- This migration stays inside the adult educator/administrator data boundary.

create table if not exists public.weekly_plan_submissions (
  id uuid primary key default gen_random_uuid(),
  weekly_plan_snapshot_id uuid not null references public.weekly_plan_snapshots(id) on delete cascade,
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  school_id uuid not null references public.schools(id) on delete cascade,
  teacher_id uuid not null references public.profiles(id) on delete cascade,
  week_start date not null,
  revision integer not null check (revision > 0),
  source_data jsonb not null,
  submitted_by uuid not null references public.profiles(id),
  submitted_at timestamptz not null default now(),
  unique (weekly_plan_snapshot_id, revision)
);

create index if not exists weekly_plan_submissions_school_week_idx
  on public.weekly_plan_submissions (school_id, week_start, teacher_id);
create index if not exists weekly_plan_submissions_assignment_week_idx
  on public.weekly_plan_submissions (teaching_assignment_id, week_start, revision desc);

alter table public.weekly_plan_submissions enable row level security;
revoke all on table public.weekly_plan_submissions from public, anon, authenticated, service_role;

comment on table public.weekly_plan_submissions is
  'Immutable professional weekly-plan content captured only when a teacher explicitly submits a saved revision.';

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
  );

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
  'Explicit teacher-controlled weekly-plan submission. Each submitted revision is copied to an immutable professional submission record before the editable snapshot is marked submitted.';

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
  submitted_revision integer,
  submission_status text,
  submitted_at timestamptz
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
    latest_submission.revision,
    case
      when ta.id is null then 'no_course'
      when w.id is null then 'not_started'
      when latest_submission.revision is null then 'draft'
      when w.is_draft or w.revision > latest_submission.revision then 'revised_after_submission'
      else 'submitted'
    end,
    latest_submission.submitted_at
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
  left join lateral (
    select wps.revision, wps.submitted_at
    from public.weekly_plan_submissions wps
    where wps.weekly_plan_snapshot_id = w.id
    order by wps.revision desc, wps.submitted_at desc
    limit 1
  ) latest_submission on true
  where pr.role = 'teacher'::public.app_role
    and private.can_report_school(s.id)
    and (target_school_id is null or s.id = target_school_id)
  order by s.name, p.display_name, ta.course_name nulls last;
end;
$$;

revoke all on function public.admin_weekly_submission_status(date, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_weekly_submission_status(date, uuid) to authenticated;

comment on function public.admin_weekly_submission_status(date, uuid) is
  'Role-scoped professional weekly-plan submission reporting. School admins are school-scoped; district admins are district-scoped; platform admins may report across governed schools. No student data is returned.';

create or replace function public.admin_weekly_submission_document(
  target_assignment_id uuid,
  target_week_start date
)
returns table (
  school_id uuid,
  school_name text,
  teacher_id uuid,
  teacher_name text,
  assignment_id uuid,
  course_name text,
  week_start date,
  submitted_revision integer,
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
    raise exception 'Authenticated administrator is required'
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
    wps.week_start,
    wps.revision,
    wps.submitted_at,
    wps.source_data
  from public.weekly_plan_submissions wps
  join public.teaching_assignments ta on ta.id = wps.teaching_assignment_id
  join public.profiles p on p.id = wps.teacher_id
  join public.schools s on s.id = wps.school_id
  where wps.teaching_assignment_id = target_assignment_id
    and wps.week_start = target_week_start
    and private.can_report_school(s.id)
  order by wps.revision desc, wps.submitted_at desc
  limit 1;
end;
$$;

revoke all on function public.admin_weekly_submission_document(uuid, date)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_weekly_submission_document(uuid, date) to authenticated;

comment on function public.admin_weekly_submission_document(uuid, date) is
  'Returns only the latest immutable submitted professional plan for an administrator authorized to report on the assignment school.';

notify pgrst, 'reload schema';
