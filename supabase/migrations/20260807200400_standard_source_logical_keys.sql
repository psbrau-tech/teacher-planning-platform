-- Gate E: source_key identifies a logical authoritative source across editions.
-- Do not encode the currently observed publication year in the stable source identifier.

update public.standard_sources
set source_key = 'alabama_academic_english_language_arts',
    updated_at = now()
where source_key = 'alabama_ela_2021';

update public.standard_sources
set source_key = 'alabama_cte_cos_business_management_administration',
    updated_at = now()
where source_key = 'alabama_bma_2021';

notify pgrst, 'reload schema';
