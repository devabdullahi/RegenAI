"""
Seed a demo farm so every screen has data to show.

The rows are fictional but realistic: a real county FIPS (so weather and soil
enrichment resolve to genuine Open-Meteo and USDA SSURGO data), crops and rates
typical for that county, and five years of yield history so APH — which needs
four — actually computes.

Run from backend/ with the service-role key set, because every table is behind
row level security and this seeds on a farmer's behalf:

    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
        python scripts/seed_demo_farm.py --email you@example.com

The auth user is created if it does not exist, so the farm belongs to a real
account you can sign into. Re-running is safe: rows are matched by name and
reused rather than duplicated.
"""

import argparse
import os
import secrets
import sys
from datetime import date, timedelta

from supabase import create_client

# --- Demo farm definition -------------------------------------------------
# Story County, Iowa (FIPS 19169) is a real county, so enrichment resolves
# coordinates and pulls live weather and soil for it.
FARM = {
    "name": "Prairie Creek Farms (demo)",
    "state": "IA",
    "county_fips": "19169",
    "total_acres": 1240,
    "goals": "both",
}

FIELDS = [
    {
        "name": "North 320",
        "acres": 320,
        "crop_type": "Corn",
        "practices": ["340", "329"],
        "boundary_description": "North of the county road, tiled 2019",
    },
    {
        "name": "Creek Bottom",
        "acres": 280,
        "crop_type": "Soybeans",
        "practices": ["329", "393"],
        "boundary_description": "Follows the creek, wet on the east end",
    },
    {
        "name": "Home Quarter",
        "acres": 160,
        "crop_type": "Corn",
        "practices": ["340", "328", "590"],
        "boundary_description": "Around the buildings",
    },
    {
        "name": "South 480",
        "acres": 480,
        "crop_type": "Soybeans",
        "practices": ["329"],
        "boundary_description": "Rolling, south-facing slope",
    },
]

# Five years each, so APH computes for every field.
YIELDS = {
    "North 320": [
        (2021, "Corn", 201.4), (2022, "Corn", 188.2), (2023, "Corn", 214.9),
        (2024, "Corn", 196.7), (2025, "Corn", 207.3),
    ],
    "Creek Bottom": [
        (2021, "Soybeans", 58.1), (2022, "Soybeans", 54.6), (2023, "Soybeans", 61.2),
        (2024, "Soybeans", 57.4), (2025, "Soybeans", 59.8),
    ],
    "Home Quarter": [
        (2021, "Corn", 195.0), (2022, "Corn", 182.5), (2023, "Corn", 208.1),
        (2024, "Corn", 190.3), (2025, "Corn", 199.6),
    ],
    "South 480": [
        (2021, "Soybeans", 55.3), (2022, "Soybeans", 52.8), (2023, "Soybeans", 58.9),
        (2024, "Soybeans", 56.1), (2025, "Soybeans", 60.4),
    ],
}


def _activities_for(field_name: str, crop: str) -> list[dict]:
    """A plausible season for one field, dated relative to today."""
    today = date.today()
    season = today.year if today.month >= 4 else today.year - 1
    planted = date(season, 4, 28) if crop == "Corn" else date(season, 5, 12)
    return [
        {
            "activity_type": "plant",
            "activity_date": planted.isoformat(),
            "seed_variety": "Pioneer P0574AMXT" if crop == "Corn" else "Asgrow AG28XF0",
            "seeding_rate": 34000 if crop == "Corn" else 140000,
            "seeding_rate_unit": "seeds_per_acre",
            "operator": "Dale",
            "equipment_used": "John Deere 1775NT",
            "notes": f"{field_name}: planted into good moisture.",
        },
        {
            "activity_type": "spray",
            "activity_date": (planted + timedelta(days=26)).isoformat(),
            "product_name": "Roundup PowerMax 3",
            "epa_reg_number": "524-537",
            "rate_per_acre": 32,
            "rate_unit": "oz_per_acre",
            "target_pest": "waterhemp",
            "wind_speed_mph": 6,
            "temperature_f": 71,
            "restricted_use": False,
            "operator": "Dale",
        },
        {
            "activity_type": "scout",
            "activity_date": (planted + timedelta(days=55)).isoformat(),
            "pest_name": "corn rootworm beetle" if crop == "Corn" else "soybean aphid",
            "severity": "low",
            "operator": "Sam",
            "notes": "Below threshold, monitoring.",
        },
    ]


def _ensure_user(supabase, email: str, password: str | None) -> str:
    for user in supabase.auth.admin.list_users():
        if (user.email or "").lower() == email.lower():
            return user.id
    created = supabase.auth.admin.create_user(
        {
            "email": email,
            "password": password or secrets.token_urlsafe(16),
            "email_confirm": True,
        }
    )
    return created.user.id


def _ensure_farm(supabase, user_id: str) -> str:
    # public.users is populated by the on_auth_user_created trigger, which farms
    # reference, so the auth user must exist first.
    found = (
        supabase.table("farms").select("id")
        .eq("user_id", user_id).eq("name", FARM["name"]).limit(1).execute()
    )
    if found.data:
        return found.data[0]["id"]
    return supabase.table("farms").insert({**FARM, "user_id": user_id}).execute().data[0]["id"]


def _ensure_field(supabase, farm_id: str, spec: dict) -> str:
    found = (
        supabase.table("fields").select("id")
        .eq("farm_id", farm_id).eq("name", spec["name"]).limit(1).execute()
    )
    if found.data:
        return found.data[0]["id"]
    return supabase.table("fields").insert({**spec, "farm_id": farm_id}).execute().data[0]["id"]


def _seed_activities(supabase, field_id: str, spec: dict) -> None:
    existing = (
        supabase.table("field_activities").select("id")
        .eq("field_id", field_id).limit(1).execute()
    )
    if existing.data:
        return
    rows = [
        {**activity, "field_id": field_id}
        for activity in _activities_for(spec["name"], spec["crop_type"])
    ]
    supabase.table("field_activities").insert(rows).execute()


def _seed_yields(supabase, field_id: str, field_name: str) -> None:
    rows = [
        {
            "field_id": field_id,
            "crop_year": year,
            "crop_type": crop,
            "yield_bu_acre": bushels,
            "moisture_pct": 15.5 if crop == "Corn" else 13.0,
        }
        for year, crop, bushels in YIELDS[field_name]
    ]
    supabase.table("yield_history").upsert(rows, on_conflict="field_id,crop_year").execute()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a demo farm for a real account.")
    parser.add_argument("--email", required=True, help="Account the demo farm belongs to.")
    parser.add_argument(
        "--password", default=None, help="Password for a newly created account."
    )
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.", file=sys.stderr)
        return 1

    # Service role bypasses RLS, which is required to seed another account's rows.
    supabase = create_client(url, service_key)

    user_id = _ensure_user(supabase, args.email, args.password)
    print(f"account {args.email} -> {user_id}")

    farm_id = _ensure_farm(supabase, user_id)
    print(f"farm {FARM['name']} -> {farm_id}")

    for spec in FIELDS:
        field_id = _ensure_field(supabase, farm_id, spec)
        print(f"  field {spec['name']} -> {field_id}")
        _seed_activities(supabase, field_id, spec)
        _seed_yields(supabase, field_id, spec["name"])

    print(
        "\nDone. Sign in as this account, then enrich a field to pull live weather "
        "and soil, and generate recommendations."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
