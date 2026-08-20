-- Governed Alabama ELA proficiency scales for Grades 6-12.
--
-- Proficiency scales are instructional guidance tied to authoritative Course of Study
-- standards. They are not selectable standards and never replace authoritative standard text.

alter table public.standard_sources
  drop constraint if exists standard_sources_source_kind;
alter table public.standard_sources
  add constraint standard_sources_source_kind check (
    source_kind in (
      'course_of_study',
      'program_guide',
      'supplemental_curriculum',
      'proficiency_scale',
      'reference'
    )
  );

create table public.standard_proficiency_scales (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null
    references public.standard_snapshots(id) on delete cascade,
  grade_band text not null,
  standard_code text not null,
  standard_text text not null,
  literacy_type text,
  focus_area text,
  category text,
  levels jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint standard_proficiency_scales_grade check (
    grade_band in ('6', '7', '8', '9', '10', '11', '12')
  ),
  constraint standard_proficiency_scales_code_nonempty check (
    length(btrim(standard_code)) > 0
  ),
  constraint standard_proficiency_scales_text_nonempty check (
    length(btrim(standard_text)) > 0
  ),
  constraint standard_proficiency_scales_core_levels check (
    levels ? '4.0' and levels ? '3.0' and levels ? '2.0'
  ),
  unique (snapshot_id, grade_band, standard_code)
);

create index standard_proficiency_scales_grade_code_idx
  on public.standard_proficiency_scales (grade_band, standard_code, snapshot_id);

alter table public.standard_proficiency_scales enable row level security;
revoke all on table public.standard_proficiency_scales
  from public, anon, authenticated, service_role;
grant select on table public.standard_proficiency_scales to authenticated;
grant select, insert, update, delete on table public.standard_proficiency_scales to service_role;

create policy standard_proficiency_scales_read_governed
on public.standard_proficiency_scales
for select to authenticated
using (
  exists (
    select 1
    from public.standard_snapshots ss
    where ss.id = standard_proficiency_scales.snapshot_id
      and (
        ss.status in ('approved', 'superseded')
        or private.has_role('platform_admin'::public.app_role, null)
      )
  )
);

insert into public.standard_sources (
  source_key,
  family,
  authority,
  title,
  edition,
  landing_url,
  document_url,
  document_format,
  resolver_key,
  parser_key,
  is_active,
  discovery_status,
  source_kind,
  provides_standard_entries
)
select
  'alabama_ela_proficiency_grade_' || grade,
  'alabama_instructional_support',
  'Alabama State Department of Education',
  'Grade ' || grade || ' ELA Proficiency Scales',
  'Current ALSDE publication',
  'https://english-language-arts.alsde.edu/proficiency-scales',
  'https://english-language-arts.alsde.edu/proficiency-scales',
  'pdf',
  'alabama_ela_proficiency_grade_' || grade || '_current',
  'alabama_ela_proficiency_grade_' || grade,
  true,
  'approved',
  'proficiency_scale',
  false
from unnest(array['6','7','8','9','10','11','12']) as grade
on conflict (source_key) do update set
  family = excluded.family,
  authority = excluded.authority,
  title = excluded.title,
  edition = excluded.edition,
  landing_url = excluded.landing_url,
  resolver_key = excluded.resolver_key,
  parser_key = excluded.parser_key,
  source_kind = excluded.source_kind,
  provides_standard_entries = excluded.provides_standard_entries,
  is_active = true,
  updated_at = now();

-- Extend the existing reviewed-snapshot approval contract for non-selectable proficiency
-- guidance. Proficiency snapshots require parsed scale rows and never project a course into
-- the teacher standards catalog.
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
  target_scale_count integer;
  rejected_pending_snapshot_id uuid;
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

  select count(*) into target_entry_count
  from public.standard_entries se
  join public.standard_courses sc on sc.id = se.course_id
  where se.snapshot_id = target_snapshot_id
    and sc.source_id = target_source_id;

  select count(*) into target_scale_count
  from public.standard_proficiency_scales sps
  where sps.snapshot_id = target_snapshot_id;

  if target_source_kind = 'proficiency_scale' then
    if target_provides_entries then
      raise exception 'proficiency-scale source must not provide selectable standard entries';
    end if;
    if target_course_count <> 0 or target_entry_count <> 0 then
      raise exception 'proficiency-scale snapshot must not contain standards catalog rows';
    end if;
    if target_scale_count = 0 then
      raise exception 'proficiency-scale snapshot has no validated parsed scales';
    end if;
  else
    if target_course_count = 0 then
      raise exception 'source snapshot has no validated parsed courses';
    end if;

    if target_provides_entries and target_entry_count = 0 then
      raise exception 'standards source snapshot has no validated parsed entries';
    end if;

    if not target_provides_entries and target_entry_count <> 0 then
      raise exception 'course-listing source snapshot must not contain standards entries';
    end if;
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

  for rejected_pending_snapshot_id in
    select ss.id
    from public.standard_snapshots ss
    where ss.source_id = target_source_id
      and ss.status = 'pending'
      and ss.id <> target_snapshot_id
    order by ss.created_at
    for update
  loop
    update public.standard_snapshots
    set status = 'rejected'
    where id = rejected_pending_snapshot_id;

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
      rejected_pending_snapshot_id,
      'reject_nonselected_standard_snapshot',
      jsonb_build_object(
        'source_id', target_source_id,
        'source_key', target_source_key,
        'status', 'rejected',
        'selected_snapshot_id', target_snapshot_id
      ),
      'Platform owner approved a different reviewed candidate for the same authoritative source'
    );
  end loop;

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

  if target_source_kind <> 'proficiency_scale' then
    perform private.sync_approved_standard_source_to_catalog(
      target_source_id,
      target_snapshot_id
    );
  end if;

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
      'entry_count', target_entry_count,
      'proficiency_scale_count', target_scale_count
    ),
    'Platform owner approved reviewed standards, catalog, or proficiency guidance snapshot'
  );

  return target_snapshot_id;
end;
$$;

revoke all on function public.approve_standard_snapshot(uuid)
  from public, anon, authenticated, service_role;
grant execute on function public.approve_standard_snapshot(uuid)
  to authenticated;

notify pgrst, 'reload schema';
