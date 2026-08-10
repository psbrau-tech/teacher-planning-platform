begin;

alter table public.standard_snapshots
  drop constraint if exists standard_snapshots_source_id_source_sha256_key;

drop index if exists public.standard_snapshots_source_hash_parser_version_key;

create unique index standard_snapshots_source_hash_parser_version_key
  on public.standard_snapshots (
    source_id,
    source_sha256,
    coalesce(parser_version, '')
  );

comment on index public.standard_snapshots_source_hash_parser_version_key is
  'Allows immutable rematerialization of the same authoritative source file when reviewed parser logic changes, while preventing duplicate snapshots for the same source hash and parser version.';

commit;
