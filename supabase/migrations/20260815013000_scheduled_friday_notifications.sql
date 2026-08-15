-- Deferred automatic Friday email delivery support.
-- Apply only when SES and the two approved Friday schedules are ready for activation.
-- Adult professional operational data only. The ledger persists profile IDs and delivery status,
-- never recipient email, course lists, reflection text, lesson-plan content, student data,
-- message bodies, generated insight, or SES MessageIds.

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

-- Preserve the existing Platform Owner admin-notification adoption contract. Teacher reminders
-- are a courtesy workflow and are intentionally not mixed into administrator delivery counts.
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
