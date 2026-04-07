-- ============================================================
-- Migration 005: Field Activity Log
-- Per-field event recording for farmers: planting, spraying,
-- fertilizing, scouting, harvest, tillage, cover crop, other.
-- Includes legally required pesticide application records (FIFRA)
-- and APH yield history for crop insurance tracking.
-- ============================================================

-- ============================================================
-- SECTION 1: SCHEMA ADDITIONS TO fields TABLE
-- ============================================================

-- FSA farm/tract/field numbers for government program linkage
ALTER TABLE public.fields
    ADD COLUMN IF NOT EXISTS fsa_farm_number  TEXT,
    ADD COLUMN IF NOT EXISTS fsa_tract_number TEXT,
    ADD COLUMN IF NOT EXISTS fsa_field_number TEXT;

-- ============================================================
-- SECTION 2: CORE ACTIVITY LOG TABLE
-- ============================================================

CREATE TABLE public.field_activities (
    -- Primary key
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership
    field_id            UUID        NOT NULL REFERENCES public.fields(id) ON DELETE CASCADE,

    -- Activity classification
    activity_type       TEXT        NOT NULL
                            CHECK (activity_type IN (
                                'plant', 'spray', 'fertilize', 'scout',
                                'harvest', 'tillage', 'cover_crop', 'other'
                            )),
    activity_date       DATE        NOT NULL,

    -- ---------------------------------------------------------
    -- Planting fields
    -- ---------------------------------------------------------
    seed_variety        TEXT,                       -- e.g. "Pioneer P0574AMXT"
    seeding_rate        NUMERIC,                    -- seeds/acre or lbs/acre
    seeding_rate_unit   TEXT
                            CHECK (seeding_rate_unit IN (
                                'seeds_per_acre', 'lbs_per_acre'
                            ) OR seeding_rate_unit IS NULL),
    row_spacing         NUMERIC,                    -- inches
    planting_depth      NUMERIC,                    -- inches

    -- ---------------------------------------------------------
    -- Spray / chemical application fields
    -- Required by FIFRA for restricted use pesticides
    -- ---------------------------------------------------------
    product_name        TEXT,                       -- e.g. "Roundup PowerMax 3"
    epa_reg_number      TEXT,                       -- EPA registration number
    rate_per_acre       NUMERIC,                    -- oz/acre, lbs/acre, gal/acre
    rate_unit           TEXT
                            CHECK (rate_unit IN (
                                'oz_per_acre', 'lbs_per_acre', 'gal_per_acre'
                            ) OR rate_unit IS NULL),
    target_pest         TEXT,                       -- what is being controlled
    wind_speed_mph      NUMERIC,
    wind_direction      TEXT,
    temperature_f       NUMERIC,
    applicator_name     TEXT,                       -- required for RUP records
    applicator_license  TEXT,                       -- certification number
    restricted_use      BOOLEAN     NOT NULL DEFAULT FALSE,

    -- ---------------------------------------------------------
    -- Fertilizer application fields
    -- ---------------------------------------------------------
    nutrient_n_lbs      NUMERIC,                    -- lbs N/acre applied
    nutrient_p_lbs      NUMERIC,                    -- lbs P2O5/acre applied
    nutrient_k_lbs      NUMERIC,                    -- lbs K2O/acre applied
    application_method  TEXT
                            CHECK (application_method IN (
                                'broadcast', 'injected', 'foliar',
                                'sidedress', 'starter'
                            ) OR application_method IS NULL),

    -- ---------------------------------------------------------
    -- Scouting / field observation fields
    -- ---------------------------------------------------------
    pest_type           TEXT
                            CHECK (pest_type IN (
                                'insect', 'disease', 'weed', 'other'
                            ) OR pest_type IS NULL),
    pest_name           TEXT,                       -- e.g. "corn rootworm beetle"
    severity            TEXT
                            CHECK (severity IN (
                                'none', 'low', 'moderate', 'high', 'critical'
                            ) OR severity IS NULL),
    threshold_exceeded  BOOLEAN,

    -- ---------------------------------------------------------
    -- Harvest fields
    -- ---------------------------------------------------------
    yield_bu_acre       NUMERIC,                    -- bushels per acre
    moisture_pct        NUMERIC,                    -- moisture at delivery
    test_weight         NUMERIC,                    -- lbs/bu
    elevator_ticket     TEXT,                       -- grain elevator ticket number

    -- ---------------------------------------------------------
    -- Common / shared fields
    -- ---------------------------------------------------------
    acres_applied       NUMERIC,                    -- may differ from field total acres
    equipment_used      TEXT,
    operator            TEXT,
    cost_per_acre       NUMERIC,                    -- $ cost for this activity
    notes               TEXT,
    photos              TEXT[],                     -- Supabase storage paths
    weather_conditions  TEXT,                       -- brief weather note

    -- Audit timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- SECTION 3: YIELD HISTORY TABLE (APH tracking)
-- ============================================================

CREATE TABLE public.yield_history (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    field_id         UUID        NOT NULL REFERENCES public.fields(id) ON DELETE CASCADE,
    crop_year        INTEGER     NOT NULL,           -- e.g. 2025
    crop_type        TEXT        NOT NULL,
    yield_bu_acre    NUMERIC     NOT NULL,
    moisture_pct     NUMERIC,
    total_bushels    NUMERIC,
    acres_harvested  NUMERIC,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (field_id, crop_year)
);

-- ============================================================
-- SECTION 4: INDEXES
-- ============================================================

-- field_activities: primary query patterns
CREATE INDEX idx_field_activities_field_date
    ON public.field_activities(field_id, activity_date DESC);

CREATE INDEX idx_field_activities_field_type
    ON public.field_activities(field_id, activity_type);

CREATE INDEX idx_field_activities_date
    ON public.field_activities(activity_date);

-- Partial index for compliance queries — restricted use pesticide records
-- must be queryable quickly for FIFRA audit/reporting purposes
CREATE INDEX idx_field_activities_restricted_use
    ON public.field_activities(field_id, activity_date DESC)
    WHERE restricted_use = TRUE;

-- yield_history: most recent year first per field
CREATE INDEX idx_yield_history_field_year
    ON public.yield_history(field_id, crop_year DESC);

-- ============================================================
-- SECTION 5: UPDATED_AT TRIGGER
-- ============================================================

-- set_updated_at() function is already defined in migration 003.
-- Apply it to field_activities only (yield_history has no updated_at column).

CREATE TRIGGER trg_field_activities_updated_at
    BEFORE UPDATE ON public.field_activities
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ============================================================
-- SECTION 6: ROW LEVEL SECURITY
-- Access chain: field_activities -> fields -> farms -> user_id
-- Matches the soil_profiles / weather_cache pattern from migration 001.
-- ============================================================

ALTER TABLE public.field_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.yield_history    ENABLE ROW LEVEL SECURITY;

-- Helper subquery shared across policies:
-- Resolves field_id -> farm ownership for the current user.
-- Inline for compatibility with Supabase RLS (no functions in policies).

-- field_activities: SELECT
CREATE POLICY "Users can view own field activities"
    ON public.field_activities FOR SELECT
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- field_activities: INSERT
CREATE POLICY "Users can insert field activities for own fields"
    ON public.field_activities FOR INSERT
    WITH CHECK (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- field_activities: UPDATE
CREATE POLICY "Users can update own field activities"
    ON public.field_activities FOR UPDATE
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- field_activities: DELETE
CREATE POLICY "Users can delete own field activities"
    ON public.field_activities FOR DELETE
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- yield_history: SELECT
CREATE POLICY "Users can view own yield history"
    ON public.yield_history FOR SELECT
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- yield_history: INSERT
CREATE POLICY "Users can insert yield history for own fields"
    ON public.yield_history FOR INSERT
    WITH CHECK (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- yield_history: UPDATE
CREATE POLICY "Users can update own yield history"
    ON public.yield_history FOR UPDATE
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );

-- yield_history: DELETE
CREATE POLICY "Users can delete own yield history"
    ON public.yield_history FOR DELETE
    USING (
        field_id IN (
            SELECT f.id
            FROM   public.fields f
            JOIN   public.farms  fa ON f.farm_id = fa.id
            WHERE  fa.user_id = auth.uid()
        )
    );
