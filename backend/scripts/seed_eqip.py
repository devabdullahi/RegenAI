"""Seed EQIP practice codes into the database.

These are the most common NRCS conservation practice standards
relevant to regenerative agriculture in the US Midwest.

Run: python -m scripts.seed_eqip
Requires: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

EQIP_PRACTICES = [
    {"code": "328", "name": "Conservation Crop Rotation", "category": "Cropland Soil Health",
     "description": "Growing crops in a planned sequence on the same field to improve soil health, reduce erosion, and manage pests.",
     "unit": "acre"},
    {"code": "329", "name": "Residue and Tillage Management, No-Till", "category": "Cropland Soil Health",
     "description": "Managing crop residue by limiting soil disturbance to only the planting operation.",
     "unit": "acre"},
    {"code": "340", "name": "Cover Crop", "category": "Cropland Soil Health",
     "description": "Planting grasses, legumes, or forbs to provide seasonal cover for soil health and erosion control.",
     "unit": "acre"},
    {"code": "345", "name": "Residue and Tillage Management, Reduced Till", "category": "Cropland Soil Health",
     "description": "Managing crop residue with reduced mechanical tillage to maintain at least 30% ground cover.",
     "unit": "acre"},
    {"code": "590", "name": "Nutrient Management", "category": "Nutrient Management",
     "description": "Managing the amount, source, placement, and timing of plant nutrients and soil amendments.",
     "unit": "acre"},
    {"code": "595", "name": "Integrated Pest Management", "category": "Pest Management",
     "description": "A site-specific combination of pest prevention, avoidance, monitoring, and suppression strategies.",
     "unit": "acre"},
    {"code": "412", "name": "Grassed Waterway", "category": "Water Quality",
     "description": "A natural or constructed channel shaped or graded and established with suitable vegetation.",
     "unit": "acre"},
    {"code": "393", "name": "Filter Strip", "category": "Water Quality",
     "description": "A strip of vegetation between cropland and a water body to remove sediment and nutrients.",
     "unit": "acre"},
    {"code": "382", "name": "Fence", "category": "Grazing Management",
     "description": "A constructed barrier to facilitate management of livestock or wildlife.",
     "unit": "foot"},
    {"code": "512", "name": "Forage and Biomass Planting", "category": "Forage",
     "description": "Establishing adapted plants for forage production, erosion control, or bioenergy feedstock.",
     "unit": "acre"},
    {"code": "528", "name": "Prescribed Grazing", "category": "Grazing Management",
     "description": "Managing grazing and browsing to improve or maintain vegetation health.",
     "unit": "acre"},
    {"code": "327", "name": "Conservation Cover", "category": "Cropland Soil Health",
     "description": "Establishing and maintaining perennial vegetative cover to protect soil and water resources.",
     "unit": "acre"},
    {"code": "449", "name": "Irrigation Water Management", "category": "Water Management",
     "description": "Determining and controlling the rate, amount, and timing of irrigation water.",
     "unit": "acre"},
    {"code": "612", "name": "Tree/Shrub Establishment", "category": "Agroforestry",
     "description": "Establishing woody plants by planting seedlings or cuttings.",
     "unit": "acre"},
    {"code": "380", "name": "Windbreak/Shelterbelt Establishment", "category": "Agroforestry",
     "description": "Rows of trees or shrubs to reduce wind erosion and protect crops.",
     "unit": "foot"},
]


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("Error: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        return

    supabase = create_client(url, key)

    print(f"Seeding {len(EQIP_PRACTICES)} EQIP practice codes...")

    result = supabase.table("eqip_practices").upsert(
        EQIP_PRACTICES, on_conflict="code"
    ).execute()

    print(f"Done. {len(result.data)} practices upserted.")


if __name__ == "__main__":
    main()
