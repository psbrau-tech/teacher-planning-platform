-- Provide period-scoped professional planning activity totals for the administration UI.
-- Configuration counts remain current-state counts; weekly activity, validation, carry-forward,
-- and document totals are constrained to the requested planning period.

create or replace function public.admin_usage_for_period(
  target_start date,
  target_end date,
  target_school_id uuid
)
returns table (
  school_id uuid,
  teachers_configured bigint,
  teachers_with_assignments bigint,
  assignments_configured bigint,
  weekly_plans_created bigint,
  weekly_plans_approved bigint,
  instruction_records_validated bigint,
  lessons_carried_forward bigint,
  documents_requested bigint,
  documents_generated bigint,
  document_generation_failures bigint
)
language sql
stable
security invoker
set search_path = ''
as $$
  with teacher_summary as (
    select count(distinct pr.profile_id)::bigint as teachers_configured
    from public.profile_roles pr
    join public.profiles p on p.id = pr.profile_id
    where pr.school_id = target_school_id
      and pr.role = 'teacher'
      and p.is_active
  ),
  assignment_summary as (
    select
      count(distinct ta.teacher_id)::bigint as teachers_with_assignments,
      count(distinct ta.id)::bigint as assignments_configured
    from public.teaching_assignments ta
    where ta.school_id = target_school_id
      and ta.is_active
  ),
  weekly_summary as (
    select
      count(distinct w.id)::bigint as weekly_plans_created,
      count(distinct w.id) filter (where w.approved_at is not null)::bigint as weekly_plans_approved
    from public.teaching_assignments ta
    join public.weekly_plan_snapshots w on w.teaching_assignment_id = ta.id
    where ta.school_id = target_school_id
      and w.week_start between target_start and target_end
  ),
  instruction_summary as (
    select
      count(distinct ir.id)::bigint as instruction_records_validated,
      count(distinct ir.id) filter (where ir.carry_forward_action = 'carry_forward')::bigint as lessons_carried_forward
    from public.teaching_assignments ta
    join public.scheduled_lessons sl on sl.teaching_assignment_id = ta.id
    join public.instruction_records ir on ir.scheduled_lesson_id = sl.id
    where ta.school_id = target_school_id
      and sl.school_date between target_start and target_end
  ),
  document_summary as (
    select
      count(distinct gd.id)::bigint as documents_requested,
      count(distinct gd.id) filter (where gd.status = 'generated')::bigint as documents_generated,
      count(distinct gd.id) filter (where gd.status = 'failed')::bigint as document_generation_failures
    from public.teaching_assignments ta
    join public.weekly_plan_snapshots w on w.teaching_assignment_id = ta.id
    join public.generated_documents gd on gd.weekly_plan_snapshot_id = w.id
    where ta.school_id = target_school_id
      and w.week_start between target_start and target_end
  )
  select
    target_school_id,
    coalesce(t.teachers_configured, 0),
    coalesce(a.teachers_with_assignments, 0),
    coalesce(a.assignments_configured, 0),
    coalesce(w.weekly_plans_created, 0),
    coalesce(w.weekly_plans_approved, 0),
    coalesce(i.instruction_records_validated, 0),
    coalesce(i.lessons_carried_forward, 0),
    coalesce(d.documents_requested, 0),
    coalesce(d.documents_generated, 0),
    coalesce(d.document_generation_failures, 0)
  from teacher_summary t
  cross join assignment_summary a
  cross join weekly_summary w
  cross join instruction_summary i
  cross join document_summary d;
$$;

revoke all on function public.admin_usage_for_period(date, date, uuid) from public, anon;
grant execute on function public.admin_usage_for_period(date, date, uuid) to authenticated;

comment on function public.admin_usage_for_period(date, date, uuid) is
  'Period-scoped educator planning activity summary; configuration counts remain current state.';