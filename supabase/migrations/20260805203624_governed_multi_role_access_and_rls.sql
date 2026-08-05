create schema if not exists private;
revoke all on schema private from public, anon, authenticated;
grant usage on schema private to authenticated;

alter table public.profiles
  add column if not exists email text,
  add column if not exists is_active boolean not null default true;

create unique index if not exists profiles_email_lower_unique
  on public.profiles (lower(email))
  where email is not null;
create index if not exists profiles_school_id_idx on public.profiles (school_id);

create table if not exists public.profile_roles (
  profile_id uuid not null references public.profiles(id) on delete cascade,
  school_id uuid not null references public.schools(id) on delete cascade,
  role public.app_role not null,
  created_at timestamptz not null default now(),
  primary key (profile_id, school_id, role)
);

create index if not exists profile_roles_school_role_idx
  on public.profile_roles (school_id, role, profile_id);

alter table public.profile_roles enable row level security;

create table if not exists private.pilot_access_allowlist (
  email text primary key,
  school_id uuid not null references public.schools(id) on delete cascade,
  display_name text,
  roles public.app_role[] not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint pilot_access_email_lowercase check (email = lower(btrim(email))),
  constraint pilot_access_roles_nonempty check (coalesce(array_length(roles, 1), 0) > 0)
);

revoke all on table private.pilot_access_allowlist from public, anon, authenticated;

create or replace function private.current_school_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select p.school_id
  from public.profiles p
  where p.id = (select auth.uid())
    and p.is_active
$$;

create or replace function private.has_role(
  requested_role public.app_role,
  requested_school_id uuid default null
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.profile_roles pr
    join public.profiles p on p.id = pr.profile_id
    where pr.profile_id = (select auth.uid())
      and p.is_active
      and pr.role = requested_role
      and (requested_school_id is null or pr.school_id = requested_school_id)
  )
$$;

