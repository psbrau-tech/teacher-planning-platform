-- Gate E: support Alabama Alternate Achievement Standards as a distinct governed catalog family.
--
-- The AAS discovery code intentionally emits a distinct source kind and category type. The
-- original catalog schema predates that family, so extend only the governed enums and approval
-- projection needed to stage and eventually activate reviewed AAS snapshots. No snapshot is
-- approved or activated by this migration.

begin;

alter table public.standard_catalog_discovery_items
  drop constraint if exists standard_catalog_discovery_item_category_type;
alter table public.standard_catalog_discovery_items
  add constraint standard_catalog_discovery_item_category_type check (
    category_type is null
    or category_type in (
      'academic_subject',
      'alternate_achievement_subject',
      'career_cluster',
      'general'
    )
  );

alter table public.standard_sources
  drop constraint if exists standard_sources_catalog_category_type;
alter table public.standard_sources
  add constraint standard_sources_catalog_category_type check (
    catalog_category_type is null
    or catalog_category_type in (
      'academic_subject',
      'alternate_achievement_subject',
      'career_cluster',
      'general'
    )
  );

alter table public.standard_sources
  drop constraint if exists standard_sources_source_kind;
alter table public.standard_sources
  add constraint standard_sources_source_kind check (
    source_kind in (
      'course_of_study',
      'alternate_achievement_standards',
      'program_guide',
      'supplemental_curriculum',
      'reference'
    )
  );

alter table public.standard_catalog_categories
  drop constraint if exists standard_catalog_category_type;
alter table public.standard_catalog_categories
  add constraint standard_catalog_category_type check (
    category_type in (
      'academic_subject',
      'alternate_achievement_subject',
      'career_cluster',
      'general'
    )
  );

-- If a catalog discovery run wrote its run header but the item batch failed, preserve the run
-- as audit evidence but correct its status so it cannot be mistaken for a complete reconciliation.
update public.standard_catalog_discovery_runs r
set status = 'error',
    error_summary = coalesce(
      r.error_summary,
      'Catalog discovery item evidence was not recorded; reconciliation did not complete'
    ),
    metadata = r.metadata || jsonb_build_object(
      'audit_repair', 'orphaned_catalog_run_without_items',
      'audit_repair_migration', '20260810232500'
    )
where r.status = 'completed'
  and r.discovered_source_count > 0
  and not exists (
    select 1
    from public.standard_catalog_discovery_items i
    where i.run_id = r.id
  );

-- Approval-time projection remains the only path that makes a staged source teacher-visible.
-- AAS sources provide authoritative standards entries and therefore project as primary sources,
-- but into their own alternate-achievement categories rather than replacing general standards.
create or replace function private.sync_approved_standard_source_to_catalog(
  target_source_id uuid,
  target_snapshot_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  src record;
  membership record;
  canonical_category_id uuid;
  canonical_course_id uuid;
  source_relationship text;
  source_priority integer;
begin
  select
    id,
    catalog_category_key,
    catalog_category_name,
    catalog_category_type,
    source_kind,
    provides_standard_entries
  into src
  from public.standard_sources
  where id = target_source_id;

  if src.id is null then
    raise exception 'standards source not found';
  end if;

  if src.catalog_category_key is null
     or src.catalog_category_name is null
     or src.catalog_category_type is null then
    raise exception 'approved standards source is missing catalog category metadata';
  end if;

  if not exists (
    select 1
    from public.standard_snapshots ss
    where ss.id = target_snapshot_id
      and ss.source_id = target_source_id
      and ss.status = 'approved'
  ) then
    raise exception 'catalog projection requires an approved snapshot for this source';
  end if;

  source_relationship := case
    when src.source_kind = 'program_guide' then 'course_listing'
    when src.source_kind = 'supplemental_curriculum' then 'supplemental_authority'
    when src.source_kind in ('course_of_study', 'alternate_achievement_standards')
         and src.provides_standard_entries then 'primary'
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
    src.catalog_category_key,
    src.catalog_category_name,
    src.catalog_category_type,
    true
  )
  on conflict (category_key) do update set
    display_name = excluded.display_name,
    category_type = excluded.category_type,
    is_active = true,
    updated_at = now()
  returning id into canonical_category_id;

  delete from public.standard_catalog_course_sources sccs
  using public.standard_courses sc
  where sccs.source_course_id = sc.id
    and sc.source_id = target_source_id
    and not exists (
      select 1
      from public.standard_snapshot_courses ssc
      where ssc.snapshot_id = target_snapshot_id
        and ssc.course_id = sc.id
    );

  for membership in
    select
      ssc.course_id,
      sc.course_key,
      ssc.display_name,
      ssc.source_course_code,
      ssc.grade_band
    from public.standard_snapshot_courses ssc
    join public.standard_courses sc on sc.id = ssc.course_id
    where ssc.snapshot_id = target_snapshot_id
      and sc.source_id = target_source_id
    order by ssc.sequence
  loop
    insert into public.standard_catalog_courses (
      category_id,
      course_key,
      display_name,
      source_course_code,
      grade_band,
      is_active
    ) values (
      canonical_category_id,
      membership.course_key,
      membership.display_name,
      membership.source_course_code,
      membership.grade_band,
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
      membership.course_id,
      source_relationship,
      source_priority
    )
    on conflict (catalog_course_id, source_course_id) do update set
      relationship = excluded.relationship,
      priority = excluded.priority;
  end loop;

  update public.standard_catalog_courses scc
  set is_active = false,
      updated_at = now()
  where scc.category_id = canonical_category_id
    and not exists (
      select 1
      from public.standard_catalog_course_sources sccs
      where sccs.catalog_course_id = scc.id
    );
end;
$$;

comment on constraint standard_catalog_discovery_item_category_type
  on public.standard_catalog_discovery_items is
  'Governed catalog evidence supports general academic, alternate achievement, CTE, and general categories.';
comment on constraint standard_sources_source_kind
  on public.standard_sources is
  'Authoritative source roles include Alabama Alternate Achievement Standards as entry-producing standards.';

notify pgrst, 'reload schema';

commit;
