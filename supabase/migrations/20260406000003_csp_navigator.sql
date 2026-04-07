-- ============================================================
-- Migration 003: CSP Navigator
-- Conservation Stewardship Program data model for RegenAI
-- ============================================================

-- ============================================================
-- SECTION 1: NEW REFERENCE / LOOKUP TABLES
-- ============================================================

-- Resource concern categories (8 NRCS priority areas for Midwest cropland)
CREATE TABLE public.csp_resource_concerns (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code          TEXT NOT NULL UNIQUE,   -- e.g. 'SOIL_EROSION'
    name          TEXT NOT NULL,          -- e.g. 'Soil Erosion'
    description   TEXT NOT NULL,
    max_points    INTEGER NOT NULL,       -- Max ranking points this concern contributes
    display_order INTEGER NOT NULL,
    is_priority   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Master reference table for all CSP enhancement activity codes (Midwest row crops)
CREATE TABLE public.csp_enhancement_activities (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                  TEXT NOT NULL UNIQUE,          -- e.g. 'E328A'
    name                  TEXT NOT NULL,                 -- e.g. 'Resource conserving crop rotation'
    category              TEXT NOT NULL,                 -- One of the 8 resource concern category names
    land_use              TEXT NOT NULL DEFAULT 'cropland',
                            -- 'cropland' | 'pasture' | 'forest' | 'all'
    description           TEXT NOT NULL,
    implementation_notes  TEXT,
    base_payment_rate     NUMERIC(8,2),                  -- National avg $ per unit; state overrides in payment rates table
    payment_unit          TEXT NOT NULL DEFAULT 'acre',  -- 'acre' | 'foot' | 'each' | 'acre-inch'
    is_bundle_eligible    BOOLEAN NOT NULL DEFAULT FALSE,
    bundle_code           TEXT,                          -- e.g. 'B000CPL24'
    resource_concern_code TEXT NOT NULL REFERENCES public.csp_resource_concerns(code),
    eqip_practice_code    TEXT,                          -- Corresponding EQIP practice code if applicable
    point_weight          INTEGER NOT NULL DEFAULT 5 CHECK (point_weight BETWEEN 1 AND 20),
    active                BOOLEAN NOT NULL DEFAULT TRUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- State-level per-acre payment rates for existing activities and enhancement multipliers
CREATE TABLE public.csp_state_payment_rates (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code              TEXT NOT NULL,    -- 2-letter abbreviation: 'IA', 'IL', etc.
    fiscal_year             INTEGER NOT NULL, -- e.g. 2025
    cropland_eap_per_rc     NUMERIC(8,2) NOT NULL,  -- $ per acre per resource concern above threshold
    pasture_eap_per_rc      NUMERIC(8,2),
    forest_eap_per_rc       NUMERIC(8,2),
    min_annual_payment      NUMERIC(10,2) NOT NULL DEFAULT 4000.00,
    max_annual_payment      NUMERIC(10,2) NOT NULL DEFAULT 50000.00,
    max_contract_payment    NUMERIC(10,2) NOT NULL DEFAULT 200000.00,
    enhancement_payment_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,  -- 100% standard
    bundle_payment_pct      NUMERIC(5,2) NOT NULL DEFAULT 115.00,  -- 115% for bundles
    act_now_threshold_score INTEGER,          -- Minimum score for immediate ACT NOW approval
    ranking_cutoff_date_1   DATE,
    ranking_cutoff_date_2   DATE,
    ranking_cutoff_date_3   DATE,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(state_code, fiscal_year)
);

-- Upcoming CSP application cutoff dates by state (pre-seeded, admin-updated)
CREATE TABLE public.csp_application_deadlines (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state_code    TEXT NOT NULL,
    fiscal_year   INTEGER NOT NULL,
    cutoff_date   DATE NOT NULL,
    cutoff_name   TEXT NOT NULL,     -- e.g. 'FY2025 First Cutoff', 'ACT NOW Window'
    is_act_now    BOOLEAN NOT NULL DEFAULT FALSE,
    act_now_start DATE,
    act_now_end   DATE,
    description   TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(state_code, fiscal_year, cutoff_name)
);

-- ============================================================
-- SECTION 2: FARM-SPECIFIC CSP TABLES
-- ============================================================

-- CSP eligibility assessment result per farm per fiscal year
-- One row per farm; upserted on re-evaluation
CREATE TABLE public.csp_eligibility_assessments (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id                     UUID NOT NULL REFERENCES public.farms(id) ON DELETE CASCADE,
    fiscal_year                 INTEGER NOT NULL DEFAULT 2025,
    evaluated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Eligibility determination
    is_eligible                 BOOLEAN,   -- NULL = not yet evaluated
    eligibility_status          TEXT NOT NULL DEFAULT 'not_evaluated'
                                    CHECK (eligibility_status IN (
                                        'not_evaluated', 'eligible',
                                        'not_eligible', 'conditional'
                                    )),
    ineligibility_reasons       TEXT[],    -- Reason codes when not_eligible

    -- Resource concern scoring
    resource_concerns_met       JSONB NOT NULL DEFAULT '[]',
        -- [{code, name, currently_met, threshold_met, score, points_earned}]
    rc_count_above_threshold    INTEGER NOT NULL DEFAULT 0,  -- RCs currently above threshold
    rc_count_will_meet          INTEGER NOT NULL DEFAULT 0,  -- RCs committed to meet by end of contract

    -- Stewardship ranking score (0-100)
    stewardship_score           INTEGER NOT NULL DEFAULT 0,
    estimated_ranking_score     INTEGER NOT NULL DEFAULT 0,

    -- Detected active practices from field data and recommendations
    active_enhancement_codes    TEXT[] NOT NULL DEFAULT '{}',
    qualifying_eqip_codes       TEXT[] NOT NULL DEFAULT '{}',

    -- ACT NOW eligibility
    act_now_eligible            BOOLEAN NOT NULL DEFAULT FALSE,
    act_now_threshold           INTEGER,   -- State threshold at time of evaluation

    -- Payment estimate
    estimated_annual_payment    NUMERIC(10,2),
    estimated_5yr_payment       NUMERIC(10,2),
    payment_calculation_detail  JSONB,     -- Breakdown: EAP + EnAP components

    -- Application readiness
    application_readiness_pct   INTEGER NOT NULL DEFAULT 0 CHECK (application_readiness_pct BETWEEN 0 AND 100),
    missing_requirements        TEXT[],

    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(farm_id, fiscal_year)
);

-- Enhancement selections and commitments per farm (used to build payment estimates)
CREATE TABLE public.csp_farm_enhancements (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farm_id           UUID NOT NULL REFERENCES public.farms(id) ON DELETE CASCADE,
    enhancement_code  TEXT NOT NULL REFERENCES public.csp_enhancement_activities(code),
    field_id          UUID REFERENCES public.fields(id) ON DELETE SET NULL,
    status            TEXT NOT NULL DEFAULT 'considering'
                          CHECK (status IN ('considering', 'committed', 'active', 'removed')),
    acres_enrolled    NUMERIC(10,2),
    estimated_payment NUMERIC(10,2),
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(farm_id, enhancement_code, field_id)
);

-- ============================================================
-- SECTION 3: MODIFICATIONS TO EXISTING TABLES
-- ============================================================

-- farms: CSP enrollment and contract tracking
ALTER TABLE public.farms
    ADD COLUMN IF NOT EXISTS csp_enrolled          BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS csp_contract_start    DATE,
    ADD COLUMN IF NOT EXISTS csp_contract_end      DATE,
    ADD COLUMN IF NOT EXISTS csp_contract_id       TEXT,   -- NRCS-assigned contract number
    ADD COLUMN IF NOT EXISTS csp_last_evaluated_at TIMESTAMPTZ;

-- fields: tillage, cover crop, and nutrient management detail
ALTER TABLE public.fields
    ADD COLUMN IF NOT EXISTS tillage_practice    TEXT
                                 CHECK (tillage_practice IN (
                                     'no_till', 'reduced_till',
                                     'conventional', 'strip_till'
                                 )),
    ADD COLUMN IF NOT EXISTS cover_crop_species  TEXT[],           -- e.g. ARRAY['cereal rye', 'hairy vetch']
    ADD COLUMN IF NOT EXISTS nutrient_mgmt_plan  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS csp_enrolled_acres  NUMERIC(10,2);

-- recommendations: link recs to CSP enhancements and score impact
ALTER TABLE public.recommendations
    ADD COLUMN IF NOT EXISTS csp_enhancement_code TEXT,    -- e.g. 'E328A'
    ADD COLUMN IF NOT EXISTS csp_points_impact    INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS csp_payment_impact   NUMERIC(10,2);

-- credit_eligibility: extend program check to include CSP
ALTER TABLE public.credit_eligibility
    DROP CONSTRAINT IF EXISTS credit_eligibility_program_check;

ALTER TABLE public.credit_eligibility
    ADD CONSTRAINT credit_eligibility_program_check
    CHECK (program IN ('EQIP', 'VCM', 'CSP'));

-- ============================================================
-- SECTION 4: INDEXES
-- ============================================================

-- csp_enhancement_activities
CREATE INDEX idx_csp_enhancements_category
    ON public.csp_enhancement_activities(category);
CREATE INDEX idx_csp_enhancements_land_use
    ON public.csp_enhancement_activities(land_use);
CREATE INDEX idx_csp_enhancements_eqip_code
    ON public.csp_enhancement_activities(eqip_practice_code);
CREATE INDEX idx_csp_enhancements_resource_concern
    ON public.csp_enhancement_activities(resource_concern_code);
CREATE INDEX idx_csp_enhancements_active
    ON public.csp_enhancement_activities(active) WHERE active = TRUE;

-- csp_state_payment_rates
CREATE INDEX idx_csp_state_rates_state
    ON public.csp_state_payment_rates(state_code);
CREATE INDEX idx_csp_state_rates_fy
    ON public.csp_state_payment_rates(fiscal_year);

-- csp_application_deadlines
CREATE INDEX idx_csp_deadlines_state
    ON public.csp_application_deadlines(state_code);
CREATE INDEX idx_csp_deadlines_date
    ON public.csp_application_deadlines(cutoff_date);
CREATE INDEX idx_csp_deadlines_active
    ON public.csp_application_deadlines(is_active, cutoff_date) WHERE is_active = TRUE;

-- csp_eligibility_assessments
CREATE INDEX idx_csp_eligibility_farm
    ON public.csp_eligibility_assessments(farm_id);
CREATE INDEX idx_csp_eligibility_status
    ON public.csp_eligibility_assessments(eligibility_status);
CREATE INDEX idx_csp_eligibility_fy
    ON public.csp_eligibility_assessments(fiscal_year);

-- csp_farm_enhancements
CREATE INDEX idx_csp_farm_enhancements_farm
    ON public.csp_farm_enhancements(farm_id);
CREATE INDEX idx_csp_farm_enhancements_status
    ON public.csp_farm_enhancements(status);
CREATE INDEX idx_csp_farm_enhancements_field
    ON public.csp_farm_enhancements(field_id);

-- ============================================================
-- SECTION 5: ROW LEVEL SECURITY
-- ============================================================

-- Reference tables: public read, no user writes
ALTER TABLE public.csp_resource_concerns ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.csp_enhancement_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.csp_state_payment_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.csp_application_deadlines ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can read CSP resource concerns"
    ON public.csp_resource_concerns FOR SELECT USING (true);

CREATE POLICY "Anyone can read CSP enhancement activities"
    ON public.csp_enhancement_activities FOR SELECT USING (true);

CREATE POLICY "Anyone can read CSP state payment rates"
    ON public.csp_state_payment_rates FOR SELECT USING (true);

CREATE POLICY "Anyone can read CSP application deadlines"
    ON public.csp_application_deadlines FOR SELECT USING (true);

-- Farm-scoped tables: access through farm ownership chain
ALTER TABLE public.csp_eligibility_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.csp_farm_enhancements ENABLE ROW LEVEL SECURITY;

-- csp_eligibility_assessments
CREATE POLICY "Users can view own CSP eligibility assessments"
    ON public.csp_eligibility_assessments FOR SELECT
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert CSP eligibility assessments for own farms"
    ON public.csp_eligibility_assessments FOR INSERT
    WITH CHECK (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

CREATE POLICY "Users can update own CSP eligibility assessments"
    ON public.csp_eligibility_assessments FOR UPDATE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

CREATE POLICY "Users can delete own CSP eligibility assessments"
    ON public.csp_eligibility_assessments FOR DELETE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

-- csp_farm_enhancements
CREATE POLICY "Users can view own CSP farm enhancements"
    ON public.csp_farm_enhancements FOR SELECT
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

CREATE POLICY "Users can insert CSP farm enhancements for own farms"
    ON public.csp_farm_enhancements FOR INSERT
    WITH CHECK (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

CREATE POLICY "Users can update own CSP farm enhancements"
    ON public.csp_farm_enhancements FOR UPDATE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

CREATE POLICY "Users can delete own CSP farm enhancements"
    ON public.csp_farm_enhancements FOR DELETE
    USING (farm_id IN (SELECT id FROM public.farms WHERE user_id = auth.uid()));

-- ============================================================
-- SECTION 6: UPDATED_AT TRIGGER FUNCTION (shared utility)
-- ============================================================

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_csp_eligibility_updated_at
    BEFORE UPDATE ON public.csp_eligibility_assessments
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE TRIGGER trg_csp_farm_enhancements_updated_at
    BEFORE UPDATE ON public.csp_farm_enhancements
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
