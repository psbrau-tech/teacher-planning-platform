-- Gate E: canonical Alabama catalog layer and teacher-controlled course mapping.
--
-- Source-specific standard_courses remain the deterministic parser output. The canonical
-- catalog above them is what teachers select: Subject / Career Cluster -> Grade / Course.
-- A canonical course may point to multiple source-specific course records so Alabama
-- provenance can coexist with a supplemental authoritative issuer such as Army Cadet Command.

create table public.standard_catalog_categories (
  id uuid primary key default gen_random_uuid(),
  category_key text not null unique,
  display_name text not null,
  category_type text not null,
  sort_order integer not null default 100,
  is_active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint standard_catalog_category_type check (
    category_type in ('academic_subject', 'career_cluster', 'general')
  ),
  constraint standard_catalog_category_name_nonempty check (
    length(btrim(display_name)) > 0
  )
);

create table public.standard_catalog_courses (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null
    references public.standard_catalog_categories(id) on delete restrict,
  course_key text not null,
  display_name text not null,
  source_course_code text,
  grade_band text,
  is_active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (category_id, course_key),
  constraint standard_catalog_course_name_nonempty check (
    length(btrim(display_name)) > 0
  )
);

create table public.standard_catalog_course_sources (
  catalog_course_id uuid not null
    references public.standard_catalog_courses(id) on delete cascade,
  source_course_id uuid not null
    references public.standard_courses(id) on delete cascade,
  relationship text not null default 'primary',
  priority integer not null default 100,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (catalog_course_id, source_course_id),
  constraint standard_catalog_course_source_relationship check (
    relationship in ('primary', 'supplemental_authority')
  ),
  constraint standard_catalog_course_source_priority_positive check (priority > 0)
);

create index standard_catalog_courses_category_name_idx
  on public.standard_catalog_courses (category_id, display_name);
create index standard_catalog_course_sources_source_idx
  on public.standard_catalog_course_sources (source_course_id, relationship, priority);

alter table public.standard_sources
  add column if not exists catalog_category_key text,
  add column if not exists catalog_category_name text,
  add column if not exists catalog_category_type text,
  add column if not exists discovery_status text not null default 'approved';

alter table public.standard_sources
  add constraint standard_sources_catalog_category_type check (
    catalog_category_type is null
    or catalog_category_type in ('academic_subject', 'career_cluster', 'general')
  ),
  add constraint standard_sources_discovery_status check (
    discovery_status in ('pending', 'approved', 'retired')
  );

-- Existing three source fixtures predate catalog-driven discovery. Assign their canonical
-- categories without making those fixtures the boundary of the catalog.
update public.standard_sources
set catalog_category_key = 'english_language_arts',
    catalog_category_name = 'English Language Arts',
    catalog_category_type = 'academic_subject'
where source_key = 'alabama_ela_2021';

update public.standard_sources
set catalog_category_key = 'business_management_administration',
    catalog_category_name = 'Business Management & Administration',
    catalog_category_type = 'career_cluster'
where source_key = 'alabama_bma_2021';

update public.standard_sources
set catalog_category_key = 'government_public_administration',
    catalog_category_name = 'Government & Public Administration',
    catalog_category_type = 'career_cluster'
where source_key = 'army_jrotc_v12';

-- The original assignment mapping stored a source-specific course. Keep the legacy columns
-- nullable for migration compatibility, but make canonical catalog_course_id the runtime contract.
drop trigger if exists assignment_standard_course_source_trigger
  on public.assignment_standard_courses;
drop function if exists private.enforce_assignment_standard_course_source();

drop policy if exists assignment_standard_courses_owner_write
  on public.assignment_standard_courses;
drop policy if exists assignment_standard_courses_platform_admin_write
  on public.assignment_standard_courses;

alter table public.assignment_standard_courses
  alter column source_id drop not null,
  alter column course_id drop not null,
  add column if not exists catalog_course_id uuid
    references public.standard_catalog_courses(id) on delete restrict;

create index assignment_standard_courses_catalog_idx
  on public.assignment_standard_courses (catalog_course_id);

create table public.assignment_standard_course_history (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null
    references public.teaching_assignments(id) on delete cascade,
  previous_catalog_course_id uuid
    references public.standard_catalog_courses(id) on delete restrict,
  new_catalog_course_id uuid not null
    references public.standard_catalog_courses(id) on delete restrict,
  changed_by uuid not null references public.profiles(id),
  changed_at timestamptz not null default now(),
  warning_required boolean not null default false,
  open_selection_count_cleared integer not null default 0,
  validated_week_count_preserved integer not null default 0,
  reason text not null default 'Teacher corrected standards-course mapping',
  metadata jsonb not null default '{}'::jsonb,
  constraint assignment_standard_history_cleared_nonnegative check (
    open_selection_count_cleared >= 0
  ),
  constraint assignment_standard_history_validated_nonnegative check (
    validated_week_count_preserved >= 0
  )
);

