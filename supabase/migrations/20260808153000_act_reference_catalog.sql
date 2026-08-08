-- Gate E: governed public first-party ACT reference catalog.
-- Professional curriculum/assessment-reference data only. No student data.

create table public.act_reference_sources (
  id uuid primary key default gen_random_uuid(),
  source_key text not null unique,
  publisher text not null default 'ACT',
  source_type text not null,
  title text not null,
  landing_url text not null,
  document_url text not null,
  edition text,
  effective_date text,
  status text not null default 'approved',
  retrieved_at timestamptz,
  source_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint act_reference_source_type check (
    source_type in (
      'assessment_skill_framework',
      'assessment_blueprint',
      'official_preparation_guidance',
      'readiness_benchmark'
    )
  ),
  constraint act_reference_source_status check (
    status in ('pending', 'approved', 'superseded', 'retired')
  ),
  constraint act_reference_source_publisher check (publisher = 'ACT')
);

create table public.act_reference_snapshots (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references public.act_reference_sources(id) on delete restrict,
  retrieved_at timestamptz not null default now(),
  source_sha256 text not null,
  normalized_sha256 text not null,
  parser_version text not null,
  status text not null default 'pending',
  approved_by uuid references public.profiles(id),
  approved_at timestamptz,
  provenance jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint act_reference_snapshot_status check (
    status in ('pending', 'approved', 'superseded', 'rejected')
  ),
  constraint act_reference_snapshot_hashes check (
    length(source_sha256) = 64 and length(normalized_sha256) = 64
  ),
  unique (source_id, source_sha256)
);

create unique index act_reference_one_approved_snapshot
  on public.act_reference_snapshots (source_id)
  where status = 'approved';

create table public.act_reference_entries (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references public.act_reference_snapshots(id) on delete restrict,
  source_id uuid not null references public.act_reference_sources(id) on delete restrict,
  reference_code text not null,
  domain text not null,
  category text,
  score_range text,
  exact_text text not null,
  sequence integer not null check (sequence > 0),
  source_locator text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint act_reference_entry_text_nonempty check (length(btrim(exact_text)) > 0),
  unique (snapshot_id, reference_code, sequence)
);

create index act_reference_entries_lookup_idx
  on public.act_reference_entries (domain, reference_code, snapshot_id);

create table public.act_readiness_benchmarks (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null references public.act_reference_snapshots(id) on delete restrict,
  source_id uuid not null references public.act_reference_sources(id) on delete restrict,
  domain text not null,
  benchmark_score integer not null,
  related_course_area text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint act_readiness_benchmark_score check (benchmark_score between 1 and 36),
  unique (snapshot_id, domain)
);

alter table public.act_reference_sources enable row level security;
alter table public.act_reference_snapshots enable row level security;
alter table public.act_reference_entries enable row level security;
alter table public.act_readiness_benchmarks enable row level security;

revoke all on table
  public.act_reference_sources,
  public.act_reference_snapshots,
  public.act_reference_entries,
  public.act_readiness_benchmarks
from public, anon, authenticated, service_role;

grant select on table
  public.act_reference_sources,
  public.act_reference_snapshots,
  public.act_reference_entries,
  public.act_readiness_benchmarks
  to authenticated;

grant select, insert, update, delete on table
  public.act_reference_sources,
  public.act_reference_snapshots,
  public.act_reference_entries,
  public.act_readiness_benchmarks
  to service_role;

create policy act_reference_sources_read_approved
on public.act_reference_sources for select to authenticated
using (status = 'approved' or private.has_role('platform_admin'::public.app_role, null));

create policy act_reference_snapshots_read_approved
on public.act_reference_snapshots for select to authenticated
using (status = 'approved' or private.has_role('platform_admin'::public.app_role, null));

create policy act_reference_entries_read_approved
on public.act_reference_entries for select to authenticated
using (
  exists (
    select 1 from public.act_reference_snapshots ars
    where ars.id = act_reference_entries.snapshot_id and ars.status = 'approved'
  )
);

create policy act_readiness_benchmarks_read_approved
on public.act_readiness_benchmarks for select to authenticated
using (
  exists (
    select 1 from public.act_reference_snapshots ars
    where ars.id = act_readiness_benchmarks.snapshot_id and ars.status = 'approved'
  )
);

-- Public, first-party ACT sources approved for the initial reference boundary.
insert into public.act_reference_sources (
  source_key, source_type, title, landing_url, document_url, edition, status, metadata
) values
  ('act_ccrs_english', 'assessment_skill_framework', 'English College and Career Readiness Standards', 'https://www.act.org/content/act/en/college-and-career-readiness/standards.html', 'https://www.act.org/content/act/en/college-and-career-readiness/standards/english-standards.html', 'current public web edition', 'approved', '{"domain":"English","commercial":false}'::jsonb),
  ('act_ccrs_mathematics', 'assessment_skill_framework', 'Mathematics College and Career Readiness Standards', 'https://www.act.org/content/act/en/college-and-career-readiness/standards.html', 'https://www.act.org/content/act/en/college-and-career-readiness/standards/mathematics-standards.html', 'current public web edition', 'approved', '{"domain":"Mathematics","commercial":false}'::jsonb),
  ('act_ccrs_reading', 'assessment_skill_framework', 'Reading College and Career Readiness Standards', 'https://www.act.org/content/act/en/college-and-career-readiness/standards.html', 'https://www.act.org/content/act/en/college-and-career-readiness/standards/reading-standards.html', 'current public web edition', 'approved', '{"domain":"Reading","commercial":false}'::jsonb),
  ('act_ccrs_science', 'assessment_skill_framework', 'Science College and Career Readiness Standards', 'https://www.act.org/content/act/en/college-and-career-readiness/standards.html', 'https://www.act.org/content/act/en/college-and-career-readiness/standards/science-standards.html', 'current public web edition', 'approved', '{"domain":"Science","commercial":false}'::jsonb),
  ('act_ccrs_writing', 'assessment_skill_framework', 'Writing College and Career Readiness Standards', 'https://www.act.org/content/act/en/college-and-career-readiness/standards.html', 'https://www.act.org/content/act/en/college-and-career-readiness/standards/writing-standards.html', 'current public web edition', 'approved', '{"domain":"Writing","commercial":false}'::jsonb),
  ('act_readiness_benchmarks', 'readiness_benchmark', 'ACT College Readiness Benchmarks', 'https://www.act.org/content/act/en/college-and-career-readiness/benchmarks.html', 'https://www.act.org/content/act/en/college-and-career-readiness/benchmarks.html', 'current public web edition', 'approved', '{"commercial":false}'::jsonb),
  ('act_preparing_public', 'official_preparation_guidance', 'Preparing for the ACT', 'https://www.act.org/content/act/en/products-and-services/state-and-district-solutions/act-info-for-examinees.html', 'https://www.act.org/content/act/en/products-and-services/state-and-district-solutions/act-info-for-examinees.html', '2026 public preparation guidance', 'approved', '{"commercial":false,"practice_questions_ingested":false}'::jsonb),
  ('act_test_structure_current', 'assessment_blueprint', 'Current ACT Test Structure and Content', 'https://www.act.org/content/act/en/products-and-services/the-act/test-preparation/act-exam-sections-and-structure.html', 'https://www.act.org/content/act/en/products-and-services/the-act/test-preparation/act-exam-sections-and-structure.html', 'current public web edition', 'approved', '{"commercial":false}'::jsonb)
on conflict (source_key) do nothing;
