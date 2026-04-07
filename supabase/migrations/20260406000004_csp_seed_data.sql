-- ============================================================
-- Migration 004: CSP Navigator Seed Data
-- Reference data: resource concerns, enhancement activity codes,
-- state payment rates, and application deadline calendar.
-- All 7 target Midwest states: IA, IL, KS, NE, MO, IN, OH
-- ============================================================

-- ============================================================
-- 1. RESOURCE CONCERN CATEGORIES
-- ============================================================

INSERT INTO public.csp_resource_concerns
    (code, name, description, max_points, display_order, is_priority)
VALUES
    (
        'SOIL_HEALTH',
        'Soil Health and Organic Matter',
        'The ability of soil to function as a living ecosystem supporting crops, animals, and humans. Evaluated through organic matter percentage, biological activity, and soil structure.',
        22, 1, TRUE
    ),
    (
        'WATER_QUALITY',
        'Water Quality',
        'The condition of water as affected by agricultural practices. Includes nutrients (nitrate, phosphorus), sediment, and pesticide loading into surface and groundwater.',
        20, 2, TRUE
    ),
    (
        'SOIL_EROSION',
        'Soil Erosion',
        'The wearing away of soil by water, wind, or tillage. Evaluated by erosion prediction models (RUSLE2, WEPS) relative to the tolerable soil loss (T value).',
        18, 3, TRUE
    ),
    (
        'AIR_QUALITY',
        'Air Quality and Climate',
        'The impact of farming practices on greenhouse gas emissions (CO2, N2O, CH4), particulate matter, and volatile organic compounds.',
        12, 4, TRUE
    ),
    (
        'PLANT_CONDITION',
        'Plant Condition and Species Diversity',
        'The health, productivity, and diversity of plant communities on the operation including crop plants, cover crops, and non-crop vegetation.',
        10, 5, TRUE
    ),
    (
        'WATER_QUANTITY',
        'Water Quantity',
        'The amount of water available for crops and other uses, including irrigation efficiency, drainage management, and groundwater recharge.',
        8, 6, TRUE
    ),
    (
        'ENERGY',
        'Energy Efficiency',
        'The efficient use of energy on the farm operation, including grain drying, irrigation pumping, and on-farm fuel consumption. Reducing energy use lowers operating costs and GHG emissions.',
        5, 7, TRUE
    ),
    (
        'ANIMALS',
        'Animal Condition and Welfare',
        'The health, comfort, and welfare of livestock on the operation. Includes access to water, shade, and appropriate nutrition. Less relevant for pure row crop operations.',
        5, 8, FALSE
    )
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 2. CSP ENHANCEMENT ACTIVITY CODES (26 Midwest Row Crop Codes)
-- ============================================================

INSERT INTO public.csp_enhancement_activities
    (code, name, category, land_use, description, implementation_notes,
     base_payment_rate, payment_unit, is_bundle_eligible, bundle_code,
     resource_concern_code, eqip_practice_code, point_weight, active)