create index assignment_standard_course_history_assignment_idx
  on public.assignment_standard_course_history (teaching_assignment_id, changed_at desc);

alter table public.standard_catalog_categories enable row level security;
alter table public.standard_catalog_courses enable row level security;
alter table public.standard_catalog_course_sources enable row level security;
alter table public.assignment_standard_course_history enable row level security;

revoke all on table
  public.standard_catalog_categories,
  public.standard_catalog_courses,
  public.standard_catalog_course_sources,
  public.assignment_standard_course_history
from public, anon, authenticated, service_role;

grant select on table
  public.standard_catalog_categories,
  public.standard_catalog_courses,
  public.standard_catalog_course_sources,
  public.assignment_standard_course_history
  to authenticated;

grant select, insert, update, delete on table
  public.standard_catalog_categories,
  public.standard_catalog_courses,
  public.standard_catalog_course_sources
  to service_role;

create policy standard_catalog_categories_read_active
on public.standard_catalog_categories
for select to authenticated
using (
  is_active
  or private.has_role('platform_admin'::public.app_role, null)
);

create policy standard_catalog_courses_read_active
on public.standard_catalog_courses
for select to authenticated
using (
  is_active
  or private.has_role('platform_admin'::public.app_role, null)
);

create policy standard_catalog_course_sources_read_governed
on public.standard_catalog_course_sources
for select to authenticated
using (
  exists (
    select 1
    from public.standard_catalog_courses scc
    where scc.id = standard_catalog_course_sources.catalog_course_id
      and (
        scc.is_active
        or private.has_role('platform_admin'::public.app_role, null)
      )
  )
);

create policy assignment_standard_course_history_read_governed
on public.assignment_standard_course_history
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));

-- Teachers own the mapping for their own teaching assignments. Direct table writes remain
-- disabled; the RPC below enforces the warning and historical-provenance contract atomically.
revoke insert, update, delete on table public.assignment_standard_courses from authenticated;

