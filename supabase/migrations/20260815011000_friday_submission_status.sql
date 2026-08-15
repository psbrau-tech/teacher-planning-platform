-- Governed Friday professional-submission status for teacher and administrator dashboards.
-- Adult educator operational data only. No student data, reflection text, lesson-plan content,
-- generated insight, or draft content is returned.

create or replace function private.assignment_has_instruction_in_week(
  target_assignment_id uuid,
  target_week_start date
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.teaching_assignments ta
    cross join lateral generate_series(
      target_week_start::timestamp,
      (target_week_start + 6)::timestamp,
      interval '1 day'
    ) as day_value
    where ta.id = target_assignment_id
      and ta.is_active
      and day_value::date between ta.starts_on and ta.ends_on
      and exists (
        select 1
        from public.meeting_patterns mp
        where mp.teaching_assignment_id = ta.id
          and day_value::date between mp.effective_from and mp.effective_to
          and extract(isodow from day_value)::smallint = any(mp.weekdays)
      )
      and coalesce((
        select cd.is_instructional
        from public.calendar_days cd
        where cd.academic_year_id = ta.academic_year_id
          and cd.school_date = day_value::date
        limit 1
      ), true)
      and not exists (
        select 1
        from public.schedule_exceptions se
        where se.teaching_assignment_id = ta.id
          and se.exception_date = day_value::date
          and not se.is_available
      )
  )
$$;

revoke all on function private.assignment_has_instruction_in_week(uuid, date)
  from public, anon, authenticated, service_role;

comment on function private.assignment_has_instruction_in_week(uuid, date) is
  'Returns whether one teaching assignment has at least one expected instructional meeting in a Monday-starting week.';

create or replace function private.friday_assignment_status(
  target_week_start date
)
returns table (
  school_id uuid,
  school_name text,
  teacher_id uuid,
  teacher_name text,
  teacher_email text,
  assignment_id uuid,
  course_name text,
  current_week_required boolean,
  current_packet_submitted boolean,
  next_week_start date,
  next_week_required boolean,
  next_plan_submitted boolean
)
language sql
stable
security definer
set search_path = ''
as $$
  -- Submission truth comes directly from immutable weekly_plan_submissions by assignment + week.
  -- Do not anchor status to the newest mutable weekly_plan_snapshot: a newer working draft must
  -- never make an already-submitted packet or lesson plan appear missing.
  with status as (
    select
      ta.school_id,
      school.name as school_name,
      ta.teacher_id,
      teacher.display_name as teacher_name,
      lower(btrim(teacher.email)) as teacher_email,
      ta.id as assignment_id,
      ta.course_name,
      private.assignment_has_instruction_in_week(ta.id, target_week_start)
        as current_week_required,
      exists (
        select 1
        from public.weekly_plan_submissions wps
        where wps.teaching_assignment_id = ta.id
          and wps.school_id = ta.school_id
          and wps.teacher_id = ta.teacher_id
          and wps.week_start = target_week_start
          and wps.submission_kind = 'completed_packet'
      ) as current_packet_submitted,
      (target_week_start + 7)::date as next_week_start,
      private.assignment_has_instruction_in_week(ta.id, target_week_start + 7)
        as next_week_required,
      exists (
        select 1
        from public.weekly_plan_submissions wps
        where wps.teaching_assignment_id = ta.id
          and wps.school_id = ta.school_id
          and wps.teacher_id = ta.teacher_id
          and wps.week_start = (target_week_start + 7)::date
          and wps.submission_kind = 'lesson_plan'
      ) as next_plan_submitted
    from public.teaching_assignments ta
    join public.schools school on school.id = ta.school_id
    join public.profiles teacher
      on teacher.id = ta.teacher_id
      and teacher.school_id = ta.school_id
      and teacher.is_active
      and nullif(btrim(coalesce(teacher.email, '')), '') is not null
    where ta.is_active
      and exists (
        select 1
        from public.profile_roles teacher_role
        where teacher_role.profile_id = teacher.id
          and teacher_role.school_id = ta.school_id
          and teacher_role.role = 'teacher'::public.app_role
      )
  )
  select *
  from status
  where current_week_required or next_week_required
$$;

revoke all on function private.friday_assignment_status(date)
  from public, anon, authenticated, service_role;

comment on function private.friday_assignment_status(date) is
  'Internal immutable-submission status for current-week closeout and following-week lesson-plan requirements.';

create or replace function public.teacher_friday_submission_status(
  target_week_start date
)
returns table (
  assignment_id uuid,
  course_name text,
  current_week_required boolean,
  current_packet_submitted boolean,
  next_week_start date,
  next_week_required boolean,
  next_plan_submitted boolean
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if (select auth.uid()) is null
     or not private.has_role('teacher'::public.app_role, null) then
    raise exception 'Authenticated teacher is required' using errcode = '42501';
  end if;
  if target_week_start is null or extract(isodow from target_week_start) <> 1 then
    raise exception 'Friday status week_start must be a Monday' using errcode = '22023';
  end if;

  return query
  select
    f.assignment_id,
    f.course_name,
    f.current_week_required,
    f.current_packet_submitted,
    f.next_week_start,
    f.next_week_required,
    f.next_plan_submitted
  from private.friday_assignment_status(target_week_start) f
  where f.teacher_id = (select auth.uid())
  order by f.course_name, f.assignment_id;
end;
$$;

revoke all on function public.teacher_friday_submission_status(date)
  from public, anon, authenticated, service_role;
grant execute on function public.teacher_friday_submission_status(date)
  to authenticated;

create or replace function public.admin_friday_submission_status(
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
  current_week_required boolean,
  current_packet_submitted boolean,
  next_week_start date,
  next_week_required boolean,
  next_plan_submitted boolean
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
  if target_week_start is null or extract(isodow from target_week_start) <> 1 then
    raise exception 'Friday status week_start must be a Monday' using errcode = '22023';
  end if;

  return query
  select
    f.school_id,
    f.school_name,
    f.teacher_id,
    f.teacher_name,
    f.assignment_id,
    f.course_name,
    f.current_week_required,
    f.current_packet_submitted,
    f.next_week_start,
    f.next_week_required,
    f.next_plan_submitted
  from private.friday_assignment_status(target_week_start) f
  where private.can_report_school(f.school_id)
    and (target_school_id is null or f.school_id = target_school_id)
  order by f.school_name, f.teacher_name, f.course_name, f.assignment_id;
end;
$$;

revoke all on function public.admin_friday_submission_status(date, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_friday_submission_status(date, uuid)
  to authenticated;

notify pgrst, 'reload schema';
