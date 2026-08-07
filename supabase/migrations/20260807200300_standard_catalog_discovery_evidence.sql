-- Gate E: auditable Alabama catalog discovery evidence.
-- Discovery records what the authoritative catalogs publish before any source/snapshot approval.

create table public.standard_catalog_discovery_runs (
  id uuid primary key default gen_random_uuid(),
  checked_at timestamptz not null default now(),
  check_month date,
  trigger_kind text not null default 'manual',
  status text not null default 'completed',
  catalog_sha256 text not null,
  discovered_source_count integer not null default 0,
  unchanged_count integer not null default 0,
  changed_count integer not null default 0,
  new_count integer not null default 0,
  missing_count integer not null default 0,
  error_summary text,
  metadata jsonb not null default '{}'::jsonb,
  constraint standard_catalog_discovery_trigger_kind check (
    trigger_kind in ('manual', 'scheduled')
  ),
  constraint standard_catalog_discovery_status check (
    status in ('completed', 'partial', 'error')
  ),
  constraint standard_catalog_discovery_hash check (length(catalog_sha256) = 64),
  constraint standard_catalog_discovery_counts_nonnegative check (
    discovered_source_count >= 0
    and unchanged_count >= 0
    and changed_count >= 0
    and new_count >= 0
    and missing_count >= 0
  )
);

create table public.standard_catalog_discovery_items (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null
    references public.standard_catalog_discovery_runs(id) on delete cascade,
  source_key text not null,
  result_state text not null,
  existing_source_id uuid references public.standard_sources(id) on delete set null,
  family text not null,
  category_key text,
  category_name text,
  category_type text,
  authority text not null,
  observed_title text,
  observed_edition text,
  observed_landing_url text,
  observed_document_url text,
  observed_document_format text,
  parser_key_hint text,
  source_kind text,
  previous_title text,
  previous_edition text,
  previous_document_url text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (run_id, source_key),
  constraint standard_catalog_discovery_item_state check (
    result_state in ('unchanged', 'changed', 'new', 'missing')
  ),
  constraint standard_catalog_discovery_item_category_type check (
    category_type is null
    or category_type in ('academic_subject', 'career_cluster', 'general')
  ),
  constraint standard_catalog_discovery_item_format check (
    observed_document_format is null
    or observed_document_format in ('pdf', 'docx', 'unknown')
  )
);

create index standard_catalog_discovery_runs_month_idx
  on public.standard_catalog_discovery_runs (check_month, checked_at desc);
create index standard_catalog_discovery_items_state_idx
  on public.standard_catalog_discovery_items (result_state, source_key);
create index standard_catalog_discovery_items_existing_source_idx
  on public.standard_catalog_discovery_items (existing_source_id, created_at desc);

alter table public.standard_catalog_discovery_runs enable row level security;
alter table public.standard_catalog_discovery_items enable row level security;

revoke all on table
  public.standard_catalog_discovery_runs,
  public.standard_catalog_discovery_items
from public, anon, authenticated, service_role;

grant select on table
  public.standard_catalog_discovery_runs,
  public.standard_catalog_discovery_items
  to authenticated;

grant select, insert, update, delete on table
  public.standard_catalog_discovery_runs,
  public.standard_catalog_discovery_items
  to service_role;

create policy standard_catalog_discovery_runs_platform_admin_read
on public.standard_catalog_discovery_runs
for select to authenticated
using (private.has_role('platform_admin'::public.app_role, null));

create policy standard_catalog_discovery_items_platform_admin_read
on public.standard_catalog_discovery_items
for select to authenticated
using (private.has_role('platform_admin'::public.app_role, null));

notify pgrst, 'reload schema';