VALUES

    -- ---- SOIL HEALTH & ORGANIC MATTER ----
    (
        'E328A',
        'Resource conserving crop rotation',
        'Soil Health and Organic Matter', 'cropland',
        'Implement a resource-conserving crop rotation that includes at least one grass, legume, or small grain species in addition to corn and soybeans.',
        'Corn-soy-wheat or corn-soy-oats counts. Adding a hay crop (alfalfa) earns maximum score. Must document the rotation plan in writing.',
        2.50, 'acre', TRUE, 'B000CPL24', 'SOIL_HEALTH', '328', 15, TRUE
    ),
    (
        'E328B',
        'Improved resource conserving crop rotation',
        'Soil Health and Organic Matter', 'cropland',
        'Enhanced crop rotation that includes at least two years of a perennial forage crop within a 5-year rotation cycle.',
        'Alfalfa-corn-corn-soy-oats is an ideal sequence. Must document rotation plan. Pays more than E328A due to greater soil health benefit.',
        4.75, 'acre', TRUE, 'B000CPL24', 'SOIL_HEALTH', '328', 18, TRUE
    ),
    (
        'E340A',
        'Cover crop to suppress weeds',
        'Soil Health and Organic Matter', 'cropland',
        'Plant a cover crop mix specifically selected to suppress weed pressure and break pest cycles.',
        'Cereal rye is most common. Terminate at least 2 weeks before cash crop planting. Document species, seeding rate, and termination date.',
        9.00, 'acre', TRUE, 'B000CPL24', 'SOIL_HEALTH', '340', 14, TRUE
    ),
    (
        'E484A',
        'Mulching with cover crop termination residue',
        'Soil Health and Organic Matter', 'cropland',
        'Terminate cover crops by rolling or crimping (no herbicide) and plant directly into the rolled mulch layer to maintain maximum residue on the surface.',
        'Roller-crimper required. Best with cereal rye at anthesis (heading stage). Works well with soybeans. More challenging for corn. Eliminates herbicide cost for termination.',
        3.75, 'acre', FALSE, NULL, 'SOIL_HEALTH', NULL, 10, TRUE
    ),
    (
        'E528A',
        'Prescribed grazing plan for integrated crop-livestock system',
        'Soil Health and Organic Matter', 'cropland',
        'Develop and implement a prescribed grazing plan that integrates livestock into the cropland system through cover crop grazing or crop residue grazing.',
        'Applicable to farms with livestock or those willing to host stocker cattle. Must limit compaction risk — no grazing on saturated soils. Document grazing dates and stocking rates.',
        7.50, 'acre', FALSE, NULL, 'SOIL_HEALTH', '528', 9, TRUE
    ),

    -- ---- SOIL EROSION ----
    (
        'E340B',
        'Cover crop to reduce soil erosion',
        'Soil Erosion', 'cropland',
        'Plant a cover crop specifically to maintain ground cover and reduce wind and water erosion during the off-season.',
        'Must achieve at least 70% ground cover by December 1. Aerial or drill seeding both acceptable. Cereal rye after corn is most common in Iowa/Illinois.',
        9.50, 'acre', TRUE, 'B000CPL24', 'SOIL_EROSION', '340', 13, TRUE
    ),
    (
        'E329A',
        'Transition to no-till on previously tilled cropland',
        'Soil Erosion', 'cropland',
        'Convert fields from conventional or reduced tillage to no-till management, minimizing soil disturbance to only the planting operation.',
        'Must maintain no-till for duration of contract (5 years). Document fields converted. Works well paired with cover crops for weed management.',
        5.50, 'acre', TRUE, 'B000CPL24', 'SOIL_EROSION', '329', 17, TRUE
    ),
    (
        'E345A',
        'Transition from conventional to reduced tillage',
        'Soil Erosion', 'cropland',
        'Reduce tillage intensity to maintain at least 30% residue cover on the soil surface post-planting.',
        'Strip-till, vertical till, or one-pass reduced till all qualify. Must achieve >= 30% residue cover verified by line transect method.',
        3.25, 'acre', FALSE, NULL, 'SOIL_EROSION', '345', 10, TRUE
    ),
    (
        'E342A',
        'Establish in-field grass hedges to reduce soil erosion',
        'Soil Erosion', 'cropland',
        'Establish permanent narrow strips of native grass or brome perpendicular to slope to intercept and slow runoff within the field.',
        'Grass hedges must be <= 10 feet wide, spaced according to slope. Eastern gamagrass or switchgrass recommended. Must be permanent for contract duration.',
        185.00, 'acre', FALSE, NULL, 'SOIL_EROSION', '342', 11, TRUE
    ),
    (
        'E412A',
        'Grassed waterway to reduce concentrated flow erosion',
        'Soil Erosion', 'cropland',
        'Establish a natural or constructed channel with grass cover to safely convey concentrated runoff water through a field.',
        'Designed by NRCS engineer. Must be seeded to brome, orchardgrass, or native grass mix. Minimum width 10 feet. Cannot be tilled.',
        850.00, 'each', FALSE, NULL, 'SOIL_EROSION', '412', 14, TRUE
    ),
    (
        'E380A',
        'Windbreak establishment to reduce wind erosion',
        'Soil Erosion', 'cropland',
        'Establish rows of trees or shrubs along field borders to reduce wind erosion on exposed cropland.',
        'Most relevant for Kansas, Nebraska, and western Iowa/Illinois. Trees must be permanent for contract duration. NRCS will assist with design and species selection.',
        0.45, 'foot', FALSE, NULL, 'SOIL_EROSION', '380', 7, TRUE
    ),

    -- ---- WATER QUALITY ----
    (
        'E340E',
        'Cover crop mix to scavenge nutrients',
        'Water Quality', 'cropland',
        'Plant a cover crop mix selected specifically for nutrient uptake efficiency to reduce nitrate leaching into groundwater and tile drainage.',
        'Brassica (radish/turnip) mixes are effective at scavenging fall N. Must use multi-species mix. Document species composition and seeding rate.',
        10.25, 'acre', FALSE, NULL, 'WATER_QUALITY', '340', 13, TRUE
    ),
    (
        'E590A',
        'Improving nutrient uptake efficiency via 4R practices',
        'Water Quality', 'cropland',
        'Apply nutrients using 4R principles: Right Source, Right Rate, Right Time, Right Place to maximize crop uptake and minimize losses.',
        'Must have a current soil test (within 3 years). Document application rates, timing (split applications preferred), and application method. Side-dress N application qualifies.',
        0.80, 'acre', TRUE, 'B000CPL24', 'WATER_QUALITY', '590', 12, TRUE
    ),
    (
        'E590B',
        'Precision nutrient application using variable rate technology',
        'Water Quality', 'cropland',
        'Use variable rate fertilizer application technology guided by soil sampling grid or management zones to apply nutrients at optimal rates across the field.',
        'Requires grid soil sampling at 2.5-acre or smaller grid OR management zone sampling. Must have VRT prescription maps on file. Works with any fertilizer type.',
        1.20, 'acre', FALSE, NULL, 'WATER_QUALITY', '590', 14, TRUE
    ),
    (
        'E590C',
        'Nutrient management using enhanced efficiency fertilizers',
        'Water Quality', 'cropland',
        'Apply enhanced efficiency fertilizers (slow release, urease inhibitors, or nitrification inhibitors) to reduce nutrient loss pathways.',
        'NBPT urease inhibitors on surface-applied urea qualify. Polymer-coated slow-release fertilizers qualify. Must document product and application rate.',
        2.10, 'acre', FALSE, NULL, 'WATER_QUALITY', '590', 11, TRUE
    ),
    (
        'E590D',
        'Manure nutrient management with precision application',
        'Water Quality', 'cropland',
        'Apply livestock manure using soil test-based rates and precision GPS equipment to prevent nutrient over-application and runoff.',
        'Must have current soil tests. Must document manure nutrient content (lab analysis required). Applies to farms receiving manure from nearby livestock operations.',
        1.80, 'acre', FALSE, NULL, 'WATER_QUALITY', '590', 11, TRUE
    ),
    (
        'E393A',
        'Riparian buffer to protect water quality',
        'Water Quality', 'cropland',
        'Establish or maintain a vegetated buffer strip along streams, ditches, or water bodies to intercept nutrient and sediment runoff before it reaches the water.',
        'Buffer must be minimum 35 feet wide for full payment. Must be planted to native grasses or other approved species. Cannot be in corn-soy rotation.',
        45.00, 'acre', FALSE, NULL, 'WATER_QUALITY', '393', 16, TRUE
    ),

    -- ---- AIR QUALITY / CLIMATE ----
    (
        'E511A',
        'Reduce GHG emissions via efficient nitrogen management',
        'Air Quality', 'cropland',
        'Implement nitrogen management practices that demonstrably reduce nitrous oxide (N2O) emissions through split application, inhibitors, or reduced application rates.',
        'Split N application (spring pre-plant + side-dress) is the most accessible option for Midwest corn. Must document pre- and post-application N rates. Fall anhydrous only allowed on frozen soil.',
        0.90, 'acre', FALSE, NULL, 'AIR_QUALITY', '590', 10, TRUE
    ),
    (
        'E329B',
        'No-till to increase soil carbon sequestration',
        'Air Quality', 'cropland',
        'Maintain continuous no-till management to maximize carbon sequestration in soil organic matter and reduce tillage-related CO2 emissions.',
        'Requires continuous no-till (no occasional tillage passes). CSP verifies through FSA aerial imagery and NRCS field visits. Pairs with E340A or E340B for maximum benefit.',
        4.00, 'acre', TRUE, 'B000CPL24', 'AIR_QUALITY', '329', 14, TRUE
    ),

    -- ---- WATER QUANTITY / DRAINAGE MANAGEMENT ----
    (
        'E449A',
        'Controlled drainage water management',
        'Water Quantity', 'cropland',
        'Install or use water control structures on existing tile drainage systems to manage water table depth, retaining water in the field during dry periods and controlling drainage during wet periods.',
        'Requires existing tile drainage system with outlet control structure. Most applicable in flat topography (Iowa, Illinois, Indiana, Ohio). Reduces drainage N loss significantly.',
        6.50, 'acre', FALSE, NULL, 'WATER_QUANTITY', '449', 12, TRUE
    ),
    (
        'E449B',
        'Irrigation water management to reduce water use',
        'Water Quantity', 'cropland',
        'Implement soil moisture monitoring and ET-based irrigation scheduling to apply water only when and where crops need it.',
        'Most applicable in western Nebraska and Kansas where irrigation is common. Must use soil moisture sensors or ET weather station data. Document irrigation applications and water savings.',
        8.75, 'acre', FALSE, NULL, 'WATER_QUANTITY', '449', 12, TRUE
    ),

    -- ---- PLANT SPECIES / BIODIVERSITY ----
    (
        'E595A',
        'IPM scouting and threshold-based pesticide application',
        'Plant Condition', 'cropland',
        'Implement a documented Integrated Pest Management plan using economic thresholds to guide pesticide application decisions.',
        'Must use economic threshold data (Iowa State, Purdue, or University of Illinois thresholds accepted). Document scouting records and spray decisions. Reduces unnecessary applications.',
        0.60, 'acre', FALSE, NULL, 'PLANT_CONDITION', '595', 9, TRUE
    ),
    (
        'E595B',
        'Precision pesticide application using GPS guidance',
        'Plant Condition', 'cropland',
        'Apply pesticides using GPS-guided precision application equipment with automatic section control to eliminate overlap and reduce overall pesticide use.',
        'Must have section control with NRCS-approved GPS system. Must document total product reduction versus conventional application. Sprayer must be GPS-equipped.',
        1.10, 'acre', FALSE, NULL, 'PLANT_CONDITION', '595', 10, TRUE
    ),
    (
        'E512A',
        'Establish pollinator habitat strips within cropland',
        'Plant Condition', 'cropland',
        'Establish perennial strips of native flowering plants within or along cropland fields to support pollinator populations and beneficial insects.',
        'Strips must be minimum 30 feet wide. Must use native species appropriate to the state (contact state NRCS for approved seed mixes). Cannot be in crop rotation. USDA-approved seed mixes available.',
        125.00, 'acre', FALSE, NULL, 'PLANT_CONDITION', '512', 8, TRUE
    ),

    -- ---- ENERGY ----
    (
        'E374A',
        'Energy efficiency audit and improvement plan',
        'Energy', 'cropland',
        'Conduct a comprehensive energy audit of the farm operation and implement identified energy efficiency improvements.',
        'Energy audit must be conducted by a qualified professional. Must implement at least one identified improvement. Grain dryer efficiency is the highest-impact target for Midwest row crops.',
        1.25, 'acre', FALSE, NULL, 'ENERGY', NULL, 5, TRUE
    )

ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 3. STATE PAYMENT RATES — FY2025 (7 Midwest States)
-- ============================================================

