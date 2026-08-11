-- Gate E: make teacher-visible catalog projection an approval-time action.
-- Pending source snapshots may be fully parsed and reviewed, but they cannot change the
-- active teacher catalog until a platform administrator approves that exact snapshot.

create table public.standard_snapshot_courses (
  snapshot_id uuid not null
    references public.standard_snapshots(id) on delete cascade,
  course_id uuid not null
    references public.standard_courses(id) on delete cascade,
  sequence integer not null,
  display_name text not null,
  source_course_code text,
  grade_band text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  primary key (snapshot_id, course_id),
  constraint standard_snapshot_courses_sequence_positive check (sequence > 0),
  constraint standard_snapshot_courses_name_nonempty check (
    length(btrim(display_name)) > 0
  )
);

create index standard_snapshot_courses_course_idx
  on public.standard_snapshot_courses (course_id, snapshot_id);

alter table public.standard_snapshot_courses enable row level security;
revoke all on table public.standard_snapshot_courses
  from public, anon, authenticated, service_role;
grant select on table public.standard_snapshot_courses to authenticated;
grant select, insert, update, delete on table public.standard_snapshot_courses to service_role;

create policy standard_snapshot_courses_read_governed
on public.standard_snapshot_courses
for select to authenticated
using (
  exists (
    select 1
    from public.standard_snapshots ss
    where ss.id = standard_snapshot_courses.snapshot_id
      and (
        ss.status in ('approved', 'superseded')
        or private.has_role('platform_admin'::public.app_role, null)
      )
  )
);

create or replace function private.enforce_snapshot_course_source()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  snapshot_source_id uuid;
  course_source_id uuid;
begin
  select ss.source_id into snapshot_source_id
  from public.standard_snapshots ss
  where ss.id = new.snapshot_id;

  select sc.source_id into course_source_id
  from public.standard_courses sc
  where sc.id = new.course_id;

  if snapshot_source_id is null
     or course_source_id is null
     or snapshot_source_id <> course_source_id then
    raise exception 'snapshot course and snapshot must belong to the same source';
  end if;
  return new;
end;
$$;

drop trigger if exists snapshot_course_source_trigger on public.standard_snapshot_courses;
create trigger snapshot_course_source_trigger
before insert or update of snapshot_id, course_id on public.standard_snapshot_courses
for each row execute function private.enforce_snapshot_course_source();

-- Do not project parsed pending courses automatically.
drop trigger if exists standard_course_catalog_sync_trigger on public.standard_courses;

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
    when src.source_kind = 'course_of_study' and src.provides_standard_entries then 'primary'
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

  -- Remove this source's prior teacher-catalog relationships that are not present in the
  -- newly approved snapshot. Other authoritative source relationships remain intact.
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

  -- Deactivate canonical courses only when no currently approved source relationship remains.
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

create or replace function public.approve_standard_snapshot(target_snapshot_id uuid)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  target_source_id uuid;
  target_source_key text;
  target_source_kind text;
  target_provides_entries boolean;
  target_status text;
  target_parser_status text;
  target_course_count integer;
  target_entry_count integer;
  actor_id uuid := (select auth.uid());
begin
  if actor_id is null
     or not private.has_role('platform_admin'::public.app_role, null) then
    raise exception 'platform administrator role is required';
  end if;

  select
    ss.source_id,
    src.source_key,
    src.source_kind,
    src.provides_standard_entries,
    ss.status,
    ss.provenance ->> 'parser_status'
  into
    target_source_id,
    target_source_key,
    target_source_kind,
    target_provides_entries,
    target_status,
    target_parser_status
  from public.standard_snapshots ss
  join public.standard_sources src on src.id = ss.source_id
  where ss.id = target_snapshot_id
  for update of ss;

  if target_source_id is null then
    raise exception 'standards snapshot not found';
  end if;

  if target_status <> 'pending' then
    raise exception 'only a pending standards snapshot can be approved';
  end if;

  if target_parser_status <> 'parsed' then
    raise exception 'only a successfully parsed source snapshot can be approved';
  end if;

  select count(*) into target_course_count
  from public.standard_snapshot_courses ssc
  join public.standard_courses sc on sc.id = ssc.course_id
  where ssc.snapshot_id = target_snapshot_id
    and sc.source_id = target_source_id;

  if target_course_count = 0 then
    raise exception 'source snapshot has no validated parsed courses';
  end if;

  select count(*) into target_entry_count
  from public.standard_entries se
  join public.standard_courses sc on sc.id = se.course_id
  where se.snapshot_id = target_snapshot_id
    and sc.source_id = target_source_id;

  if target_provides_entries and target_entry_count = 0 then
    raise exception 'standards source snapshot has no validated parsed entries';
  end if;

  if not target_provides_entries and target_entry_count <> 0 then
    raise exception 'course-listing source snapshot must not contain standards entries';
  end if;

  if target_source_kind = 'supplemental_curriculum'
     and target_source_key = 'army_jrotc_v12'
     and (
       select count(distinct sc.course_key)
       from public.standard_snapshot_courses ssc
       join public.standard_courses sc on sc.id = ssc.course_id
       where ssc.snapshot_id = target_snapshot_id
         and sc.source_id = target_source_id
         and sc.course_key in (
           'army_jrotc_let_1',
           'army_jrotc_let_2',
           'army_jrotc_let_3',
           'army_jrotc_let_4'
         )
     ) <> 4 then
    raise exception 'all four Army JROTC LET courses are required';
  end if;

  update public.standard_snapshots
  set status = 'superseded'
  where source_id = target_source_id
    and status = 'approved';

  update public.standard_snapshots
  set status = 'approved',
      approved_by = actor_id,
      approved_at = now()
  where id = target_snapshot_id;

  update public.standard_sources
  set approved_snapshot_id = target_snapshot_id,
      discovery_status = 'approved',
      updated_at = now()
  where id = target_source_id;

  perform private.sync_approved_standard_source_to_catalog(
    target_source_id,
    target_snapshot_id
  );

  insert into public.audit_events (
    actor_id,
    entity_type,
    entity_id,
    action,
    after_data,
    reason
  ) values (
    actor_id,
    'standard_snapshot',
    target_snapshot_id,
    'approve_standard_snapshot',
    jsonb_build_object(
      'source_id', target_source_id,
      'source_key', target_source_key,
      'source_kind', target_source_kind,
      'status', 'approved',
      'course_count', target_course_count,
      'entry_count', target_entry_count
    ),
    'Platform owner approved authoritative standards or course-catalog snapshot'
  );

  return target_snapshot_id;
end;
$$;

revoke all on function public.approve_standard_snapshot(uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.approve_standard_snapshot(uuid)
  to authenticated;

notify pgrst, 'reload schema';
