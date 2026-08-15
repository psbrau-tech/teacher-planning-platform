-- Harden school-local notification scheduling after the multi-school control foundation.
-- Delivery remains disabled until the separately governed SES/scheduler activation.

alter table public.school_notification_settings
  drop constraint if exists school_notification_teacher_quarter_hour,
  drop constraint if exists school_notification_admin_quarter_hour;

alter table public.school_notification_settings
  add constraint school_notification_teacher_quarter_hour check (
    extract(second from teacher_reminder_local_time) = 0
    and mod(extract(minute from teacher_reminder_local_time)::integer, 15) = 0
  ),
  add constraint school_notification_admin_quarter_hour check (
    extract(second from admin_digest_local_time) = 0
    and mod(extract(minute from admin_digest_local_time)::integer, 15) = 0
  );

create or replace function public.scheduled_notification_school_windows(
  target_mode text,
  target_now timestamptz
)
returns table (
  school_id uuid,
  timezone text,
  week_start date
)
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if coalesce((select auth.role())::text, '') <> 'service_role' then
    raise exception 'Scheduled notification worker role is required' using errcode = '42501';
  end if;
  if target_mode not in ('teacher', 'admin') or target_now is null then
    raise exception 'Scheduled notification dispatch inputs are invalid' using errcode = '22023';
  end if;

  return query
  with local_clock as (
    select
      s.id as school_id,
      s.timezone,
      ns.teacher_reminders_enabled,
      ns.teacher_reminder_local_time,
      ns.admin_digest_enabled,
      ns.admin_digest_local_time,
      target_now at time zone s.timezone as local_now
    from public.schools s
    join public.school_notification_settings ns on ns.school_id = s.id
  )
  select
    lc.school_id,
    lc.timezone,
    (
      lc.local_now::date
      - ((extract(isodow from lc.local_now)::integer - 1) * interval '1 day')
    )::date as week_start
  from local_clock lc
  where extract(isodow from lc.local_now) = 5
    and (
      (
        target_mode = 'teacher'
        and lc.teacher_reminders_enabled
        and lc.local_now >= lc.local_now::date + lc.teacher_reminder_local_time
        and lc.local_now < lc.local_now::date + lc.teacher_reminder_local_time + interval '15 minutes'
      )
      or
      (
        target_mode = 'admin'
        and lc.admin_digest_enabled
        and lc.local_now >= lc.local_now::date + lc.admin_digest_local_time
        and lc.local_now < lc.local_now::date + lc.admin_digest_local_time + interval '15 minutes'
      )
    )
  order by lc.school_id;
end;
$$;

revoke all on function public.scheduled_notification_school_windows(text, timestamptz)
  from public, anon, authenticated, service_role;
grant execute on function public.scheduled_notification_school_windows(text, timestamptz)
  to service_role;

comment on function public.scheduled_notification_school_windows(text, timestamptz) is
  'Service-role-only dispatcher for enabled schools at their configured local Friday send time. IANA school timezones provide DST-safe local scheduling.';

notify pgrst, 'reload schema';
