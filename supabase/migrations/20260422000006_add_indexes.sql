-- Performance indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_recommendations_field_status ON public.recommendations(field_id, status);
CREATE INDEX IF NOT EXISTS idx_soil_profiles_field_fetched ON public.soil_profiles(field_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_weather_cache_field_date_desc ON public.weather_cache(field_id, date DESC);
