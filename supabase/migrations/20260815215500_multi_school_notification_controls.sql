-- Multi-school provisioning and school-local Friday notification controls.
-- Adult professional data only. Student data remains prohibited.
-- This migration follows the deferred scheduled-delivery foundation and does not itself enable email.

-- Pilot access is now school-membership based. A professional account may hold governed
-- roles in more than one school while retaining one explicit home school for legacy profile scope.
drop trigger if exists sync_tpp_allowlisted_user on private.pilot_access_allowlist;

alter table private.pilot_access_allowlist
  add column if not exists is_home boolean not null default true;

alter table private.pilot_access_allowlist
  drop constraint if exists pilot_access_allowlist_pkey;

alter table private.pilot_access_allowlist
  add constraint pilot_access_allowlist_pkey primary key (email, school_id);

create unique index if not exists pilot_access_one_active_home_per_email_idx
  on private.pilot_access_allowlist (email)
  where is_active and is_home;

comment on column private.pilot_access_allowlist.is_home is
  'Exactly one active school membership per professional account is designated as the home school by governed provisioning.';

create or replace function private.apply_pilot_access(
  target_user_id uuid,
  target_email text,
  target_display_name text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  normalized_email text := lower(btrim(target_email));
  home_record record;
  selected_role public.app_role;
begin
  select
    a.school_id,
    a.display_name,
    a.roles
  into home_record
  from private.pilot_access_allowlist a
  where a.email = normalized_email
    and a.is_active
  order by a.is_home desc, a.created_at, a.school_id
  limit 1;

  if not found then
    update public.profiles
      set is_active = false,
          updated_at = now()
      where id = target_user_id;
    delete from public.profile_roles where profile_id = target_user_id;
    return;
  end if;

  select case
    when exists (
      select 1
      from private.pilot_access_allowlist a
      where a.email = normalized_email
        and a.is_active
        and 'teacher'::public.app_role = any(a.roles)
    ) then 'teacher'::public.app_role
    else home_record.roles[1]
  end
  into selected_role;

  insert into public.profiles (
    id,
    school_id,
    display_name,
    email,
    role,
    is_active,
    created_at,
    updated_at
  ) values (
    target_user_id,
    home_record.school_id,
    coalesce(
      nullif(btrim(home_record.display_name), ''),
      nullif(btrim(target_display_name), ''),
      normalized_email
    ),
    normalized_email,
    selected_role,
    true,
    now(),
    now()
  )
  on conflict (id) do update set
    school_id = excluded.school_id,
    display_name = excluded.display_name,
    email = excluded.email,
    role = excluded.role,
    is_active = true,
    updated_at = now();

  delete from public.profile_roles where profile_id = target_user_id;
  insert into public.profile_roles (profile_id, school_id, role)
  select distinct
    target_user_id,
    a.school_id,
    role_value
  from private.pilot_access_allowlist a
  cross join lateral unnest(a.roles) as role_value
  where a.email = normalized_email
    and a.is_active
  on conflict do nothing;
end;
$$;

revoke all on function private.apply_pilot_access(uuid, text, text)
  from public, anon, authenticated, service_role;

create or replace function private.sync_allowlisted_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_email text;
  previous_email text;
  user_record record;
begin
  target_email := case when tg_op = 'DELETE' then old.email else new.email end;
  previous_email := case when tg_op = 'UPDATE' then old.email else null end;

  select u.id, u.email, u.raw_user_meta_data
    into user_record
  from auth.users u
  where lower(u.email) = target_email
  limit 1;

  if found then
    perform private.apply_pilot_access(
      user_record.id,
      user_record.email,
      coalesce(
        user_record.raw_user_meta_data ->> 'full_name',
        user_record.raw_user_meta_data ->> 'name',
        user_record.email
      )
    );
  end if;

  if previous_email is not null and previous_email <> target_email then
    select u.id, u.email, u.raw_user_meta_data
      into user_record
    from auth.users u
    where lower(u.email) = previous_email
    limit 1;

    if found then
      perform private.apply_pilot_access(
        user_record.id,
        user_record.email,
        coalesce(
          user_record.raw_user_meta_data ->> 'full_name',
          user_record.raw_user_meta_data ->> 'name',
          user_record.email
        )
      );
    end if;
  end if;

  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke all on function private.sync_allowlisted_auth_user()
  from public, anon, authenticated, service_role;

create trigger sync_tpp_allowlisted_user
after insert or update or delete on private.pilot_access_allowlist
for each row execute function private.sync_allowlisted_auth_user();

-- Every school owns its IANA timezone. Provisioning validates the identifier using the
-- runtime timezone database; this database constraint additionally prevents blank values.
alter table public.schools
  drop constraint if exists schools_timezone_nonempty;
alter table public.schools
  add constraint schools_timezone_nonempty
  check (length(btrim(timezone)) > 0);

comment on column public.schools.timezone is
  'Required IANA timezone used for school-local scheduling and calendar interpretation.';

create table if not exists public.school_notification_settings (
  school_id uuid primary key references public.schools(id) on delete cascade,
  teacher_reminders_enabled boolean not null default false,
  teacher_reminder_local_time time without time zone not null default time '14:00',
  admin_digest_enabled boolean not null default false,
  admin_digest_local_time time without time zone not null default time '15:30',
  updated_at timestamptz not null default now()
);

insert into public.school_notification_settings (school_id)
select s.id
from public.schools s
on conflict (school_id) do nothing;

alter table public.school_notification_settings enable row level security;
revoke all on table public.school_notification_settings
  from public, anon, authenticated, service_role;

comment on table public.school_notification_settings is
  'School-local professional notification controls. New schools default to all automated notifications disabled.';

-- The original delivery key did not distinguish the same professional recipient serving
-- more than one school. Replace it with an explicitly school-scoped at-most-once key.
do $$
declare
  constraint_record record;
begin
  for constraint_record in
    select conname
    from pg_constraint
    where conrelid = 'public.scheduled_notification_deliveries'::regclass
      and contype = 'u'
  loop
    execute format(
      'alter table public.scheduled_notification_deliveries drop constraint %I',
      constraint_record.conname
    );
  end loop;
end;
$$;

alter table public.scheduled_notification_deliveries
  add constraint scheduled_notification_deliveries_school_recipient_week_key
  unique (notification_key, school_id, recipient_profile_id, week_start);

-- Return only schools whose local Friday clock is currently inside the approved 15-minute
-- dispatch window. The worker then performs an explicit school-scoped claim for each result.
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
        and lc.local_now >= date_trunc('day', lc.local_now) + lc.teacher_reminder_local_time
        and lc.local_now < date_trunc('day', lc.local_now) + lc.teacher_reminder_local_time + interval '15 minutes'
      )
      or
      (
        target_mode = 'admin'
        and lc.admin_digest_enabled
        and lc.local_now >= date_trunc('day', lc.local_now) + lc.admin_digest_local_time
        and lc.local_now < date_trunc('day', lc.local_now) + lc.admin_digest_local_time + interval '15 minutes'
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

-- Replace the global candidate RPCs with explicit school-scoped claims.
drop function if exists public.claim_teacher_friday_reminder_candidates(date);
drop function if exists public.claim_scheduled_admin_weekly_digest_candidates(date);

create function public.claim_teacher_friday_reminder_candidates(
  target_school_id uuid,
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
  if target_school_id is null or target_week_start is null
     or extract(isodow from target_week_start) <> 1 then
    raise exception 'Teacher reminder scope is invalid' using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.school_notification_settings ns
    where ns.school_id = target_school_id
      and ns.teacher_reminders_enabled
  ) then
    raise exception 'Teacher reminders are not enabled for this school' using errcode = '42501';
  end if;

  return query
  with needing as (
    select f.*
    from private.friday_assignment_status(target_week_start) f
    where f.school_id = target_school_id
      and (
        (f.current_week_required and not f.current_packet_submitted)
        or (f.next_week_required and not f.next_plan_submitted)
      )
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
    on conflict (
      notification_key,
      school_id,
      recipient_profile_id,
      week_start
    ) do nothing
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
  order by g.recipient_profile_id;
end;
$$;

revoke all on function public.claim_teacher_friday_reminder_candidates(uuid, date)
  from public, anon, authenticated, service_role;
grant execute on function public.claim_teacher_friday_reminder_candidates(uuid, date)
  to service_role;

comment on function public.claim_teacher_friday_reminder_candidates(uuid, date) is
  'Service-role-only, explicitly school-scoped teacher reminder manifest. Course names and missing-item flags remain transient.';

create function public.claim_scheduled_admin_weekly_digest_candidates(
  target_school_id uuid,
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
  if target_school_id is null or target_week_start is null
     or extract(isodow from target_week_start) <> 1 then
    raise exception 'Scheduled digest scope is invalid' using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.school_notification_settings ns
    where ns.school_id = target_school_id
      and ns.admin_digest_enabled
  ) then
    raise exception 'Administrator digest is not enabled for this school' using errcode = '42501';
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
    where pr.school_id = target_school_id
      and pr.role = 'school_admin'::public.app_role
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
    where f.school_id = target_school_id
    group by f.school_id, f.teacher_id
  ),
  school_metrics as (
    select
      target_school_id as school_id,
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
    from teacher_rollup t
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
    cross join school_metrics m
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
    on conflict (
      notification_key,
      school_id,
      recipient_profile_id,
      week_start
    ) do nothing
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
  order by e.recipient_profile_id;
end;
$$;

revoke all on function public.claim_scheduled_admin_weekly_digest_candidates(uuid, date)
  from public, anon, authenticated, service_role;
grant execute on function public.claim_scheduled_admin_weekly_digest_candidates(uuid, date)
  to service_role;

comment on function public.claim_scheduled_admin_weekly_digest_candidates(uuid, date) is
  'Service-role-only, explicitly school-scoped administrator digest manifest with aggregate professional submission counts only.';

notify pgrst, 'reload schema';
