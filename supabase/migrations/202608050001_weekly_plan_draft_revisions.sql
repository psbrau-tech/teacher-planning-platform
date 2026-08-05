alter table public.weekly_plan_snapshots
  add column if not exists revision integer not null default 1,
  add column if not exists updated_at timestamptz not null default now(),
  add column if not exists updated_by uuid references public.profiles(id),
  add column if not exists is_draft boolean not null default true;

alter table public.weekly_plan_snapshots
  add constraint weekly_plan_snapshots_revision_positive
  check (revision > 0);

create or replace function public.bump_weekly_plan_revision()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
  if new.source_data is distinct from old.source_data then
    if new.revision <> old.revision then
      raise exception 'revision is managed by the database';
    end if;
    new.revision := old.revision + 1;
    new.updated_at := now();
    new.updated_by := auth.uid();
  end if;
  return new;
end;
$$;

drop trigger if exists weekly_plan_revision_trigger on public.weekly_plan_snapshots;
create trigger weekly_plan_revision_trigger
before update on public.weekly_plan_snapshots
for each row execute function public.bump_weekly_plan_revision();

comment on column public.weekly_plan_snapshots.revision is
  'Monotonic revision used to reject stale weekly-plan edits.';
comment on column public.weekly_plan_snapshots.is_draft is
  'True until the teacher explicitly approves the weekly plan for export.';
