-- ============================================================
-- Migration 007: CSP FY2026 activity model
--
-- Source: NRCS National Bulletin 440-26-2 (2025-12-17)
--   https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf
--   - Unique "E" enhancement codes are no longer used.
--   - Bundles and some structural/infrastructure practices are no longer offered.
--   - Single activity list; higher payments remain for cover crop, AGM, RCCR, IRCCR.
--   - No CSP payment limitation in FY2026; EAP is $4,000 per contract per year.
--
-- Approach (non-destructive):
--   * Existing E-code rows are NOT deleted or renamed. csp_farm_enhancements
--     has an FK to csp_enhancement_activities(code), and recommendations
--     stores codes as text, so old rows stay for referential integrity and
--     history. They are marked active = FALSE, is_deprecated = TRUE, and
--     point at their replacement via superseded_by.
--   * New activity rows are keyed by NRCS conservation practice standard code
--     (with RCCR/IRCCR suffixes under 328) and inserted as active.
--   * Per-acre rates on the new rows are pre-FY2026 estimates copied from the
--     retired enhancement rows (migration 004). They are flagged
--     rate_is_estimate = TRUE pending the FY2026 state payment schedule.
-- ============================================================

-- 1. New descriptive columns (all nullable / defaulted — safe for existing rows)
ALTER TABLE public.csp_enhancement_activities
    ADD COLUMN IF NOT EXISTS practice_standard_code  TEXT,
    ADD COLUMN IF NOT EXISTS higher_payment_category TEXT
        CHECK (higher_payment_category IS NULL
               OR higher_payment_category IN ('cover_crop', 'agm', 'rccr', 'irccr')),
    ADD COLUMN IF NOT EXISTS is_deprecated           BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS superseded_by           TEXT,
    ADD COLUMN IF NOT EXISTS rate_is_estimate        BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS rate_basis              TEXT,
    ADD COLUMN IF NOT EXISTS rules_as_of             DATE,
    ADD COLUMN IF NOT EXISTS rules_source_url        TEXT;

COMMENT ON COLUMN public.csp_enhancement_activities.code IS
    'Activity code. FY2026+: NRCS practice standard code (e.g. 340, 328-RCCR). Retired E-codes remain as deprecated rows.';
COMMENT ON COLUMN public.csp_enhancement_activities.is_bundle_eligible IS
    'Deprecated: CSP bundles are not offered starting FY2026 (NB 440-26-2).';
COMMENT ON COLUMN public.csp_enhancement_activities.bundle_code IS
    'Deprecated: CSP bundles are not offered starting FY2026 (NB 440-26-2).';
COMMENT ON COLUMN public.csp_state_payment_rates.max_annual_payment IS
    'Pre-FY2026 only. There is no CSP annual payment limitation in FY2026 (NB 440-26-2).';
COMMENT ON COLUMN public.csp_state_payment_rates.max_contract_payment IS
    'Pre-FY2026 contracts: $200,000 ($400,000 joint). FY2026+ contracts: $300,000 ($600,000 joint) (NB 440-26-2).';

-- 2. Insert FY2026 activity rows
INSERT INTO public.csp_enhancement_activities
    (code, name, category, land_use, description, implementation_notes,
     base_payment_rate, payment_unit, is_bundle_eligible, bundle_code,
     resource_concern_code, eqip_practice_code, point_weight, active,
     practice_standard_code, higher_payment_category, is_deprecated,
     rate_is_estimate, rate_basis, rules_as_of, rules_source_url)