INSERT INTO public.csp_state_payment_rates
    (state_code, fiscal_year,
     cropland_eap_per_rc, pasture_eap_per_rc, forest_eap_per_rc,
     min_annual_payment, max_annual_payment, max_contract_payment,
     enhancement_payment_pct, bundle_payment_pct,
     act_now_threshold_score,
     ranking_cutoff_date_1, ranking_cutoff_date_2, ranking_cutoff_date_3,
     notes)
VALUES
    -- Iowa FY2025
    (
        'IA', 2025,
        2.50, 1.75, 1.25,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        15,
        '2024-11-22', '2025-05-09', NULL,
        'Iowa MRBI priority state. High competition. ACT NOW pools open May-July.'
    ),
    -- Illinois FY2025
    (
        'IL', 2025,
        2.75, 1.90, 1.50,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        20,
        '2025-01-10', '2025-06-06', NULL,
        'Illinois IRA funding for climate-smart. Higher threshold due to large number of applicants.'
    ),
    -- Kansas FY2025
    (
        'KS', 2025,
        2.10, 1.50, 1.00,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        55,
        '2025-01-31', '2025-07-31', NULL,
        'Kansas uses area-based ranking pools. Ag Land Area 01 (east) threshold is 55; western areas lower.'
    ),
    -- Nebraska FY2025
    (
        'NE', 2025,
        2.25, 1.60, 1.10,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        30,
        '2025-01-31', '2025-07-11', NULL,
        'Nebraska second IRA CSP sign-up FY2025. Check NRCS Nebraska for updated pools.'
    ),
    -- Missouri FY2025
    (
        'MO', 2025,
        2.40, 1.70, 1.30,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        25,
        '2024-11-01', '2025-05-30', NULL,
        'Missouri MRBI priority areas in northern counties draining to Mississippi.'
    ),
    -- Indiana FY2025
    (
        'IN', 2025,
        2.60, 1.80, 1.40,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        20,
        '2025-01-17', '2025-06-20', NULL,
        'Indiana high drainage density; controlled drainage enhancements highly valued.'
    ),
    -- Ohio FY2025
    (
        'OH', 2025,
        2.65, 1.85, 1.45,
        4000.00, 50000.00, 200000.00,
        100.00, 115.00,
        20,
        '2025-01-24', '2025-06-27', NULL,
        'Ohio Lake Erie watershed priority. Phosphorus runoff is primary resource concern.'
    )
