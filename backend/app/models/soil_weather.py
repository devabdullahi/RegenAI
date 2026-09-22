"""Soil profile and weather response models."""

from datetime import datetime

from pydantic import BaseModel


class SoilProfileResponse(BaseModel):
    id: str
    field_id: str
    ssurgo_map_unit: str
    texture: str
    ph: float
    organic_matter_pct: float
    source: str
    fetched_at: datetime



class WeatherResponse(BaseModel):
    id: str
    field_id: str
    date: str
    temp_high: float
    temp_low: float
    precip_mm: float
    soil_temp: float | None = None  # nullable column; None when Open-Meteo has no reading
    fetched_at: datetime
