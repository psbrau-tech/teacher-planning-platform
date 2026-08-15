-- Friday professional-workflow status, teacher reminders, and automatic admin digest support.
-- This deferred migration has not been applied to the pilot. It replaces the earlier admin-only
-- scheduled-digest design before activation. Adult professional operational data only: no student
-- data, reflection text, lesson-plan content, generated insight, email body, SES MessageId, or
-- recipient email address is persisted in the delivery ledger.

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
          and extract(isodow from day_value)::integer = any(mp.weekdays)
      )
      -- A missing calendar row is treated as the normal meeting pattern. An explicit
      -- non-instructional calendar day suppresses the reminder for that date.
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
  'Determines whether one professional teaching assignment has at least one expected instructional meeting in a Monday-starting week.';

create or replace function private.friday_assignment_status(
  target_week_start date
)
returns table (
  school_id uuid,
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
  with status as (
    select
      ta.school_id,
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
  'Internal professional submission status from immutable submitted weekly-plan records; no draft content or reflection text is returned.';

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
  order by f.teacher_name, f.course_name, f.assignment_id;
end;
$$;

revoke all on function public.admin_friday_submission_status(date, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.admin_friday_submission_status(date, uuid)
  to authenticated;

create table public.scheduled_notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  recipient_profile_id uuid not null references public.profiles(id) on delete cascade,
  week_start date not null,
  notification_key text not null,
  status text not null default 'claimed',
  claimed_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint scheduled_notification_deliveries_key_check check (
    notification_key in ('teacher_friday_reminder', 'admin_weekly_digest')
  ),
  constraint scheduled_notification_deliveries_status_check check (
    status in ('claimed', 'sent', 'failed')
  ),
  constraint scheduled_notification_deliveries_completed_check check (
    (status = 'claimed' and completed_at is null)
    or (status in ('sent', 'failed') and completed_at is not null)
  ),
  unique (notification_key, recipient_profile_id, week_start)
);

create index scheduled_notification_deliveries_school_week_idx
  on public.scheduled_notification_deliveries (school_id, week_start desc, status);
create index scheduled_notification_deliveries_recipient_week_idx
  on public.scheduled_notification_deliveries (recipient_profile_id, week_start desc);

alter table public.scheduled_notification_deliveries enable row level security;
revoke all on table public.scheduled_notification_deliveries
  from public, anon, authenticated, service_role;

comment on table public.scheduled_notification_deliveries is
  'At-most-once scheduled Friday notification claims using professional profile IDs; no recipient email, course list, or message content is persisted.';

create or replace function public.claim_teacher_friday_reminder_candidates(
  target_week_start date
)
returns table (
  delivery_id uuid,
  school_id uuid,
  recipient_profile_id uuid,
  recipient_email text,
  recipient_display_name text,
  next_week_start date,
  outstanding_items jsonb
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce((select auth.role())::text, '') <> 'service_role' then
    raise exception 'Scheduled notification worker role is required' using errcode = '42501';
  end if;
  if target_week_start is null or extract(isodow from target_week_start) <> 1 then
    raise exception 'Teacher reminder week_start must be a Monday' using errcode = '22023';
  end if;

  return query
  with needing as (
    select f.*
    from private.friday_assignment_status(target_week_start) f
    where (f.current_week_required and not f.current_packet_submitted)
       or (f.next_week_required and not f.next_plan_submitted)
  ),
  grouped as (
    select
      n.school_id,
      n.teacher_id as recipient_profile_id,
      n.teacher_email as recipient_email,
      n.teacher_name as recipient_display_name,
      (target_week_start + 7)::date as next_week_start,
      jsonb_agg(
        jsonb_build_object(
          'course_name', n.course_name,
          'missing_current_closeout',
            (n.current_week_required and not n.current_packet_submitted),
          'missing_next_plan',
            (n.next_week_required and not n.next_plan_submitted)
        )
        order by n.course_name, n.assignment_id
      ) as outstanding_items
    from needing n
    group by n.school_id, n.teacher_id, n.teacher_email, n.teacher_name
  ),
  inserted as (
    insert into public.scheduled_notification_deliveries (
      school_id,
      recipient_profile_id,
      week_start,
      notification_key,
      status
    )
    select
      g.school_id,
      g.recipient_profile_id,
      target_week_start,
      'teacher_friday_reminder',
      'claimed'
    from grouped g
    on conflict (notification_key, recipient_profile_id, week_start) do nothing
    returning
      scheduled_notification_deliveries.id,
      scheduled_notification_deliveries.school_id,
      scheduled_notification_deliveries.recipient_profile_id
  )
  select
    i.id,
    g.school_id,
    g.recipient_profile_id,
    g.recipient_email,
    g.recipient_display_name,
    g.next_week_start,
    g.outstanding_items
  from inserted i
  join grouped g
    on g.school_id = i.school_id
    and g.recipient_profile_id = i.recipient_profile_id
  order by g.school_id, g.recipient_profile_id;
end;
$$;

revoke all on function public.claim_teacher_friday_reminder_candidates(date)
  from public, anon, authenticated, service_role;
grant execute on function public.claim_teacher_friday_reminder_candidates(date)
  to service_role;

comment on function public.claim_teacher_friday_reminder_candidates(date) is
  'Service-role-only at-most-once teacher reminder manifest. Course names and missing-item flags are transient return values and are not persisted in the ledger.';

create or replace function public.claim_scheduled_admin_weekly_digest_candidates(
  target_week_start date
)
returns table (
  delivery_id uuid,
  school_id uuid,
  recipient_profile_id uuid,
  recipient_email text,
  current_teachers_expected integer,
  current_teachers_complete integer,
  current_packets_expected integer,
  current_packets_submitted integer,
  next_teachers_expected integer,
  next_teachers_complete integer,
  next_plans_expected integer,
  next_plans_submitted integer,
  teachers_with_completed_packets integer
)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce((select auth.role())::text, '') <> 'service_role' then
    raise exception 'Scheduled notification worker role is required' using errcode = '42501';
  end if;
  if target_week_start is null or extract(isodow from target_week_start) <> 1 then
    raise exception 'Scheduled digest week_start must be a Monday' using errcode = '22023';
  end if;

  return query
  with admin_recipients as (
    select distinct
      pr.school_id,
      p.id as recipient_profile_id,
      lower(btrim(p.email)) as recipient_email
    from public.profile_roles pr
    join public.profiles p
      on p.id = pr.profile_id
      and p.school_id = pr.school_id
      and p.is_active
      and nullif(btrim(coalesce(p.email, '')), '') is not null
    where pr.role = 'school_admin'::public.app_role
  ),
  teacher_rollup as (
    select
      f.school_id,
      f.teacher_id,
      count(*) filter (where f.current_week_required)::integer
        as current_expected_assignments,
      count(*) filter (
        where f.current_week_required and f.current_packet_submitted
      )::integer as current_submitted_assignments,
      count(*) filter (where f.next_week_required)::integer
        as next_expected_assignments,
      count(*) filter (
        where f.next_week_required and f.next_plan_submitted
      )::integer as next_submitted_assignments
    from private.friday_assignment_status(target_week_start) f
    group by f.school_id, f.teacher_id
  ),
  school_metrics as (
    select
      s.id as school_id,
      count(t.teacher_id) filter (
        where t.current_expected_assignments > 0
      )::integer as current_teachers_expected,
      count(t.teacher_id) filter (
        where t.current_expected_assignments > 0
          and t.current_expected_assignments = t.current_submitted_assignments
      )::integer as current_teachers_complete,
      coalesce(sum(t.current_expected_assignments), 0)::integer as current_packets_expected,
      coalesce(sum(t.current_submitted_assignments), 0)::integer as current_packets_submitted,
      count(t.teacher_id) filter (
        where t.next_expected_assignments > 0
      )::integer as next_teachers_expected,
      count(t.teacher_id) filter (
        where t.next_expected_assignments > 0
          and t.next_expected_assignments = t.next_submitted_assignments
      )::integer as next_teachers_complete,
      coalesce(sum(t.next_expected_assignments), 0)::integer as next_plans_expected,
      coalesce(sum(t.next_submitted_assignments), 0)::integer as next_plans_submitted,
      count(t.teacher_id) filter (
        where t.current_submitted_assignments > 0
      )::integer as teachers_with_completed_packets
    from public.schools s
    left join teacher_rollup t on t.school_id = s.id
    group by s.id
  ),
  eligible as (
    select
      r.school_id,
      r.recipient_profile_id,
      r.recipient_email,
      m.current_teachers_expected,
      m.current_teachers_complete,
      m.current_packets_expected,
      m.current_packets_submitted,
      m.next_teachers_expected,
      m.next_teachers_complete,
      m.next_plans_expected,
      m.next_plans_submitted,
      m.teachers_with_completed_packets
    from admin_recipients r
    join school_metrics m on m.school_id = r.school_id
  ),
  inserted as (
    insert into public.scheduled_notification_deliveries (
      school_id,
      recipient_profile_id,
      week_start,
      notification_key,
      status
    )
    select
      e.school_id,
      e.recipient_profile_id,
      target_week_start,
      'admin_weekly_digest',
      'claimed'
    from eligible e
    on conflict (notification_key, recipient_profile_id, week_start) do nothing
    returning
      scheduled_notification_deliveries.id,
      scheduled_notification_deliveries.school_id,
      scheduled_notification_deliveries.recipient_profile_id
  )
  select
    i.id,
    e.school_id,
    e.recipient_profile_id,
    e.recipient_email,
    e.current_teachers_expected,
    e.current_teachers_complete,
    e.current_packets_expected,
    e.current_packets_submitted,
    e.next_teachers_expected,
    e.next_teachers_complete,
    e.next_plans_expected,
    e.next_plans_submitted,
    e.teachers_with_completed_packets
  from inserted i
  join eligible e
    on e.school_id = i.school_id
    and e.recipient_profile_id = i.recipient_profile_id
  order by e.school_id, e.recipient_profile_id;
end;
$$;

revoke all on function public.claim_scheduled_admin_weekly_digest_candidates(date)
  from public, anon, authenticated, service_role;
grant execute on function public.claim_scheduled_admin_weekly_digest_candidates(date)
  to service_role;

comment on function public.claim_scheduled_admin_weekly_digest_candidates(date) is
  'Service-role-only at-most-once school-admin Friday digest manifest using current-week closeout and following-week lesson-plan counts only.';

create or replace function public.complete_scheduled_notification_delivery(
  target_delivery_id uuid,
  target_success boolean
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if coalesce((select auth.role())::text, '') <> 'service_role' then
    raise exception 'Scheduled notification worker role is required' using errcode = '42501';
  end if;

  update public.scheduled_notification_deliveries d
  set status = case when target_success then 'sent' else 'failed' end,
      completed_at = now()
  where d.id = target_delivery_id
    and d.status = 'claimed';

  if not found then
    raise exception 'Scheduled notification delivery claim is unavailable' using errcode = '40001';
  end if;
end;
$$;

revoke all on function public.complete_scheduled_notification_delivery(uuid, boolean)
  from public, anon, authenticated, service_role;
grant execute on function public.complete_scheduled_notification_delivery(uuid, boolean)
  to service_role;

-- Preserve the existing Platform Owner notification-adoption contract. Teacher reminder delivery
-- is intentionally not mixed into the admin-digest counters.
drop function if exists public.platform_notification_usage(date, date);
create function public.platform_notification_usage(
  target_start date,
  target_end date
)
returns table (
  period_start date,
  period_end date,
  admin_weekly_digests_sent integer,
  admin_digest_senders integer,
  scheduled_admin_weekly_digests_sent integer,
  scheduled_digest_recipient_admins integer,
  scheduled_digest_schools integer
)
language sql
stable
security definer
set search_path = ''
as $$
  with manual as (
    select
      count(*) filter (
        where e.notification_key = 'admin_weekly_digest_sent'
      )::integer as sent,
      count(distinct e.actor_id) filter (
        where e.notification_key = 'admin_weekly_digest_sent'
      )::integer as senders
    from public.notification_delivery_events e
    where e.occurred_at >= target_start::timestamptz
      and e.occurred_at < (target_end + 1)::timestamptz
  ),
  scheduled as (
    select
      count(*) filter (
        where d.status = 'sent' and d.notification_key = 'admin_weekly_digest'
      )::integer as sent,
      count(distinct d.recipient_profile_id) filter (
        where d.status = 'sent' and d.notification_key = 'admin_weekly_digest'
      )::integer as recipients,
      count(distinct d.school_id) filter (
        where d.status = 'sent' and d.notification_key = 'admin_weekly_digest'
      )::integer as schools
    from public.scheduled_notification_deliveries d
    where d.completed_at >= target_start::timestamptz
      and d.completed_at < (target_end + 1)::timestamptz
  )
  select
    target_start,
    target_end,
    (manual.sent + scheduled.sent)::integer,
    manual.senders,
    scheduled.sent,
    scheduled.recipients,
    scheduled.schools
  from manual, scheduled
  where target_end >= target_start
    and private.has_role('platform_admin'::public.app_role, null)
$$;

revoke all on function public.platform_notification_usage(date, date)
  from public, anon, authenticated, service_role;
grant execute on function public.platform_notification_usage(date, date)
  to authenticated;

notify pgrst, 'reload schema';
