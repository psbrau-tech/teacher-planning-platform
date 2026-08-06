-- Correct the pilot allowlist synchronization order.
-- The original BEFORE trigger called apply_pilot_access before an inserted row
-- was visible to its lookup. For an already-authenticated approved user, that
-- could incorrectly deactivate the profile and remove roles. Timestamp updates
-- remain a BEFORE concern; identity synchronization runs only after the row is
-- committed to the statement-visible table state.

create or replace function private.touch_pilot_access_allowlist()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

revoke all on function private.touch_pilot_access_allowlist()
  from public, anon, authenticated;

drop trigger if exists touch_tpp_pilot_access_allowlist
  on private.pilot_access_allowlist;
create trigger touch_tpp_pilot_access_allowlist
before update on private.pilot_access_allowlist
for each row execute function private.touch_pilot_access_allowlist();

create or replace function private.sync_allowlisted_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  user_record record;
begin
  select u.id, u.email, u.raw_user_meta_data
    into user_record
  from auth.users u
  where lower(u.email) = new.email
  limit 1;

  if found then
    perform private.apply_pilot_access(
      user_record.id,
      user_record.email,
      coalesce(
        user_record.raw_user_meta_data ->> 'full_name',
        user_record.raw_user_meta_data ->> 'name',
        user_record.email
      )
    );
  end if;
  return new;
end;
$$;

revoke all on function private.sync_allowlisted_auth_user()
  from public, anon, authenticated;

drop trigger if exists sync_tpp_allowlisted_user
  on private.pilot_access_allowlist;
create trigger sync_tpp_allowlisted_user
after insert or update on private.pilot_access_allowlist
for each row execute function private.sync_allowlisted_auth_user();

comment on function private.sync_allowlisted_auth_user() is
  'After-write synchronization that applies the now-visible allowlist row to an existing Supabase Auth user.';
