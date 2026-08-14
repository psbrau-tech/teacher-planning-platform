-- Extend AI operational logging to governed administrator synthesis requests without
-- misclassifying an administrator as a teacher. This does not expand the data boundary:
-- only bounded model/token/cost/request metadata is stored here.

drop policy if exists ai_usage_teacher_insert on public.ai_usage_events;
drop policy if exists ai_usage_actor_insert on public.ai_usage_events;

create policy ai_usage_actor_insert on public.ai_usage_events
for insert to authenticated
with check (
  actor_id = (select auth.uid())
  and school_id = private.current_school_id()
  and (
    (
      teacher_id = (select auth.uid())
      and private.has_role('teacher'::public.app_role, school_id)
    )
    or (
      teacher_id is null
      and (
        private.has_role('school_admin'::public.app_role, school_id)
        or private.has_role('district_admin'::public.app_role, null)
        or private.has_role('platform_admin'::public.app_role, null)
      )
    )
  )
);

notify pgrst, 'reload schema';