ON CONFLICT (state_code, fiscal_year) DO NOTHING;


-- ============================================================
-- 4. APPLICATION DEADLINES — FY2025 (14 rows, 2 per state)
-- ============================================================

INSERT INTO public.csp_application_deadlines
    (state_code, fiscal_year, cutoff_date, cutoff_name,
     is_act_now, act_now_start, act_now_end,
     description, is_active)
VALUES
    -- Iowa
    (
        'IA', 2025, '2024-11-22', 'FY2025 First Cutoff',
        FALSE, NULL, NULL,
        'Submit applications to local NRCS office by this date to be ranked in the first FY2025 funding pool.',
        FALSE
    ),
    (
        'IA', 2025, '2025-05-09', 'FY2025 Second Cutoff / ACT NOW Opens',
        TRUE, '2025-05-09', '2025-07-11',
        'Second cutoff date. ACT NOW pool opens May 9 through July 11. Applications meeting the 15-point threshold are immediately approved without waiting for ranking period end.',
        TRUE
    ),
    -- Illinois
    (
        'IL', 2025, '2025-01-10', 'FY2025 IRA Sign-up Cutoff',
        FALSE, NULL, NULL,
        'Deadline for IRA-funded CSP applications in Illinois for FY2025 consideration.',
        FALSE
    ),
    (
        'IL', 2025, '2025-06-06', 'FY2025 Second Cutoff / ACT NOW Opens',
        TRUE, '2025-06-06', '2025-08-08',
        'Illinois second ranking pool. Score 20+ qualifies for ACT NOW immediate approval.',
        TRUE
    ),
    -- Kansas
    (
        'KS', 2025, '2025-01-31', 'FY2025 First Cutoff',
        FALSE, NULL, NULL,
        'Kansas first ranking cutoff. Ranked by area pool; eastern Ag Land Area 01 threshold is 55 points.',
        FALSE
    ),
    (
        'KS', 2025, '2025-07-31', 'FY2025 Second Cutoff',
        TRUE, '2025-07-31', '2025-09-30',
        'Kansas second ranking pool. ACT NOW process available for applications meeting area threshold.',
        TRUE
    ),
    -- Nebraska
    (
        'NE', 2025, '2025-01-31', 'FY2025 First Cutoff',
        FALSE, NULL, NULL,
        'Nebraska first sign-up cutoff for IRA CSP funding in FY2025.',
        FALSE
    ),
    (
        'NE', 2025, '2025-07-11', 'FY2025 Second Cutoff / ACT NOW Opens',
        TRUE, '2025-07-11', '2025-09-12',
        'Nebraska second ranking pool. Score 30+ for ACT NOW immediate approval.',
        TRUE
    ),
    -- Missouri
    (
        'MO', 2025, '2024-11-01', 'FY2025 First Cutoff',
        FALSE, NULL, NULL,
        'Missouri first ranking cutoff. Northern counties (MRBI priority area) receive competitive advantage.',
        FALSE
    ),
    (
        'MO', 2025, '2025-05-30', 'FY2025 Second Cutoff',
        TRUE, '2025-05-30', '2025-07-31',
        'Missouri second ranking pool with ACT NOW process.',
        TRUE
    ),
    -- Indiana
    (
        'IN', 2025, '2025-01-17', 'FY2025 First Cutoff',
        FALSE, NULL, NULL,
        'Indiana first ranking cutoff for FY2025.',
        FALSE
    ),
    (
        'IN', 2025, '2025-06-20', 'FY2025 Second Cutoff',
        TRUE, '2025-06-20', '2025-08-22',
        'Indiana second ranking pool. Score 20+ for ACT NOW approval.',
        TRUE
    ),
    -- Ohio
    (
        'OH', 2025, '2025-01-24', 'FY2025 First Cutoff',
        FALSE, NULL, NULL,
        'Ohio first ranking date. Lake Erie watershed applications get priority.',
        FALSE
    ),
    (
        'OH', 2025, '2025-06-27', 'FY2025 Second Cutoff',
        TRUE, '2025-06-27', '2025-08-29',
        'Ohio second ranking pool with ACT NOW for scores 20+.',
        TRUE
    )
ON CONFLICT (state_code, fiscal_year, cutoff_name) DO NOTHING;
