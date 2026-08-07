-- A publisher change may be detectable at the raw-document level before the new
-- document can be parsed safely. Preserve that candidate fingerprint for review,
-- but keep it non-approvable until validated standard entries exist.

alter table public.standard_snapshots
  alter column normalized_sha256 drop not null;

alter table public.standard_snapshots
  drop constraint standard_snapshots_hash_nonempty;

alter table public.standard_snapshots
  add constraint standard_snapshots_hash_validity check (
    length(source_sha256) = 64
    and (
      normalized_sha256 is null
      or length(normalized_sha256) = 64
    )
  );
