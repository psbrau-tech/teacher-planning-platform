-- Content-free delivery telemetry for school-scoped TPP notification emails.
-- No email body, reflection text, teacher-quality data, student data, or recipient address is stored.

create table public.notification_delivery_events (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools(id) on delete cascade,
  actor_id uuid not null references public.profiles(id) on delete cascade,
  notification_key text not null,
  occurred_at timestamptz not null default now(),
  constraint notification_delivery_events_key_check check (
    notification_key in ('admin_weekly_digest_sent')
  )
);

create index notification_delivery_events_school_time_idx
  on public.notification_delivery_events (school_id, occurred_at desc);
create index notification_delivery_events_actor_time_idx
  on public.notification_delivery_events (actor_id, occurred_at desc);
create index notification_delivery_events_key_time_idx
  on public.notification_delivery_events (notification_key, occurred_at desc);

alter table public.notification_delivery_events enable row level security;
revoke all on table public.notification_delivery_events
  from public, anon, authenticated, service_role;

comment on table public.notification_delivery_events is
  'Content-free TPP email delivery telemetry: school, requesting professional, event key, and timestamp only.';

create or replace function public.record_notification_delivery_event(
  target_notification_key text,
  target_school_id uuid default null
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor uuid := (select auth.uid());
  actor_school uuid;
  effective_school uuid;
  inserted_id uuid;
begin
  if actor is null then
    raise exception 'Authenticated professional user is required' using errcode = '42501';
  end if;

  if target_notification_key <> 'admin_weekly_digest_sent' then
    raise exception 'Unsupported TPP notification event' using errcode = '22023';
  end if;

  select p.school_id into actor_school
  from public.profiles p
  where p.id = actor and p.is_active;

  if actor_school is null then
    raise exception 'Active governed school context is required' using errcode = '42501';
  end if;

  effective_school := coalesce(target_school_id, actor_school);
  if not private.can_report_school(effective_school) then
    raise exception 'School reporting access is required' using errcode = '42501';
  end if;

  insert into public.notification_delivery_events (school_id, actor_id, notification_key)
  values (effective_school, actor, target_notification_key)
  returning id into inserted_id;

  return inserted_id;
end;
$$;

revoke all on function public.record_notification_delivery_event(text, uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.record_notification_delivery_event(text, uuid)
  to authenticated;

create or replace function public.platform_notification_usage(
  target_start date,
  target_end date
)
returns table (
  period_start date,
  period_end date,
  admin_weekly_digests_sent integer,
  admin_digest_senders integer
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    target_start,
    target_end,
    count(*) filter (where e.notification_key = 'admin_weekly_digest_sent')::integer,
    count(distinct e.actor_id) filter (where e.notification_key = 'admin_weekly_digest_sent')::integer
  from public.notification_delivery_events e
  where e.occurred_at >= target_start::timestamptz
    and e.occurred_at < (target_end + 1)::timestamptz
    and target_end >= target_start
    and private.has_role('platform_admin'::public.app_role, null)
$$;

revoke all on function public.platform_notification_usage(date, date)
  from public, anon, authenticated, service_role;
grant execute on function public.platform_notification_usage(date, date)
  to authenticated;

notify pgrst, 'reload schema';
