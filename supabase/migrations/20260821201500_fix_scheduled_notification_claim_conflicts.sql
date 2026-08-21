-- Repair the live school-scoped notification claim functions after the first Friday
-- execution exposed ambiguous PL/pgSQL ON CONFLICT column references. Both functions
-- return columns named school_id and recipient_profile_id, so an unqualified conflict
-- target can collide with PL/pgSQL output parameters at execution time.
--
-- The replacement is deliberately exact and fail-closed: it updates only the known
-- conflict clause in the two governed functions and aborts if either live definition
-- no longer matches the reviewed source.

do $migration$
declare
  function_signature regprocedure;
  current_definition text;
  repaired_definition text;
  old_conflict_clause constant text := E'on conflict (\n      notification_key,\n      school_id,\n      recipient_profile_id,\n      week_start\n    ) do nothing';
  new_conflict_clause constant text := E'on conflict on constraint scheduled_notification_deliveries_school_recipient_week_key\n    do nothing';
begin
  foreach function_signature in array array[
    'public.claim_teacher_friday_reminder_candidates(uuid,date)'::regprocedure,
    'public.claim_scheduled_admin_weekly_digest_candidates(uuid,date)'::regprocedure
  ]
  loop
    select pg_get_functiondef(function_signature)
    into current_definition;

    repaired_definition := replace(
      current_definition,
      old_conflict_clause,
      new_conflict_clause
    );

    if repaired_definition = current_definition then
      raise exception 'Scheduled notification claim repair target did not match %',
        function_signature::text;
    end if;

    execute repaired_definition;
  end loop;
end
$migration$;

notify pgrst, 'reload schema';
