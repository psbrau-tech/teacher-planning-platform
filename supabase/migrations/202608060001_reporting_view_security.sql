-- Ensure reporting views honor the querying user's permissions and RLS policies.
-- PostgreSQL 15+ supports security_invoker views directly.

alter view public.school_admin_usage_summary
  set (security_invoker = true);

alter view public.school_ai_cost_summary
  set (security_invoker = true);