VALUES
    ('340', 'Cover Crop', 'Soil Health and Organic Matter', 'cropland',
     'Plant a cover crop between cash crops to protect soil, scavenge nutrients, and build organic matter.',
     'Higher CSP payment category (cover crop activities). Implement to the practice standard.',
     9.00, 'acre', FALSE, NULL, 'SOIL_HEALTH', '340', 14, TRUE,
     '340', 'cover_crop', FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('328-RCCR', 'Conservation Crop Rotation — Resource Conserving Crop Rotation (RCCR)', 'Soil Health and Organic Matter', 'cropland',
     'Add a resource-conserving crop (e.g. small grain, grass, or legume) to the rotation beyond corn and soybeans.',
     'Higher CSP payment category (RCCR). Document the rotation plan.',
     2.50, 'acre', FALSE, NULL, 'SOIL_HEALTH', '328', 15, TRUE,
     '328', 'rccr', FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('328-IRCCR', 'Conservation Crop Rotation — Improved Resource Conserving Crop Rotation (IRCCR)', 'Soil Health and Organic Matter', 'cropland',
     'Improve an existing resource conserving crop rotation, for example by adding a perennial resource-conserving crop year.',
     'Higher CSP payment category (IRCCR). Document the rotation plan.',
     4.75, 'acre', FALSE, NULL, 'SOIL_HEALTH', '328', 18, TRUE,
     '328', 'irccr', FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('329', 'Residue and Tillage Management, No Till', 'Soil Erosion', 'cropland',
     'Limit soil disturbance to planting operations and keep crop residue on the surface year-round.',
     NULL,
     5.50, 'acre', FALSE, NULL, 'SOIL_EROSION', '329', 17, TRUE,
     '329', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('345', 'Residue and Tillage Management, Reduced Till', 'Soil Erosion', 'cropland',
     'Reduce tillage intensity and maintain surface residue cover after planting.',
     NULL,
     3.25, 'acre', FALSE, NULL, 'SOIL_EROSION', '345', 10, TRUE,
     '345', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('590', 'Nutrient Management', 'Water Quality', 'cropland',
     'Manage the source, rate, timing, and placement of nutrients to improve uptake and reduce losses.',
     NULL,
     0.80, 'acre', FALSE, NULL, 'WATER_QUALITY', '590', 12, TRUE,
     '590', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('595', 'Pest Management Conservation System', 'Plant Condition', 'cropland',
     'Use scouting and economic thresholds to guide pest control and reduce pesticide risk.',
     NULL,
     0.60, 'acre', FALSE, NULL, 'PLANT_CONDITION', '595', 9, TRUE,
     '595', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('449', 'Irrigation Water Management', 'Water Quantity', 'cropland',
     'Schedule irrigation from soil moisture or ET data to apply water only when crops need it.',
     NULL,
     8.75, 'acre', FALSE, NULL, 'WATER_QUANTITY', '449', 12, TRUE,
     '449', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('554', 'Drainage Water Management', 'Water Quantity', 'cropland',
     'Use control structures on subsurface drainage to manage the water table and reduce nutrient loss.',
     NULL,
     6.50, 'acre', FALSE, NULL, 'WATER_QUANTITY', '554', 12, TRUE,
     '554', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('393', 'Filter Strip', 'Water Quality', 'cropland',
     'Establish a strip of permanent vegetation between cropland and water to trap sediment and nutrients.',
     NULL,
     45.00, 'acre', FALSE, NULL, 'WATER_QUALITY', '393', 16, TRUE,
     '393', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('528', 'Prescribed Grazing', 'Animals', 'cropland',
     'Manage grazing timing, intensity, and rest. Advanced grazing management (AGM) activities are eligible for higher CSP payments.',
     'Higher CSP payment category (AGM).',
     7.50, 'acre', FALSE, NULL, 'ANIMALS', '528', 9, TRUE,
     '528', 'agm', FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'),
    ('374', 'Energy Efficient Agricultural Operation', 'Energy', 'cropland',
     'Reduce on-farm energy use, for example through grain dryer or pumping efficiency improvements.',
     NULL,
     1.25, 'acre', FALSE, NULL, 'ENERGY', '374', 5, TRUE,
     '374', NULL, FALSE, TRUE,
     'Pre-FY2026 estimate, pending FY2026 state payment schedule', '2025-12-17',
     'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf')
ON CONFLICT (code) DO NOTHING;

-- 3. Retire E-code rows (kept for FK integrity and history)
UPDATE public.csp_enhancement_activities AS a
SET active = FALSE,
    is_deprecated = TRUE,
    superseded_by = m.new_code,
    rules_as_of = '2025-12-17',
    rules_source_url = 'https://directives.nrcs.usda.gov/sites/default/files2/1765996417/NB%20440-26-2%20PGM%E2%80%93Fiscal%20Year%202026%20Financial%20Assistance%20Program%20Changes%20and%20Guidance.pdf'
FROM (VALUES
    ('E340A', '340'), ('E340B', '340'), ('E340E', '340'),
    ('E328A', '328-RCCR'), ('E328B', '328-IRCCR'),
    ('E329A', '329'), ('E329B', '329'),
    ('E345A', '345'),
    ('E590A', '590'), ('E590B', '590'), ('E590C', '590'), ('E590D', '590'), ('E511A', '590'),
    ('E595A', '595'), ('E595B', '595'),
    ('E449B', '449'),
    ('E449A', '554'),
    ('E393A', '393'),
    ('E528A', '528'),
    ('E374A', '374')
) AS m(old_code, new_code)
WHERE a.code = m.old_code;

-- Any remaining E-code rows with no FY2026 equivalent (e.g. E342A, E412A,
-- E380A, E484A, E512A) are retired without a replacement.
UPDATE public.csp_enhancement_activities
SET active = FALSE,
    is_deprecated = TRUE,
    rules_as_of = '2025-12-17'
WHERE code ~ '^E[0-9]{3}[A-Z]$'
  AND is_deprecated = FALSE;

CREATE INDEX IF NOT EXISTS idx_csp_enhancements_practice_standard
    ON public.csp_enhancement_activities(practice_standard_code);
