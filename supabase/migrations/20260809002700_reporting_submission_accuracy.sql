-- Keep the existing school usage summary accurate after explicit submission is introduced.
-- A plan edited after submission is a draft again and is not counted as currently submitted.

create or replace view public.school_admin_usage_summary
with (security_invoker = true)
as
with teacher_summary as (
  select
    pr.school_id,
    count(distinct pr.profile_id) as teachers_configured
  from public.profile_roles pr
  join public.profiles p on p.id = pr.profile_id
  where pr.role = 'teacher'
    and p.is_active
  group by pr.school_id
),
assignment_summary as (
  select
    ta.school_id,
    count(distinct ta.teacher_id) as teachers_with_assignments,
    count(distinct ta.id) as assignments_configured
  from public.teaching_assignments ta
  group by ta.school_id
),
weekly_summary as (
  select
    ta.school_id,
    count(distinct w.id) as weekly_plans_created,
    count(distinct w.id) filter (
      where w.approved_at is not null and not w.is_draft
    ) as weekly_plans_approved
  from public.teaching_assignments ta
  left join public.weekly_plan_snapshots w on w.teaching_assignment_id = ta.id
  group by ta.school_id
),
instruction_summary as (
  select
    ta.school_id,
    count(distinct ir.id) as instruction_records_validated,
    count(distinct ir.id) filter (
      where ir.carry_forward_action = 'carry_forward'
    ) as lessons_carried_forward
  from public.teaching_assignments ta
  left join public.scheduled_lessons sl on sl.teaching_assignment_id = ta.id
  left join public.instruction_records ir on ir.scheduled_lesson_id = sl.id
  group by ta.school_id
),
document_summary as (
  select
    ta.school_id,
    count(distinct gd.id) as documents_requested,
    count(distinct gd.id) filter (where gd.status = 'generated') as documents_generated,
    count(distinct gd.id) filter (where gd.status = 'failed') as document_generation_failures
  from public.teaching_assignments ta
  left join public.weekly_plan_snapshots w on w.teaching_assignment_id = ta.id
  left join public.generated_documents gd on gd.weekly_plan_snapshot_id = w.id
  group by ta.school_id
)
select
  s.id as school_id,
  coalesce(ts.teachers_configured, 0)::bigint as teachers_configured,
  coalesce(a.teachers_with_assignments, 0)::bigint as teachers_with_assignments,
  coalesce(a.assignments_configured, 0)::bigint as assignments_configured,
  coalesce(w.weekly_plans_created, 0)::bigint as weekly_plans_created,
  coalesce(w.weekly_plans_approved, 0)::bigint as weekly_plans_approved,
  coalesce(i.instruction_records_validated, 0)::bigint as instruction_records_validated,
  coalesce(i.lessons_carried_forward, 0)::bigint as lessons_carried_forward,
  coalesce(d.documents_requested, 0)::bigint as documents_requested,
  coalesce(d.documents_generated, 0)::bigint as documents_generated,
  coalesce(d.document_generation_failures, 0)::bigint as document_generation_failures
from public.schools s
left join teacher_summary ts on ts.school_id = s.id
left join assignment_summary a on a.school_id = s.id
left join weekly_summary w on w.school_id = s.id
left join instruction_summary i on i.school_id = s.id
left join document_summary d on d.school_id = s.id;

comment on view public.school_admin_usage_summary is
  'School-level professional planning usage summary; weekly_plans_approved counts only current explicitly submitted plan revisions.';
