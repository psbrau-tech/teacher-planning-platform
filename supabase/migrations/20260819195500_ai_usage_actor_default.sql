-- Restore teacher AI-planning usage logging after actor-aware RLS was introduced.
--
-- The governed actor policy requires actor_id = auth.uid() for every authenticated
-- AI usage insert. Existing teacher-planning callers predate actor_id and therefore
-- omit the column. Derive the actor from the authenticated database session by
-- default so those callers remain compatible without weakening the RLS check or
-- trusting client-supplied identity data.

alter table public.ai_usage_events
  alter column actor_id set default auth.uid();

comment on column public.ai_usage_events.actor_id is
  'Governed professional user who invoked the AI feature. Defaults to the authenticated user for legacy governed callers; RLS independently requires actor_id = auth.uid().';

notify pgrst, 'reload schema';
