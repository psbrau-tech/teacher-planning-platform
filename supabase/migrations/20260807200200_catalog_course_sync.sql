-- Gate E: automatically project deterministic source-specific parser output into the
-- canonical teacher-facing standards catalog.

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
  source_authority text;
  canonical_category_id uuid;
  canonical_course_id uuid;
  source_relationship text;
begin
  select
    src.catalog_category_key,
    src.catalog_category_name,
    src.catalog_category_type,
    src.authority
  into
    source_category_key,
    source_category_name,
    source_category_type,
    source_authority
  from public.standard_sources src
  where src.id = new.source_id;

  -- Pending catalog discovery may create source metadata before its category is reviewed.
  -- Such a source is not projected until the governed category metadata is present.
  if source_category_key is null
     or source_category_name is null
     or source_category_type is null then
    return new;
  end if;

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
    display_name = excluded.display_name,
    source_course_code = coalesce(
      excluded.source_course_code,
      public.standard_catalog_courses.source_course_code
    ),
    grade_band = coalesce(
      excluded.grade_band,
      public.standard_catalog_courses.grade_band
    ),
    is_active = true,
    updated_at = now()
  returning id into canonical_course_id;

  source_relationship := case
    when source_authority = 'Alabama State Department of Education' then 'primary'
    else 'supplemental_authority'
  end;

  insert into public.standard_catalog_course_sources (
    catalog_course_id,
    source_course_id,
    relationship,
    priority
  ) values (
    canonical_course_id,
    new.id,
    source_relationship,
    case when source_relationship = 'primary' then 10 else 50 end
  )
  on conflict (catalog_course_id, source_course_id) do update set
    relationship = excluded.relationship,
    priority = excluded.priority;

  return new;
end;
$$;

drop trigger if exists standard_course_catalog_sync_trigger on public.standard_courses;
create trigger standard_course_catalog_sync_trigger
after insert or update of
  source_id,
  course_key,
  display_name,
  source_course_code,
  grade_band
on public.standard_courses
for each row execute function private.sync_standard_course_to_catalog();

-- The comprehensive catalog replaces the former small pilot allow-list. Source-specific
-- records are readable when they participate in an active canonical catalog course.
drop policy if exists standard_courses_read_pilot on public.standard_courses;
create policy standard_courses_read_catalog
on public.standard_courses
for select to authenticated
using (
  exists (
    select 1
    from public.standard_catalog_course_sources sccs
    join public.standard_catalog_courses scc on scc.id = sccs.catalog_course_id
    join public.standard_catalog_categories cat on cat.id = scc.category_id
    where sccs.source_course_id = standard_courses.id
      and scc.is_active
      and cat.is_active
  )
  or private.has_role('platform_admin'::public.app_role, null)
);

drop policy if exists standard_entries_read_governed on public.standard_entries;
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
    where ss.id = standard_entries.snapshot_id
      and (
        (
          ss.status in ('approved', 'superseded')
          and scc.is_active
          and cat.is_active
        )
        or private.has_role('platform_admin'::public.app_role, null)
      )
  )
);

notify pgrst, 'reload schema';
