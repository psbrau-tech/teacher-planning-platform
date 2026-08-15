-- Isolated scheduled admin-digest delivery ledger and service-role-only candidate RPCs.
-- This is adult professional operational data only. No reflection text, generated insight,
-- student data, email body, SES MessageId, or recipient email address is persisted here.

create table public.scheduled_notification_deliveries (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  recipient_profile_id uuid not null references public.profiles(id) on delete cascade,
  week_start date not null,
  notification_key text not null default 'admin_weekly_digest',
  status text not null default 'claimed',
  claimed_at timestamptz not null default now(),
  completed_at timestamptz,
  constraint scheduled_notification_deliveries_key_check check (
    notification_key = 'admin_weekly_digest'
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
  'At-most-once scheduled TPP admin digest claims using professional profile IDs; no recipient email or message content is persisted.';

create or replace function public.claim_scheduled_admin_weekly_digest_candidates(
  target_week_start date
)
returns table (
  delivery_id uuid,
  school_id uuid,
  recipient_profile_id uuid,
  recipient_email text,
  configured_assignments integer,
  lesson_plans_submitted integer,
  lesson_plans_missing integer,
  completed_packets_submitted integer,
  completed_packets_missing integer,
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
      and p.is_active
      and nullif(btrim(coalesce(p.email, '')), '') is not null
    where pr.role = 'school_admin'::public.app_role
  ),
  assignment_status as (
    select
      ta.school_id,
      ta.teacher_id,
      ta.id as assignment_id,
      lesson_plan.revision as lesson_plan_revision,
      completed_packet.revision as completed_packet_revision
    from public.teaching_assignments ta
    join public.profiles teacher
      on teacher.id = ta.teacher_id
      and teacher.is_active
    join public.profile_roles teacher_role
      on teacher_role.profile_id = teacher.id
      and teacher_role.school_id = ta.school_id
      and teacher_role.role = 'teacher'::public.app_role
    left join lateral (
      select w.id
      from public.weekly_plan_snapshots w
      where w.teaching_assignment_id = ta.id
        and w.week_start = target_week_start
      order by w.revision desc, w.updated_at desc
      limit 1
    ) snapshot on true
    left join lateral (
      select wps.revision
      from public.weekly_plan_submissions wps
      where wps.weekly_plan_snapshot_id = snapshot.id
        and wps.submission_kind = 'lesson_plan'
      order by wps.revision desc, wps.submitted_at desc
      limit 1
    ) lesson_plan on true
    left join lateral (
      select wps.revision
      from public.weekly_plan_submissions wps
      where wps.weekly_plan_snapshot_id = snapshot.id
        and wps.submission_kind = 'completed_packet'
      order by wps.revision desc, wps.submitted_at desc
      limit 1
    ) completed_packet on true
    where ta.is_active
  ),
  school_metrics as (
    select
      s.id as school_id,
      count(a.assignment_id)::integer as configured_assignments,
      count(a.assignment_id) filter (
        where a.lesson_plan_revision is not null
      )::integer as lesson_plans_submitted,
      count(a.assignment_id) filter (
        where a.completed_packet_revision is not null
      )::integer as completed_packets_submitted,
      count(distinct a.teacher_id) filter (
        where a.completed_packet_revision is not null
      )::integer as teachers_with_completed_packets
    from public.schools s
    left join assignment_status a on a.school_id = s.id
    group by s.id
  ),
  eligible as (
    select
      r.school_id,
      r.recipient_profile_id,
      r.recipient_email,
      m.configured_assignments,
      m.lesson_plans_submitted,
      (m.configured_assignments - m.lesson_plans_submitted)::integer
        as lesson_plans_missing,
      m.completed_packets_submitted,
      (m.configured_assignments - m.completed_packets_submitted)::integer
        as completed_packets_missing,
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
    e.configured_assignments,
    e.lesson_plans_submitted,
    e.lesson_plans_missing,
    e.completed_packets_submitted,
    e.completed_packets_missing,
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
  'Service-role-only at-most-once candidate manifest for school-admin weekly digests; raw lesson/reflection content is excluded.';

create or replace function public.complete_scheduled_admin_weekly_digest_delivery(
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

revoke all on function public.complete_scheduled_admin_weekly_digest_delivery(uuid, boolean)
  from public, anon, authenticated, service_role;
grant execute on function public.complete_scheduled_admin_weekly_digest_delivery(uuid, boolean)
  to service_role;

-- Expand Platform Owner notification adoption reporting while keeping the original total field.
-- admin_weekly_digests_sent = all successful manual + scheduled deliveries in the period.
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
      count(*) filter (where d.status = 'sent')::integer as sent,
      count(distinct d.recipient_profile_id) filter (
        where d.status = 'sent'
      )::integer as recipients,
      count(distinct d.school_id) filter (
        where d.status = 'sent'
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
