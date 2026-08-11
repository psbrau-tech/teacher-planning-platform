-- Distinguish the pre-instruction weekly lesson-plan submission from the
-- end-of-week completed packet that attaches the teacher-authored reflection.
-- Both records remain immutable professional planning submissions.

alter table public.weekly_plan_submissions
  add column if not exists submission_kind text not null default 'lesson_plan';

alter table public.weekly_plan_submissions
  drop constraint if exists weekly_plan_submissions_submission_kind_check;

alter table public.weekly_plan_submissions
  add constraint weekly_plan_submissions_submission_kind_check
  check (submission_kind in ('lesson_plan', 'completed_packet'));

-- Preserve existing immutable content while classifying the old pilot rows.
-- A stored, nonblank reflection can only have come from the end-of-week closeout path.
update public.weekly_plan_submissions
set submission_kind = 'completed_packet'
where nullif(btrim(coalesce(source_data ->> 'reflection', '')), '') is not null;

alter table public.weekly_plan_submissions
  drop constraint if exists weekly_plan_submissions_weekly_plan_snapshot_id_revision_key;

alter table public.weekly_plan_submissions
  add constraint weekly_plan_submissions_snapshot_revision_kind_key
  unique (weekly_plan_snapshot_id, revision, submission_kind);

create index if not exists weekly_plan_submissions_kind_school_week_idx
  on public.weekly_plan_submissions (submission_kind, school_id, week_start, teacher_id);

comment on column public.weekly_plan_submissions.submission_kind is
  'lesson_plan = pre-instruction plan/grid submission; completed_packet = end-of-week plan plus teacher-authored reflection.';

create or replace function public.submit_weekly_plan_typed(
  target_snapshot_id uuid,
  expected_revision integer,
  target_submission_kind text
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
    raise exception 'Authenticated teacher is required' using errcode = '42501';
  end if;

  if target_submission_kind not in ('lesson_plan', 'completed_packet') then
    raise exception 'Unsupported weekly submission kind' using errcode = '22023';
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
    raise exception 'Weekly plan submission is not authorized' using errcode = '42501';
  end if;

  if current_record.revision <> expected_revision then
    raise exception 'Weekly plan revision conflict' using errcode = '40001';
  end if;

  if target_submission_kind = 'completed_packet'
     and nullif(btrim(coalesce(current_record.source_data ->> 'reflection', '')), '') is null then
    raise exception 'Completed packet requires the teacher reflection' using errcode = '23514';
  end if;

  select wps.submitted_at
    into existing_submitted_at
  from public.weekly_plan_submissions wps
  where wps.weekly_plan_snapshot_id = current_record.id
    and wps.revision = current_record.revision
    and wps.submission_kind = target_submission_kind
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
      submitted_by,
      submission_kind
    ) values (
      current_record.id,
      current_record.teaching_assignment_id,
      current_record.school_id,
      current_record.teacher_id,
      current_record.week_start,
      current_record.revision,
      current_record.source_data,
      (select auth.uid()),
      target_submission_kind
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
    raise exception 'Weekly plan revision conflict' using errcode = '40001';
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
      case
        when target_submission_kind = 'completed_packet' then 'submit_weekly_completed_packet'
        else 'submit_weekly_lesson_plan'
      end,
      jsonb_build_object(
        'revision', updated_record.revision,
        'submission_kind', target_submission_kind,
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

revoke all on function public.submit_weekly_plan_typed(uuid, integer, text)
  from public, anon, authenticated, service_role;
grant execute on function public.submit_weekly_plan_typed(uuid, integer, text) to authenticated;

comment on function public.submit_weekly_plan_typed(uuid, integer, text) is
  'Explicit teacher-controlled immutable submission of either the upcoming lesson plan or the completed weekly packet.';

create or replace function public.admin_weekly_submission_status_v2(
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
  lesson_plan_revision integer,
  lesson_plan_submitted_at timestamptz,
  completed_packet_revision integer,
  completed_packet_submitted_at timestamptz
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated administrator is required' using errcode = '42501';
  end if;

  if not (
    private.has_role('platform_admin'::public.app_role, null)
    or private.has_role('school_admin'::public.app_role, null)
    or private.has_role('district_admin'::public.app_role, null)
  ) then
    raise exception 'Administration reporting is not authorized' using errcode = '42501';
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
    lesson_plan.revision,
    lesson_plan.submitted_at,
    completed_packet.revision,
    completed_packet.submitted_at
  from public.profile_roles pr
  join public.profiles p on p.id = pr.profile_id and p.is_active
  join public.schools s on s.id = pr.school_id
  left join public.teaching_assignments ta
    on ta.teacher_id = p.id and ta.school_id = s.id and ta.is_active
  left join public.weekly_plan_snapshots w
    on w.teaching_assignment_id = ta.id and w.week_start = target_week_start
  left join lateral (
    select wps.revision, wps.submitted_at
    from public.weekly_plan_submissions wps
    where wps.weekly_plan_snapshot_id = w.id
      and wps.submission_kind = 'lesson_plan'
    order by wps.revision desc, wps.submitted_at desc
    limit 1
  ) lesson_plan on true
  left join lateral (
    select wps.revision, wps.submitted_at
    from public.weekly_plan_submissions wps
    where wps.weekly_plan_snapshot_id = w.id
      and wps.submission_kind = 'completed_packet'
    order by wps.revision desc, wps.submitted_at desc
    limit 1
  ) completed_packet on true
  where pr.role = 'teacher'::public.app_role
    and private.can_report_school(s.id)
    and (target_school_id is null or s.id = target_school_id)
  order by s.name, p.display_name, ta.course_name nulls last;
end;
$$;

revoke all on function public.admin_weekly_submission_status_v2(date, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_weekly_submission_status_v2(date, uuid) to authenticated;

create or replace function public.admin_weekly_submission_document_by_kind(
  target_assignment_id uuid,
  target_week_start date,
  target_submission_kind text
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
  submission_kind text,
  source_data jsonb
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'Authenticated administrator is required' using errcode = '42501';
  end if;

  if target_submission_kind not in ('lesson_plan', 'completed_packet') then
    raise exception 'Unsupported weekly submission kind' using errcode = '22023';
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
    wps.submission_kind,
    wps.source_data
  from public.weekly_plan_submissions wps
  join public.teaching_assignments ta on ta.id = wps.teaching_assignment_id
  join public.profiles p on p.id = wps.teacher_id
  join public.schools s on s.id = wps.school_id
  where wps.teaching_assignment_id = target_assignment_id
    and wps.week_start = target_week_start
    and wps.submission_kind = target_submission_kind
    and private.can_report_school(s.id)
  order by wps.revision desc, wps.submitted_at desc
  limit 1;
end;
$$;

revoke all on function public.admin_weekly_submission_document_by_kind(uuid, date, text)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_weekly_submission_document_by_kind(uuid, date, text) to authenticated;

comment on function public.admin_weekly_submission_document_by_kind(uuid, date, text) is
  'Returns the latest immutable professional submission for one week and one governed submission kind.';

notify pgrst, 'reload schema';