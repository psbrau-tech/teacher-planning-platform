create table if not exists public.friday_validation_snapshots (
  id uuid primary key default gen_random_uuid(),
  teaching_assignment_id uuid not null references public.teaching_assignments(id) on delete cascade,
  week_start date not null,
  result_data jsonb not null,
  revision integer not null default 1,
  validated_by uuid not null references public.profiles(id),
  validated_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (teaching_assignment_id, week_start),
  constraint friday_validation_revision_positive check (revision > 0),
  constraint friday_validation_result_object check (jsonb_typeof(result_data) = 'object')
);

alter table public.friday_validation_snapshots enable row level security;

create or replace function private.bump_friday_validation_revision()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if new.result_data is distinct from old.result_data then
    if new.revision <> old.revision then
      raise exception 'revision is managed by the database';
    end if;
    new.revision := old.revision + 1;
    new.validated_at := now();
    new.updated_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists friday_validation_revision_trigger
  on public.friday_validation_snapshots;
create trigger friday_validation_revision_trigger
before update on public.friday_validation_snapshots
for each row execute function private.bump_friday_validation_revision();

grant select, insert, update, delete
  on table public.friday_validation_snapshots
  to authenticated;

create policy friday_validation_read_governed
on public.friday_validation_snapshots
for select to authenticated
using (private.can_access_assignment(teaching_assignment_id));

create policy friday_validation_owner_write
on public.friday_validation_snapshots
for all to authenticated
using (
  validated_by = (select auth.uid())
  and exists (
    select 1
    from public.teaching_assignments ta
    where ta.id = friday_validation_snapshots.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
)
with check (
  validated_by = (select auth.uid())
  and exists (
    select 1
    from public.teaching_assignments ta
    where ta.id = friday_validation_snapshots.teaching_assignment_id
      and ta.teacher_id = (select auth.uid())
  )
);

notify pgrst, 'reload schema';
