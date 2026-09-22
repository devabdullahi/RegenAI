-- ============================================================
-- RegenAI Seed Data
-- EQIP Practice Codes — USDA NRCS reference data
-- Relevant to Midwest row crop and regenerative agriculture
--
-- Codes and names follow the NRCS National Handbook of Conservation
-- Practices (Conservation Practice Standards).
--
-- This file is the single source of truth for eqip_practices.
-- `supabase db reset` applies it locally; backend/scripts/seed_eqip.py
-- parses the VALUES below to upsert them into a hosted project, so keep
-- every row in the ('code', 'name', 'category', 'description', 'unit')
-- shape. Codes shared with the CSP scoring catalog
-- (backend/app/services/program_rules.py, CSP_PRACTICE_CATALOG) must use
-- the same NRCS standard code and name.
-- ============================================================

insert into public.eqip_practices (code, name, category, description, unit)
values
  -- Conservation Crop and Tillage
  ('327',  'Conservation Cover',
   'Conservation Crop Management',
   'Establish and maintain permanent vegetative cover on land retired from agricultural production. Reduces erosion and sedimentation, improves soil health, and provides wildlife and pollinator habitat.',
   'acre'),

  ('328',  'Conservation Crop Rotation',
   'Conservation Crop Management',
   'Grow a planned sequence of various crops on the same field. Reduces erosion, maintains or increases soil organic matter, and breaks pest and disease cycles.',
   'acre'),

  ('340',  'Cover Crop',
   'Conservation Crop Management',
   'Establish adapted plants, including grasses, legumes, and forbs, for seasonal cover and conservation purposes. Reduces erosion, builds organic matter, and suppresses weeds.',
   'acre'),

  ('329',  'Residue and Tillage Management, No-Till',
   'Conservation Crop Management',
   'Manage the amount, orientation, and distribution of crop and other plant residue on the soil surface year-round with no disturbance from tillage. Improves water infiltration and reduces soil disturbance.',
   'acre'),

  ('345',  'Residue and Tillage Management, Reduced Till',
   'Conservation Crop Management',
   'Manage the amount, orientation, and distribution of crop and other plant residue on the soil surface year-round while limiting soil-disturbing activities used to grow and harvest crops. Maintains surface residue and reduces erosion.',
   'acre'),

  ('330',  'Contour Farming',
   'Erosion Prevention',
   'Farm sloping land by performing field operations, such as tillage, planting, and cultivation, on the contour. Reduces water-caused erosion on slopes.',
   'acre'),

  ('585',  'Stripcropping',
   'Erosion Prevention',
   'Grow crops in a systematic arrangement of strips or bands across the general slope or perpendicular to prevailing wind. Alternating strips of row crops with close-growing crops interrupt runoff flow and filter sediment.',
   'acre'),

  -- Nutrient and Pest Management
  ('590',  'Nutrient Management',
   'Nutrient Management',
   'Manage the amount, source, placement, form, and timing of the application of plant nutrients and soil amendments to achieve production and environmental goals. Reduces nutrient loss to water and air.',
   'acre'),

  ('595',  'Pest Management Conservation System',
   'Pest Management',
   'Use an integrated approach combining cultural, biological, mechanical, and chemical management tactics to prevent unacceptable levels of pest damage with minimal adverse effect on human health and the environment.',
   'acre'),

  -- Water Management
  ('449',  'Irrigation Water Management',
   'Water Management',
   'Determine and control the rate, amount, and timing of irrigation water in a planned, efficient manner. Conserves water, reduces energy costs, and minimizes nutrient and pesticide movement.',
   'acre'),

  ('554',  'Drainage Water Management',
   'Water Management',
   'Manage the drainage water table or the rate and timing of drainage water discharge from a field to reduce nutrient and pesticide losses, and improve water quality.',
   'acre'),

  ('441',  'Irrigation System, Microirrigation',
   'Water Management',
   'Install microirrigation systems that apply water slowly at or near the root zone of plants through emitters, sprinklers, spray heads, or bubblers. Maximizes water use efficiency.',
   'acre'),

  -- https://www.nrcs.usda.gov/resources/guides-and-instructions/irrigation-pipeline-ft-430-conservation-practice-standard
  ('430',  'Irrigation Pipeline',
   'Water Management',
   'Install a pipeline and appurtenances to convey water for storage or application as part of an irrigation system.',
   'foot'),

  -- Grass and Buffer Practices
  ('412',  'Grassed Waterway',
   'Erosion Prevention',
   'Shape or grade a natural or constructed channel and establish permanent vegetation to safely carry surface water at a non-erosive velocity. Prevents gully formation and reduces sediment delivery.',
   'acre'),

  ('393',  'Filter Strip',
   'Water Quality',
   'Establish a strip or area of herbaceous vegetation between cropland and environmentally sensitive areas such as streams. Removes sediment, nutrients, and other contaminants from runoff.',
   'acre'),

  ('332',  'Contour Buffer Strips',
   'Erosion Prevention',
   'Establish narrow strips of permanent, herbaceous vegetation alternated with wider cropped strips and farmed on the contour. Traps sediment, reduces runoff velocity, and provides wildlife habitat.',
   'acre'),

  ('386',  'Field Border',
   'Erosion Prevention',
   'Establish a strip of permanent vegetation at the edge or around the perimeter of a field. Reduces wind and water erosion, improves water quality, and provides wildlife habitat.',
   'acre'),

  ('342',  'Critical Area Planting',
   'Erosion Prevention',
   'Establish vegetation on sites that have, or are expected to have, high erosion rates and sites that have physical, chemical, or biological conditions that prevent the establishment of vegetation with normal practices.',
   'acre'),

  -- Grazing and Livestock
  ('528',  'Prescribed Grazing',
   'Grazing Management',
   'Manage the harvest of vegetation with grazing or browsing animals and the period of non-grazing or non-browsing to achieve desired plant composition, structure, ground cover, and vigor.',
   'acre'),

  ('512',  'Forage and Biomass Planting',
   'Grazing Management',
   'Establish appropriate species of herbaceous plants for forage, energy biomass, and conservation purposes. Provides feed for livestock, improves soil health, and supports biodiversity.',
   'acre'),

  ('472',  'Access Control',
   'Grazing Management',
   'Exclude or limit animal and human access to an area to protect or improve its resources. Prevents overgrazing, bank erosion along streams, and compaction in sensitive areas.',
   'acre'),

  ('614',  'Watering Facility',
   'Grazing Management',
   'Construct or modify facilities to provide water for livestock or wildlife. Improves water quality by drawing animals away from natural water sources.',
   'each'),

  -- Structural Practices
  ('600',  'Terrace',
   'Erosion Prevention',
   'Construct an earth embankment, or a combination ridge and channel, across the field slope. Reduces slope length, sheet and rill erosion, and sediment delivery.',
   'foot'),

  ('382',  'Fence',
   'Grazing Management',
   'Construct a fence to control the movement of people, animals, equipment, and vehicles. Essential for managed rotational grazing systems and protecting sensitive areas from livestock.',
   'foot'),

  -- Wind Erosion
  ('380',  'Windbreak/Shelterbelt Establishment',
   'Wind Erosion',
   'Establish woody plants in a linear design to protect soil from wind erosion, reduce wind speed, and protect livestock, structures, and crops from wind damage.',
   'foot'),

  ('612',  'Tree/Shrub Establishment',
   'Agroforestry',
   'Establish woody plants by planting seedlings or cuttings, by direct seeding, or through natural regeneration. Reduces erosion, improves water quality, and sequesters carbon.',
   'acre'),

  -- Waste Management
  ('633',  'Waste Recycling',
   'Waste Management',
   'Apply organic waste materials at agronomic rates for beneficial use. Reduces nutrient runoff risk while recycling nutrients and organic matter back into the cropping system.',
   'acre'),

  -- Energy (standard 374 was titled "Farmstead Energy Improvement" before 2021)
  ('374',  'Energy Efficient Agricultural Operation',
   'Energy',
   'Develop and implement improvements, based on an agricultural energy audit, that reduce on-farm energy use or improve its efficiency, such as grain dryer, ventilation, or pumping upgrades.',
   'each'),

  -- Soil Health
  ('484',  'Mulching',
   'Soil Health',
   'Apply organic or inorganic material on the soil surface to conserve moisture, reduce temperature fluctuations, suppress weeds, and improve soil health.',
   'acre'),

  ('647',  'Early Successional Habitat Development and Management',
   'Wildlife Habitat',
   'Establish, develop, and manage areas of early successional habitat for target wildlife species. Provides nesting, brood-rearing, and food resources for a variety of wildlife species.',
   'acre')

-- Update existing rows so previously seeded, mislabelled codes are corrected.
on conflict (code) do update
  set name        = excluded.name,
      category    = excluded.category,
      description = excluded.description,
      unit        = excluded.unit;
