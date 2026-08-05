create unique index if not exists districts_name_unique
  on public.districts (name);

create unique index if not exists schools_district_name_unique
  on public.schools (district_id, name);

create unique index if not exists academic_years_school_name_unique
  on public.academic_years (school_id, name);