create or replace function public.set_assignment_standard_catalog_course(
  target_assignment_id uuid,
  target_catalog_course_id uuid,
  confirm_existing_plans boolean default false
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
  assignment_teacher_id uuid;
  old_catalog_course_id uuid;
  plan_count integer := 0;
  validated_count integer := 0;
  cleared_count integer := 0;
  warning_required boolean := false;
begin
  if actor_id is null
     or not private.has_role('teacher'::public.app_role, null) then
    raise exception 'teacher role is required';
  end if;

  select ta.teacher_id
    into assignment_teacher_id
  from public.teaching_assignments ta
  where ta.id = target_assignment_id;

  if assignment_teacher_id is null or assignment_teacher_id <> actor_id then
    raise exception 'teachers may map only their own teaching assignments';
  end if;

  if not exists (
    select 1
    from public.standard_catalog_courses scc
    join public.standard_catalog_categories cat on cat.id = scc.category_id
    where scc.id = target_catalog_course_id
      and scc.is_active
      and cat.is_active
  ) then
    raise exception 'standards catalog course is unavailable';
  end if;

  select asc_map.catalog_course_id
    into old_catalog_course_id
  from public.assignment_standard_courses asc_map
  where asc_map.teaching_assignment_id = target_assignment_id
  for update;

  if old_catalog_course_id = target_catalog_course_id then
    return jsonb_build_object(
      'changed', false,
      'warning_required', false,
      'open_selection_count_cleared', 0,
      'validated_week_count_preserved', 0,
      'catalog_course_id', target_catalog_course_id
    );
  end if;

  select count(*) into plan_count
  from public.weekly_plan_snapshots wps
  where wps.teaching_assignment_id = target_assignment_id;

  warning_required := old_catalog_course_id is not null and plan_count > 0;
  if warning_required and not confirm_existing_plans then
    raise exception 'standards mapping change requires explicit confirmation because weekly planning exists';
  end if;

  select count(*) into validated_count
  from public.friday_validation_snapshots fvs
  where fvs.teaching_assignment_id = target_assignment_id;

  -- Preserve validated history exactly. Clear selections only from weeks that have not been
  -- finalized through Friday validation; narrative planning content itself is not deleted.
  with removed as (
    delete from public.weekly_standard_selections wss
    where wss.teaching_assignment_id = target_assignment_id
      and not exists (
        select 1
        from public.friday_validation_snapshots fvs
        where fvs.teaching_assignment_id = wss.teaching_assignment_id
          and fvs.week_start = wss.week_start
      )
    returning 1
  )
  select count(*) into cleared_count from removed;

  insert into public.assignment_standard_courses (
    teaching_assignment_id,
    source_id,
    course_id,
    catalog_course_id,
    mapped_by,
    mapped_at
  ) values (
    target_assignment_id,
    null,
    null,
    target_catalog_course_id,
    actor_id,
    now()
  )
  on conflict (teaching_assignment_id) do update set
    source_id = null,
    course_id = null,
    catalog_course_id = excluded.catalog_course_id,
    mapped_by = excluded.mapped_by,
    mapped_at = excluded.mapped_at;

  insert into public.assignment_standard_course_history (
    teaching_assignment_id,
    previous_catalog_course_id,
    new_catalog_course_id,
    changed_by,
    warning_required,
    open_selection_count_cleared,
    validated_week_count_preserved
  ) values (
    target_assignment_id,
    old_catalog_course_id,
    target_catalog_course_id,
    actor_id,
    warning_required,
    cleared_count,
    validated_count
  );

  insert into public.audit_events (
    actor_id,
    entity_type,
    entity_id,
    action,
    before_data,
    after_data,
    reason
  ) values (
    actor_id,
    'teaching_assignment',
    target_assignment_id,
    'set_assignment_standard_catalog_course',
    jsonb_build_object('catalog_course_id', old_catalog_course_id),
    jsonb_build_object(
      'catalog_course_id', target_catalog_course_id,
      'open_selection_count_cleared', cleared_count,
      'validated_week_count_preserved', validated_count
    ),
    'Teacher selected or corrected Subject / Career Cluster and Grade / Course mapping'
  );

  return jsonb_build_object(
    'changed', true,
    'warning_required', warning_required,
    'open_selection_count_cleared', cleared_count,
    'validated_week_count_preserved', validated_count,
    'catalog_course_id', target_catalog_course_id
  );
end;
$$;

revoke all on function public.set_assignment_standard_catalog_course(uuid, uuid, boolean)
  from public, anon, authenticated, service_role;
grant execute on function public.set_assignment_standard_catalog_course(uuid, uuid, boolean)
  to authenticated;

-- Weekly selection remains exact-entry based. Valid entries must come from an approved
-- snapshot of a source-specific course linked to the assignment's canonical catalog course.
create or replace function public.replace_weekly_standard_selections(
  target_assignment_id uuid,
  target_week_start date,
  target_entry_ids uuid[]
)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  actor_id uuid := (select auth.uid());
  mapped_catalog_course_id uuid;
  supplied_count integer;
  valid_count integer;
  inserted_count integer;
begin
  if actor_id is null
     or not private.has_role('teacher'::public.app_role, null) then
    raise exception 'teacher role is required';
  end if;

  if not exists (
    select 1 from public.teaching_assignments ta
    where ta.id = target_assignment_id
      and ta.teacher_id = actor_id
  ) then
    raise exception 'teaching assignment access denied';
  end if;

  if target_entry_ids is null then
    target_entry_ids := '{}'::uuid[];
  end if;

  select count(distinct entry_id)
    into supplied_count
  from unnest(target_entry_ids) as selected(entry_id);

  if supplied_count > 20 then
    raise exception 'no more than 20 standards may be selected for one week';
  end if;

  select asc_map.catalog_course_id
    into mapped_catalog_course_id
  from public.assignment_standard_courses asc_map
  where asc_map.teaching_assignment_id = target_assignment_id;

  if mapped_catalog_course_id is null then
    raise exception 'teaching assignment has no standards-course mapping';
  end if;

  select count(distinct se.id)
    into valid_count
  from public.standard_entries se
  join public.standard_snapshots ss on ss.id = se.snapshot_id
  join public.standard_catalog_course_sources sccs
    on sccs.source_course_id = se.course_id
  where se.id = any(target_entry_ids)
    and sccs.catalog_course_id = mapped_catalog_course_id
    and sccs.relationship in ('primary', 'supplemental_authority')
    and ss.status = 'approved';

  if valid_count <> supplied_count then
    raise exception 'one or more selected standards are not approved for this assignment';
  end if;

  delete from public.weekly_standard_selections
  where teaching_assignment_id = target_assignment_id
    and week_start = target_week_start;

  insert into public.weekly_standard_selections (
    teaching_assignment_id,
    week_start,
    standard_entry_id,
    selected_by
  )
  select
    target_assignment_id,
    target_week_start,
    selected.entry_id,
    actor_id
  from (
    select distinct entry_id
    from unnest(target_entry_ids) as entries(entry_id)
  ) as selected;

  get diagnostics inserted_count = row_count;

  insert into public.audit_events (
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data,
    reason
  ) values (
    actor_id,
    'teaching_assignment',
    target_assignment_id,
    'replace_weekly_standard_selections',
    jsonb_build_object(
      'week_start', target_week_start,
      'selection_count', inserted_count,
      'standard_entry_ids', target_entry_ids,
      'catalog_course_id', mapped_catalog_course_id
    ),
    'Teacher updated weekly authoritative standards selection'
  );

  return inserted_count;
end;
$$;

revoke all on function public.replace_weekly_standard_selections(uuid, date, uuid[])
  from public, anon, authenticated, service_role;
grant execute on function public.replace_weekly_standard_selections(uuid, date, uuid[])
  to authenticated;

notify pgrst, 'reload schema';
