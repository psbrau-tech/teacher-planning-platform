-- Gate E: authoritative standards snapshots, course mapping, weekly selections,
-- monthly source validation evidence, and bounded AI-usage decision recording.
-- Teacher/curriculum/standards data only. No student data.

create table public.standard_sources (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  family text not null,
  authority text not null,
  title text not null,
  edition text not null,
  effective_school_year text,
  landing_url text not null,
  document_url text not null,
  document_format text not null,
  resolver_key text not null,
  parser_key text not null,
  approved_snapshot_id uuid,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint standard_sources_format check (document_format in ('pdf', 'docx'))
);

create table public.standard_snapshots (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.standard_sources(id) on delete restrict,
  retrieved_at timestamptz not null default now(),
  resolved_document_url text not null,
  source_sha256 text not null,
  normalized_sha256 text not null,
  source_version text,
  effective_date text,
  parser_version text not null,
  status text not null default 'pending',
  provenance jsonb not null default '{}'::jsonb,
  approved_by uuid references public.profiles(id),
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  constraint standard_snapshots_status check (
    status in ('pending', 'approved', 'superseded', 'rejected')
  ),
  constraint standard_snapshots_hash_nonempty check (
    length(source_sha256) = 64 and length(normalized_sha256) = 64
  ),
  unique (source_id, source_sha256)
);

alter table public.standard_sources
  add constraint standard_sources_approved_snapshot_fk
  foreign key (approved_snapshot_id)
  references public.standard_snapshots(id)
  on delete set null;

create unique index standard_snapshots_one_approved_per_source
  on public.standard_snapshots (source_id)
  where status = 'approved';

create table public.standard_courses (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.standard_sources(id) on delete cascade,
  course_key text not null,
  display_name text not null,
  source_course_code text,
  grade_band text,
  is_pilot_allowed boolean not null default false,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_id, course_key)
);

create table public.standard_entries (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references public.standard_snapshots(id) on delete cascade,
  course_id uuid not null references public.standard_courses(id) on delete cascade,
  sequence integer not null check (sequence > 0),
  code text not null,
  text text not null,
  parent_code text,
  strand text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint standard_entries_text_nonempty check (length(btrim(text)) > 0),
  unique (snapshot_id, course_id, code)
);

create index standard_entries_course_sequence_idx
  on public.standard_entries (course_id, snapshot_id, sequence);

create table public.assignment_standard_courses (
  teaching_assignment_id uuid primary key
    references public.teaching_assignments(id) on delete cascade,
  source_id uuid not null references public.standard_sources(id) on delete restrict,
  course_id uuid not null references public.standard_courses(id) on delete restrict,
  mapped_by uuid not null references public.profiles(id),
  mapped_at timestamptz not null default now()
);

-- Enforce that the selected standards course belongs to the selected source without a
-- cross-table CHECK constraint (which PostgreSQL does not support).
create or replace function private.enforce_assignment_standard_course_source()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  expected_source_id uuid;
begin
  select sc.source_id into expected_source_id
  from public.standard_courses sc
  where sc.id = new.course_id;

  if expected_source_id is null or expected_source_id <> new.source_id then
    raise exception 'standards course does not belong to selected source';
  end if;
  return new;
end;
$$;

drop trigger if exists assignment_standard_course_source_trigger
  on public.assignment_standard_courses;
create trigger assignment_standard_course_source_trigger
before insert or update on public.assignment_standard_courses
for each row execute function private.enforce_assignment_standard_course_source();

create table public.weekly_standard_selections (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null
    references public.teaching_assignments(id) on delete cascade,
  week_start date not null,
  standard_entry_id uuid not null references public.standard_entries(id) on delete restrict,
  selected_by uuid not null references public.profiles(id),
  created_at timestamptz not null default now(),
  unique (teaching_assignment_id, week_start, standard_entry_id)
);

create index weekly_standard_selections_assignment_week_idx
  on public.weekly_standard_selections (teaching_assignment_id, week_start);

create table public.standard_source_checks (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.standard_sources(id) on delete cascade,
  check_month date not null,
  checked_at timestamptz not null default now(),
  result_status text not null,
  approved_snapshot_id_before uuid references public.standard_snapshots(id),
  observed_source_sha256 text,
  candidate_snapshot_id uuid references public.standard_snapshots(id),
  resolved_document_url text,
  error_summary text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint standard_source_checks_month_first check (
    extract(day from check_month) = 1
  ),
  constraint standard_source_checks_status check (
    result_status in ('unchanged', 'changed', 'unavailable_error')
  ),
  unique (source_id, check_month)
);

alter table public.standard_sources enable row level security;
alter table public.standard_snapshots enable row level security;
alter table public.standard_courses enable row level security;
alter table public.standard_entries enable row level security;
alter table public.assignment_standard_courses enable row level security;
alter table public.weekly_standard_selections enable row level security;
alter table public.standard_source_checks enable row level security;

revoke all on table
  public.standard_sources,
  public.standard_snapshots,
  public.standard_courses,
  public.standard_entries,
  public.assignment_standard_courses,
  public.weekly_standard_selections,
  public.standard_source_checks
from public, anon, authenticated, service_role;

grant select on table
  public.standard_sources,
  public.standard_snapshots,
  public.standard_courses,
  public.standard_entries,
  public.assignment_standard_courses,
  public.weekly_standard_selections,
  public.standard_source_checks
  to authenticated;

grant insert, update, delete on table
  public.assignment_standard_courses,
  public.weekly_standard_selections
  to authenticated;

grant select, insert, update, delete on table
  public.standard_sources,
  public.standard_snapshots,
  public.standard_courses,
  public.standard_entries,
  public.standard_source_checks
  to service_role;

