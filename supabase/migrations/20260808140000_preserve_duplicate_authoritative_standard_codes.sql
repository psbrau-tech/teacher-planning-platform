-- Preserve authoritative source identifiers exactly, including rare source-document
-- duplicate identifiers. A standard entry's UUID + snapshot/course sequence is the
-- governed identity; source code remains provenance/display data and is not rewritten.
-- Teacher/curriculum/standards data only. No student data.

alter table public.standard_entries
  drop constraint if exists standard_entries_snapshot_id_course_id_code_key;

alter table public.standard_entries
  add constraint standard_entries_snapshot_course_sequence_key
  unique (snapshot_id, course_id, sequence);

create index if not exists standard_entries_course_snapshot_code_idx
  on public.standard_entries (course_id, snapshot_id, code);
