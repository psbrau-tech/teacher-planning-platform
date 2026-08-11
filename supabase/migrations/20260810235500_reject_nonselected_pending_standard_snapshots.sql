-- Gate E: an explicit snapshot approval also disposes of older/nonselected pending
-- candidates for the same authoritative source. This preserves every candidate as
-- immutable audit history while preventing an obsolete parser candidate from remaining
-- indefinitely actionable after a newer reviewed candidate is approved.

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

  -- Explicitly dispose of every nonselected pending candidate for this source. These
  -- snapshots remain queryable as rejected audit history and can never be approved later.
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