create policy standard_sources_read_governed on public.standard_sources
for select to authenticated
using (
  is_active
  or private.has_role('platform_admin'::public.app_role, null)
);

create policy standard_snapshots_read_governed on public.standard_snapshots
for select to authenticated
using (
  status in ('approved', 'superseded')
  or private.has_role('platform_admin'::public.app_role, null)
);

create policy standard_courses_read_pilot on public.standard_courses
for select to authenticated
using (
  is_pilot_allowed
  or private.has_role('platform_admin'::public.app_role, null)
);

create policy standard_entries_read_governed on public.standard_entries
for select to authenticated
using (
  exists (
    select 1
    from public.standard_snapshots ss
    join public.standard_courses sc on sc.id = standard_entries.course_id
    where ss.id = standard_entries.snapshot_id
      and (
        (ss.status in ('approved', 'superseded') and sc.is_pilot_allowed)
        or private.has_role('platform_admin'::public.app_role, null)
      )
  )
);

create policy assignment_standard_courses_read_governed
on public.assignment_standard_courses
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));

create policy assignment_standard_courses_owner_write
on public.assignment_standard_courses
for all to authenticated
using (private.can_access_assignment(teaching_assignment_id))
with check (
  mapped_by = (select auth.uid())
  and private.can_access_assignment(teaching_assignment_id)
  and exists (
    select 1 from public.standard_courses sc
    where sc.id = assignment_standard_courses.course_id
      and sc.source_id = assignment_standard_courses.source_id
      and sc.is_pilot_allowed
  )
);

create policy weekly_standard_selections_read_governed
on public.weekly_standard_selections
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));

create policy weekly_standard_selections_owner_write
on public.weekly_standard_selections
for all to authenticated
using (
  selected_by = (select auth.uid())
  and private.can_access_assignment(teaching_assignment_id)
)
with check (
  selected_by = (select auth.uid())
  and private.can_access_assignment(teaching_assignment_id)
  and exists (
    select 1
    from public.standard_entries se
    join public.standard_snapshots ss on ss.id = se.snapshot_id
    join public.assignment_standard_courses asc_map
      on asc_map.teaching_assignment_id = weekly_standard_selections.teaching_assignment_id
     and asc_map.course_id = se.course_id
    where se.id = weekly_standard_selections.standard_entry_id
      and ss.status = 'approved'
  )
);

create policy standard_source_checks_platform_read on public.standard_source_checks
for select to authenticated
using (private.has_role('platform_admin'::public.app_role, null));

-- Teachers can record only the accept/reject decision on their own AI usage event through
-- this narrow function. Token counts, model, and cost remain immutable to the client.
create or replace function public.set_ai_usage_acceptance(
  target_event_id uuid,
  accepted boolean
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.ai_usage_events
  set accepted_by_teacher = accepted
  where id = target_event_id
    and teacher_id = (select auth.uid());
  return found;
end;
$$;

revoke all on function public.set_ai_usage_acceptance(uuid, boolean)
  from public, anon, authenticated, service_role;
grant execute on function public.set_ai_usage_acceptance(uuid, boolean)
  to authenticated;

-- Seed only authoritative source metadata. Snapshot content is populated by the governed
-- importer so no copied standards text is silently embedded in migrations.
insert into public.standard_sources (
  source_key,
  family,
  authority,
  title,
  edition,
  effective_school_year,
  landing_url,
  document_url,
  document_format,
  resolver_key,
  parser_key
) values
  (
    'alabama_ela_2021',
    'alabama_academic',
    'Alabama State Department of Education',
    'Alabama Course of Study: English Language Arts',
    '2021 Alabama Course of Study: English Language Arts',
    '2022-2023',
    'https://www.alabamaachieves.org/content-areas-specialty/english-language-arts/',
    'https://www.alabamaachieves.org/wp-content/uploads/2023/06/AS_202353_2021-Alabama-Course-of-Study-English-Language-Arts_V1.0.pdf',
    'pdf',
    'alabama_ela_current',
    'alabama_ela_2021'
  ),
  (
    'alabama_bma_2021',
    'alabama_cte',
    'Alabama State Department of Education',
    'Alabama Course of Study: Business Management and Administration',
    '2021 BMA Course of Study',
    null,
    'https://www.alabamaachieves.org/cte/cte-course-of-study/',
    'https://www.alabamaachieves.org/wp-content/uploads/2021/08/2021-BMA-Course-of-StudyMARCH2021.pdf',
    'pdf',
    'alabama_bma_current',
    'alabama_bma_2021'
  ),
  (
    'army_jrotc_v12',
    'army_jrotc',
    'U.S. Army Cadet Command',
    'Army JROTC Curriculum Guide',
    'JROTC Curriculum Guide v12 (25 JUN 2025)',
    null,
    'https://usarmyjrotc.army.mil/jsocc-course-documents/',
    'https://usarmyjrotc.army.mil/wp-content/uploads/2025/07/JROTC-Curriculum-Guide-25JUN25-4.docx',
    'docx',
    'army_jrotc_current',
    'army_jrotc_v12'
  )
on conflict (source_key) do update set
  family = excluded.family,
  authority = excluded.authority,
  title = excluded.title,
  edition = excluded.edition,
  effective_school_year = excluded.effective_school_year,
  landing_url = excluded.landing_url,
  document_url = excluded.document_url,
  document_format = excluded.document_format,
  resolver_key = excluded.resolver_key,
  parser_key = excluded.parser_key,
  updated_at = now();

notify pgrst, 'reload schema';