create or replace function private.can_admin_school(target_school_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select private.has_role('platform_admin'::public.app_role, null)
      or private.has_role('school_admin'::public.app_role, target_school_id)
$$;

create or replace function private.can_access_assignment(target_assignment_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.teaching_assignments ta
    where ta.id = target_assignment_id
      and (
        ta.teacher_id = (select auth.uid())
        or private.can_admin_school(ta.school_id)
      )
  )
$$;

revoke all on function private.current_school_id() from public, anon;
revoke all on function private.has_role(public.app_role, uuid) from public, anon;
revoke all on function private.can_admin_school(uuid) from public, anon;
revoke all on function private.can_access_assignment(uuid) from public, anon;
grant execute on function private.current_school_id() to authenticated;
grant execute on function private.has_role(public.app_role, uuid) to authenticated;
grant execute on function private.can_admin_school(uuid) to authenticated;
grant execute on function private.can_access_assignment(uuid) to authenticated;

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
  access_record private.pilot_access_allowlist%rowtype;
  selected_role public.app_role;
begin
  select * into access_record
  from private.pilot_access_allowlist
  where email = lower(btrim(target_email));

  if not found or not access_record.is_active then
    update public.profiles
      set is_active = false,
          updated_at = now()
      where id = target_user_id;
    delete from public.profile_roles where profile_id = target_user_id;
    return;
  end if;

  selected_role := case
    when 'teacher'::public.app_role = any(access_record.roles)
      then 'teacher'::public.app_role
    else access_record.roles[1]
  end;

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
    access_record.school_id,
    coalesce(nullif(btrim(access_record.display_name), ''), nullif(btrim(target_display_name), ''), lower(btrim(target_email))),
    lower(btrim(target_email)),
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
  select target_user_id, access_record.school_id, role_value
  from unnest(access_record.roles) as role_value
  on conflict do nothing;
end;
$$;

revoke all on function private.apply_pilot_access(uuid, text, text) from public, anon, authenticated;

create or replace function private.provision_pilot_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform private.apply_pilot_access(
    new.id,
    coalesce(new.email, ''),
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', new.email, '')
  );
  return new;
end;
$$;

revoke all on function private.provision_pilot_auth_user() from public, anon, authenticated;

drop trigger if exists provision_tpp_pilot_user on auth.users;
create trigger provision_tpp_pilot_user
after insert or update of email, raw_user_meta_data on auth.users
for each row execute function private.provision_pilot_auth_user();

create or replace function private.sync_allowlisted_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  user_record record;
begin
  select u.id, u.email, u.raw_user_meta_data
    into user_record
  from auth.users u
  where lower(u.email) = new.email
  limit 1;

  if found then
    perform private.apply_pilot_access(
      user_record.id,
      user_record.email,
      coalesce(user_record.raw_user_meta_data ->> 'full_name', user_record.raw_user_meta_data ->> 'name', user_record.email)
    );
  end if;
  new.updated_at := now();
  return new;
end;
$$;

revoke all on function private.sync_allowlisted_auth_user() from public, anon, authenticated;

drop trigger if exists sync_tpp_allowlisted_user on private.pilot_access_allowlist;
create trigger sync_tpp_allowlisted_user
before insert or update on private.pilot_access_allowlist
for each row execute function private.sync_allowlisted_auth_user();

alter table public.teaching_assignments
  add column if not exists revision integer not null default 1,
  add column if not exists updated_at timestamptz not null default now();

alter table public.teaching_assignments
  drop constraint if exists teaching_assignments_revision_positive;
alter table public.teaching_assignments
  add constraint teaching_assignments_revision_positive check (revision > 0);

create or replace function private.bump_teaching_assignment_revision()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new is distinct from old then
    if new.revision <> old.revision then
      raise exception 'revision is managed by the database';
    end if;
    new.revision := old.revision + 1;
    new.updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists teaching_assignment_revision_trigger on public.teaching_assignments;
create trigger teaching_assignment_revision_trigger
before update on public.teaching_assignments
for each row execute function private.bump_teaching_assignment_revision();

alter table public.weekly_plan_snapshots
  drop constraint if exists weekly_plan_required_instructional_fields;
alter table public.weekly_plan_snapshots
  add constraint weekly_plan_required_instructional_fields check (
    length(btrim(coalesce(source_data ->> 'literacy_standards', ''))) > 0
    and length(btrim(coalesce(source_data ->> 'act_preparation', ''))) > 0
  );

alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke execute on functions from public, anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke usage, select on sequences from anon, authenticated, service_role;

revoke all on all tables in schema public from anon;
revoke execute on all functions in schema public from public, anon, authenticated;
revoke usage, select on all sequences in schema public from anon;

revoke execute on function public.rls_auto_enable() from public, anon, authenticated;

grant select on table
  public.districts,
  public.schools,
  public.profiles,
  public.profile_roles,
  public.academic_years,
  public.calendar_days,
  public.curricula,
  public.curriculum_units,
  public.lessons,
  public.teaching_assignments,
  public.meeting_patterns,
  public.schedule_exceptions,
  public.scheduled_lessons,
  public.instruction_records,
  public.weekly_plan_snapshots,
  public.generated_documents,
  public.document_templates,
  public.ai_usage_events,
  public.ai_budgets,
  public.audit_events
 to authenticated;

grant insert, update, delete on table
  public.curricula,
  public.curriculum_units,
  public.lessons,
  public.teaching_assignments,
  public.meeting_patterns,
  public.schedule_exceptions,
  public.scheduled_lessons,
  public.instruction_records,
  public.weekly_plan_snapshots,
  public.generated_documents
 to authenticated;

grant insert on table public.ai_usage_events, public.audit_events to authenticated;
grant insert, update, delete on table
  public.academic_years,
  public.calendar_days,
  public.document_templates,
  public.ai_budgets
 to authenticated;

grant select on table
  public.school_admin_usage_summary,
  public.school_ai_cost_summary
 to authenticated;

-- Replace legacy policies with explicit authenticated, role-aware policies.
drop policy if exists profiles_self_read on public.profiles;
drop policy if exists assignments_teacher_access on public.teaching_assignments;
drop policy if exists scheduled_lessons_teacher_read on public.scheduled_lessons;
drop policy if exists instruction_records_teacher_access on public.instruction_records;
drop policy if exists weekly_plans_teacher_access on public.weekly_plan_snapshots;
drop policy if exists generated_documents_teacher_access on public.generated_documents;
drop policy if exists document_templates_school_read on public.document_templates;
drop policy if exists ai_budgets_admin_read on public.ai_budgets;

create policy profiles_read_governed on public.profiles
for select to authenticated
using (
  id = (select auth.uid())
  or private.can_admin_school(school_id)
);

create policy profile_roles_read_governed on public.profile_roles
for select to authenticated
using (
  profile_id = (select auth.uid())
  or private.can_admin_school(school_id)
);

create policy districts_read_governed on public.districts
for select to authenticated
using (
  private.has_role('platform_admin'::public.app_role, null)
  or exists (
    select 1 from public.schools s
    where s.district_id = districts.id
      and s.id = private.current_school_id()
  )
);

create policy schools_read_governed on public.schools
for select to authenticated
using (
  id = private.current_school_id()
  or private.has_role('platform_admin'::public.app_role, null)
);

create policy academic_years_read_governed on public.academic_years
for select to authenticated
using (
  school_id = private.current_school_id()
  or private.has_role('platform_admin'::public.app_role, null)
);
create policy academic_years_admin_write on public.academic_years
for all to authenticated
using (private.can_admin_school(school_id))
with check (private.can_admin_school(school_id));

create policy calendar_days_read_governed on public.calendar_days
for select to authenticated
using (
  exists (
    select 1 from public.academic_years ay
    where ay.id = calendar_days.academic_year_id
      and (ay.school_id = private.current_school_id() or private.can_admin_school(ay.school_id))
  )
);
create policy calendar_days_admin_write on public.calendar_days
for all to authenticated
using (
  exists (
    select 1 from public.academic_years ay
    where ay.id = calendar_days.academic_year_id
      and private.can_admin_school(ay.school_id)
  )
)
with check (
  exists (
    select 1 from public.academic_years ay
    where ay.id = calendar_days.academic_year_id
      and private.can_admin_school(ay.school_id)
  )
);

create policy curricula_read_governed on public.curricula
for select to authenticated
using (
  school_id = private.current_school_id()
  or private.can_admin_school(school_id)
);
create policy curricula_teacher_insert on public.curricula
for insert to authenticated
with check (
  school_id = private.current_school_id()
  and created_by = (select auth.uid())
  and private.has_role('teacher'::public.app_role, school_id)
);
create policy curricula_owner_or_admin_update on public.curricula
for update to authenticated
using (created_by = (select auth.uid()) or private.can_admin_school(school_id))
with check (created_by = (select auth.uid()) or private.can_admin_school(school_id));
create policy curricula_owner_or_admin_delete on public.curricula
for delete to authenticated
using (created_by = (select auth.uid()) or private.can_admin_school(school_id));

create policy curriculum_units_read_governed on public.curriculum_units
for select to authenticated
using (
  exists (
    select 1 from public.curricula c
    where c.id = curriculum_units.curriculum_id
      and (c.school_id = private.current_school_id() or private.can_admin_school(c.school_id))
  )
);
create policy curriculum_units_owner_write on public.curriculum_units
for all to authenticated
using (
  exists (
    select 1 from public.curricula c
    where c.id = curriculum_units.curriculum_id
      and (c.created_by = (select auth.uid()) or private.can_admin_school(c.school_id))
  )
)
with check (
  exists (
    select 1 from public.curricula c
    where c.id = curriculum_units.curriculum_id
      and (c.created_by = (select auth.uid()) or private.can_admin_school(c.school_id))
  )
);

create policy lessons_read_governed on public.lessons
for select to authenticated
using (
  exists (
    select 1
    from public.curriculum_units cu
    join public.curricula c on c.id = cu.curriculum_id
    where cu.id = lessons.unit_id
      and (c.school_id = private.current_school_id() or private.can_admin_school(c.school_id))
  )
);
create policy lessons_owner_write on public.lessons
for all to authenticated
using (
  exists (
    select 1
    from public.curriculum_units cu
    join public.curricula c on c.id = cu.curriculum_id
    where cu.id = lessons.unit_id
      and (c.created_by = (select auth.uid()) or private.can_admin_school(c.school_id))
  )
)
with check (
  exists (
    select 1
    from public.curriculum_units cu
    join public.curricula c on c.id = cu.curriculum_id
    where cu.id = lessons.unit_id
      and (c.created_by = (select auth.uid()) or private.can_admin_school(c.school_id))
  )
);

create policy teaching_assignments_read_governed on public.teaching_assignments
for select to authenticated
using (teacher_id = (select auth.uid()) or private.can_admin_school(school_id));
create policy teaching_assignments_teacher_insert on public.teaching_assignments
for insert to authenticated
with check (
  teacher_id = (select auth.uid())
  and school_id = private.current_school_id()
  and private.has_role('teacher'::public.app_role, school_id)
);
create policy teaching_assignments_owner_update on public.teaching_assignments
for update to authenticated
using (teacher_id = (select auth.uid()))
with check (teacher_id = (select auth.uid()) and school_id = private.current_school_id());
create policy teaching_assignments_owner_delete on public.teaching_assignments
for delete to authenticated
using (teacher_id = (select auth.uid()));

create policy meeting_patterns_read_governed on public.meeting_patterns
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));
create policy meeting_patterns_owner_write on public.meeting_patterns
for all to authenticated
using (
  exists (
    select 1 from public.teaching_assignments ta
    where ta.id = meeting_patterns.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1 from public.teaching_assignments ta
    where ta.id = meeting_patterns.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
);

create policy schedule_exceptions_read_governed on public.schedule_exceptions
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));
create policy schedule_exceptions_owner_write on public.schedule_exceptions
for all to authenticated
using (
  created_by = (select auth.uid())
  and exists (
    select 1 from public.teaching_assignments ta
    where ta.id = schedule_exceptions.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
)
with check (
  created_by = (select auth.uid())
  and exists (
    select 1 from public.teaching_assignments ta
    where ta.id = schedule_exceptions.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
);

create policy scheduled_lessons_read_governed on public.scheduled_lessons
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));
create policy scheduled_lessons_owner_write on public.scheduled_lessons
for all to authenticated
using (
  exists (
    select 1 from public.teaching_assignments ta
    where ta.id = scheduled_lessons.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1 from public.teaching_assignments ta
    where ta.id = scheduled_lessons.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
);

create policy instruction_records_read_governed on public.instruction_records
for select to authenticated
using (
  exists (
    select 1
    from public.scheduled_lessons sl
    where sl.id = instruction_records.scheduled_lesson_id
      and private.can_access_assignment(sl.teaching_assignment_id)
  )
);
create policy instruction_records_owner_write on public.instruction_records
for all to authenticated
using (
  validated_by = (select auth.uid())
  and exists (
    select 1
    from public.scheduled_lessons sl
    join public.teaching_assignments ta on ta.id = sl.teaching_assignment_id
    where sl.id = instruction_records.scheduled_lesson_id
      and ta.teacher_id = (select auth.uid())
  )
)
with check (
  validated_by = (select auth.uid())
  and exists (
    select 1
    from public.scheduled_lessons sl
    join public.teaching_assignments ta on ta.id = sl.teaching_assignment_id
    where sl.id = instruction_records.scheduled_lesson_id
      and ta.teacher_id = (select auth.uid())
  )
);

create policy weekly_plans_read_governed on public.weekly_plan_snapshots
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));
create policy weekly_plans_owner_write on public.weekly_plan_snapshots
for all to authenticated
using (
  exists (
    select 1 from public.teaching_assignments ta
    where ta.id = weekly_plan_snapshots.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
)
with check (
  exists (
    select 1 from public.teaching_assignments ta
    where ta.id = weekly_plan_snapshots.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
  and (updated_by is null or updated_by = (select auth.uid()))
  and (approved_by is null or approved_by = (select auth.uid()))
);

create policy generated_documents_read_governed on public.generated_documents
for select to authenticated
using (
  exists (
    select 1 from public.weekly_plan_snapshots w
    where w.id = generated_documents.weekly_plan_snapshot_id
      and private.can_access_assignment(w.teaching_assignment_id)
  )
);
create policy generated_documents_owner_write on public.generated_documents
for all to authenticated
using (generated_by = (select auth.uid()))
with check (
  generated_by = (select auth.uid())
  and exists (
    select 1
    from public.weekly_plan_snapshots w
    join public.teaching_assignments ta on ta.id = w.teaching_assignment_id
    where w.id = generated_documents.weekly_plan_snapshot_id
      and ta.teacher_id = (select auth.uid())
  )
);

create policy document_templates_read_governed on public.document_templates
for select to authenticated
using (school_id = private.current_school_id() or private.can_admin_school(school_id));
create policy document_templates_admin_write on public.document_templates
for all to authenticated
using (private.can_admin_school(school_id))
with check (private.can_admin_school(school_id));

create policy ai_usage_read_governed on public.ai_usage_events
for select to authenticated
using (teacher_id = (select auth.uid()) or private.can_admin_school(school_id));
create policy ai_usage_teacher_insert on public.ai_usage_events
for insert to authenticated
with check (
  teacher_id = (select auth.uid())
  and school_id = private.current_school_id()
);

create policy ai_budgets_admin_read on public.ai_budgets
for select to authenticated
using (private.can_admin_school(school_id));
create policy ai_budgets_admin_write on public.ai_budgets
for all to authenticated
using (private.can_admin_school(school_id))
with check (private.can_admin_school(school_id));

create policy audit_events_read_governed on public.audit_events
for select to authenticated
using (actor_id = (select auth.uid()) or (school_id is not null and private.can_admin_school(school_id)));
create policy audit_events_actor_insert on public.audit_events
for insert to authenticated
with check (
  actor_id = (select auth.uid())
  and (school_id is null or school_id = private.current_school_id())
);

notify pgrst, 'reload schema';