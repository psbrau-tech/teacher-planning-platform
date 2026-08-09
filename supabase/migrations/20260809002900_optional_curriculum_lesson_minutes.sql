-- Curriculum lesson duration is optional. When omitted, weekly planning derives
-- instructional minutes from the teaching assignment's meeting pattern.
-- Existing explicit durations remain valid overrides for multi-meeting or
-- shortened lessons.

alter table public.lessons
  alter column estimated_minutes drop not null;
