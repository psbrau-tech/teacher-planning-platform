-- Gate E controlled-pilot hardening: a deterministic parser attempt that fails before
-- emitting its parser version must still be stageable as pending review evidence.
-- Approval remains fail-closed because approve_standard_snapshot requires
-- provenance.parser_status = 'parsed'. Teacher/admin professional reference data only.

alter table public.standard_snapshots
  alter column parser_version drop not null;
