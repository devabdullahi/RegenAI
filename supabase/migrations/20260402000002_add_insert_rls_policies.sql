-- Add missing INSERT RLS policies for derived tables
-- These allow the authenticated user's Supabase client to insert records
-- for fields they own (through the farm ownership chain).

-- Soil profiles: insert through field → farm ownership
create policy "Users can insert soil profiles for own fields" on public.soil_profiles
  for insert with check (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );

-- Weather cache: insert through field → farm ownership
create policy "Users can insert weather for own fields" on public.weather_cache
  for insert with check (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );

-- Recommendations: insert through field → farm ownership
create policy "Users can insert recommendations for own fields" on public.recommendations
  for insert with check (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );

-- Credit eligibility: insert through farm ownership
create policy "Users can insert credit eligibility for own farms" on public.credit_eligibility
  for insert with check (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );

-- Credit eligibility: update through farm ownership
create policy "Users can update own credit eligibility" on public.credit_eligibility
  for update using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );

-- Add unique constraint for credit_eligibility upsert (used by eqip.py and vcm.py)
alter table public.credit_eligibility
  add constraint credit_eligibility_farm_program_unique unique (farm_id, program);
