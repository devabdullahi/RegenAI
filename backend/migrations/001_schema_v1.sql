-- RegenAI Schema v1
-- Run this in Supabase SQL Editor

-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ============================================
-- TABLES
-- ============================================

-- Users (extends Supabase auth.users)
create table public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'farmer' check (role in ('farmer', 'admin')),
  created_at timestamptz not null default now()
);

-- Farms
create table public.farms (
  id uuid primary key default uuid_generate_v4(),
  user_id uuid not null references public.users(id) on delete cascade,
  name text not null,
  state text not null,
  county_fips text not null,
  total_acres numeric not null check (total_acres > 0),
  goals text check (goals in ('cost_savings', 'carbon_credits', 'both')),
  created_at timestamptz not null default now()
);

-- Fields
create table public.fields (
  id uuid primary key default uuid_generate_v4(),
  farm_id uuid not null references public.farms(id) on delete cascade,
  name text not null,
  acres numeric not null check (acres > 0),
  crop_type text not null,
  boundary_geojson jsonb,
  boundary_description text,
  practices text[] default '{}',
  created_at timestamptz not null default now()
);

-- Soil Profiles
create table public.soil_profiles (
  id uuid primary key default uuid_generate_v4(),
  field_id uuid not null references public.fields(id) on delete cascade,
  ssurgo_map_unit text not null,
  texture text not null,
  ph numeric not null,
  organic_matter_pct numeric not null,
  source text not null default 'ssurgo' check (source in ('ssurgo', 'soilgrids', 'manual')),
  fetched_at timestamptz not null default now()
);

-- Weather Cache
create table public.weather_cache (
  id uuid primary key default uuid_generate_v4(),
  field_id uuid not null references public.fields(id) on delete cascade,
  date date not null,
  temp_high numeric not null,
  temp_low numeric not null,
  precip_mm numeric not null default 0,
  soil_temp numeric,
  fetched_at timestamptz not null default now(),
  unique(field_id, date)
);

-- Recommendations
create table public.recommendations (
  id uuid primary key default uuid_generate_v4(),
  field_id uuid not null references public.fields(id) on delete cascade,
  created_at timestamptz not null default now(),
  practice_code text not null,
  title text not null,
  rationale text not null,
  priority text not null default 'medium' check (priority in ('high', 'medium', 'low')),
  status text not null default 'pending' check (status in ('pending', 'acted', 'dismissed'))
);

-- Credit Eligibility
create table public.credit_eligibility (
  id uuid primary key default uuid_generate_v4(),
  farm_id uuid not null references public.farms(id) on delete cascade,
  program text not null check (program in ('EQIP', 'VCM')),
  status text not null default 'pending_review' check (status in ('eligible', 'not_eligible', 'pending_review')),
  practices_documented text[] default '{}',
  notes text default '',
  updated_at timestamptz not null default now()
);

-- Documents
create table public.documents (
  id uuid primary key default uuid_generate_v4(),
  farm_id uuid not null references public.farms(id) on delete cascade,
  storage_path text not null,
  doc_type text not null check (doc_type in ('soil_report', 'field_photo', 'compliance', 'other')),
  uploaded_at timestamptz not null default now()
);

-- EQIP Practice Codes (reference data)
create table public.eqip_practices (
  code text primary key,
  name text not null,
  description text,
  category text,
  unit text,
  created_at timestamptz not null default now()
);

-- ============================================
-- INDEXES
-- ============================================

create index idx_farms_user_id on public.farms(user_id);
create index idx_fields_farm_id on public.fields(farm_id);
create index idx_soil_profiles_field_id on public.soil_profiles(field_id);
create index idx_weather_cache_field_id on public.weather_cache(field_id);
create index idx_weather_cache_date on public.weather_cache(field_id, date);
create index idx_recommendations_field_id on public.recommendations(field_id);
create index idx_credit_eligibility_farm_id on public.credit_eligibility(farm_id);
create index idx_documents_farm_id on public.documents(farm_id);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- Critical: ensures farm data isolation
-- ============================================

alter table public.users enable row level security;
alter table public.farms enable row level security;
alter table public.fields enable row level security;
alter table public.soil_profiles enable row level security;
alter table public.weather_cache enable row level security;
alter table public.recommendations enable row level security;
alter table public.credit_eligibility enable row level security;
alter table public.documents enable row level security;

-- Users: can only see/edit their own record
create policy "Users can view own record" on public.users
  for select using (auth.uid() = id);
create policy "Users can update own record" on public.users
  for update using (auth.uid() = id);

-- Farms: users can only access their own farms
create policy "Users can view own farms" on public.farms
  for select using (auth.uid() = user_id);
create policy "Users can create own farms" on public.farms
  for insert with check (auth.uid() = user_id);
create policy "Users can update own farms" on public.farms
  for update using (auth.uid() = user_id);
create policy "Users can delete own farms" on public.farms
  for delete using (auth.uid() = user_id);

-- Fields: access through farm ownership
create policy "Users can view own fields" on public.fields
  for select using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );
create policy "Users can create fields in own farms" on public.fields
  for insert with check (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );
create policy "Users can update own fields" on public.fields
  for update using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );
create policy "Users can delete own fields" on public.fields
  for delete using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );

-- Soil profiles: access through field → farm ownership
create policy "Users can view own soil profiles" on public.soil_profiles
  for select using (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );

-- Weather cache: access through field → farm ownership
create policy "Users can view own weather" on public.weather_cache
  for select using (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );

-- Recommendations: access through field → farm ownership
create policy "Users can view own recommendations" on public.recommendations
  for select using (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );
create policy "Users can update own recommendation status" on public.recommendations
  for update using (
    field_id in (
      select f.id from public.fields f
      join public.farms fa on f.farm_id = fa.id
      where fa.user_id = auth.uid()
    )
  );

-- Credit eligibility: access through farm ownership
create policy "Users can view own credit eligibility" on public.credit_eligibility
  for select using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );

-- Documents: access through farm ownership
create policy "Users can view own documents" on public.documents
  for select using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );
create policy "Users can upload documents to own farms" on public.documents
  for insert with check (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );
create policy "Users can delete own documents" on public.documents
  for delete using (
    farm_id in (select id from public.farms where user_id = auth.uid())
  );

-- EQIP practices: public read (reference data)
alter table public.eqip_practices enable row level security;
create policy "Anyone can read EQIP practices" on public.eqip_practices
  for select using (true);

-- ============================================
-- AUTO-CREATE USER ON SIGNUP
-- ============================================

create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.users (id, email)
  values (new.id, new.email);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
