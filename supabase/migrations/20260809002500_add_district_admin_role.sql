-- Add a governed district administrator role as a separate enum migration.
-- PostgreSQL requires a newly added enum value to commit before later migrations
-- safely reference it in functions, policies, or casts.

alter type public.app_role add value if not exists 'district_admin';

comment on type public.app_role is
  'Governed TPP roles: teacher, school_admin, district_admin, and platform_admin.';
