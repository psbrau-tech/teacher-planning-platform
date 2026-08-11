-- Gate E: distinguish authoritative standards text from course-listing provenance.
-- Alabama Course of Study sources provide primary standards, CTE Program Guides enumerate
-- state courses/codes, and issuer curricula such as Army JROTC may provide supplemental standards.

alter table public.standard_sources
  add column if not exists source_kind text not null default 'course_of_study',
  add column if not exists provides_standard_entries boolean not null default true;

alter table public.standard_sources
  add constraint standard_sources_source_kind check (
    source_kind in (
      'course_of_study',
      'program_guide',
      'supplemental_curriculum',
      'reference'
    )
  ),
  add constraint standard_sources_program_guide_no_standard_entries check (
    source_kind <> 'program_guide' or not provides_standard_entries
  );

update public.standard_sources
set source_kind = 'supplemental_curriculum',
    provides_standard_entries = true
where source_key = 'army_jrotc_v12';

update public.standard_sources
set source_kind = 'course_of_study',
    provides_standard_entries = true
where authority = 'Alabama State Department of Education'
  and family in ('alabama_academic', 'alabama_cte');

-- The original relationship enum predates course-listing-only sources.
alter table public.standard_catalog_course_sources
  drop constraint if exists standard_catalog_course_source_relationship;
alter table public.standard_catalog_course_sources
  add constraint standard_catalog_course_source_relationship check (
    relationship in ('primary', 'course_listing', 'supplemental_authority')
  );

create or replace function private.sync_standard_course_to_catalog()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  source_category_key text;
  source_category_name text;
  source_category_type text;
  source_kind text;
  source_provides_entries boolean;
  canonical_category_id uuid;
  canonical_course_id uuid;
  source_relationship text;
  source_priority integer;
begin
  select
    src.catalog_category_key,
    src.catalog_category_name,
    src.catalog_category_type,
    src.source_kind,
    src.provides_standard_entries
  into
    source_category_key,
    source_category_name,
    source_category_type,
    source_kind,
    source_provides_entries
  from public.standard_sources src
  where src.id = new.source_id;

  -- Pending catalog discovery may create source metadata before its category is reviewed.
  if source_category_key is null
     or source_category_name is null
     or source_category_type is null then
    return new;
  end if;

  source_relationship := case
    when source_kind = 'program_guide' then 'course_listing'
    when source_kind = 'supplemental_curriculum' then 'supplemental_authority'
    when source_kind = 'course_of_study' and source_provides_entries then 'primary'
    else 'course_listing'
  end;

  source_priority := case source_relationship
    when 'course_listing' then 5
    when 'primary' then 10
    else 50
  end;

  insert into public.standard_catalog_categories (
    category_key,
    display_name,
    category_type,
    is_active
  ) values (
    source_category_key,
    source_category_name,
    source_category_type,
    true
  )
  on conflict (category_key) do update set
    display_name = excluded.display_name,
    category_type = excluded.category_type,
    updated_at = now()
  returning id into canonical_category_id;

  insert into public.standard_catalog_courses (
    category_id,
    course_key,
    display_name,
    source_course_code,
    grade_band,
    is_active
  ) values (
    canonical_category_id,
    new.course_key,
    new.display_name,
    new.source_course_code,
    new.grade_band,
    true
  )
  on conflict (category_id, course_key) do update set
    display_name = case
      when source_relationship = 'supplemental_authority'
        then public.standard_catalog_courses.display_name
      else excluded.display_name
    end,
    source_course_code = case
      when source_relationship = 'supplemental_authority'
        then coalesce(
          public.standard_catalog_courses.source_course_code,
          excluded.source_course_code
        )
      else coalesce(
        excluded.source_course_code,
        public.standard_catalog_courses.source_course_code
      )
    end,
    grade_band = case
      when source_relationship = 'supplemental_authority'
        then coalesce(public.standard_catalog_courses.grade_band, excluded.grade_band)
      else coalesce(excluded.grade_band, public.standard_catalog_courses.grade_band)
    end,
    is_active = true,
    updated_at = now()
  returning id into canonical_course_id;

  insert into public.standard_catalog_course_sources (
    catalog_course_id,
    source_course_id,
    relationship,
    priority
  ) values (
    canonical_course_id,
    new.id,
    source_relationship,
    source_priority
  )
  on conflict (catalog_course_id, source_course_id) do update set
    relationship = excluded.relationship,
    priority = excluded.priority;

  return new;
end;
$$;

-- A course-listing source may establish course identity/provenance but never make entries
-- selectable as authoritative weekly standards.
drop policy if exists standard_entries_read_catalog on public.standard_entries;
create policy standard_entries_read_catalog
on public.standard_entries
for select to authenticated
using (
  exists (
    select 1
    from public.standard_snapshots ss
    join public.standard_catalog_course_sources sccs
      on sccs.source_course_id = standard_entries.course_id
    join public.standard_catalog_courses scc on scc.id = sccs.catalog_course_id
    join public.standard_catalog_categories cat on cat.id = scc.category_id
    join public.standard_courses sc on sc.id = standard_entries.course_id
    join public.standard_sources src on src.id = sc.source_id
    where ss.id = standard_entries.snapshot_id
      and (
        (
          ss.status in ('approved', 'superseded')
          and sccs.relationship in ('primary', 'supplemental_authority')
          and src.provides_standard_entries
          and scc.is_active
          and cat.is_active
        )
        or private.has_role('platform_admin'::public.app_role, null)
      )
  )
);

-- Weekly selection remains limited to entry-producing source roles.
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
  join public.standard_courses sc on sc.id = se.course_id
  join public.standard_sources src on src.id = sc.source_id
  join public.standard_catalog_course_sources sccs
    on sccs.source_course_id = se.course_id
  where se.id = any(target_entry_ids)
    and sccs.catalog_course_id = mapped_catalog_course_id
    and sccs.relationship in ('primary', 'supplemental_authority')
    and src.provides_standard_entries
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
