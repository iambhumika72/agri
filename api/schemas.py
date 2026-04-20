from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class FarmRequest(BaseModel):
    farm_id: str = Field(..., example="punjab_farm_001")
    latitude: float = Field(..., example=30.90)
    longitude: float = Field(..., example=75.85)
    crop_type: str = Field("Wheat", example="Wheat")
    planting_date: datetime = Field(..., example="2024-10-01T00:00:00")
    season: str = Field("Kharif", example="Kharif")
    language: str = "en"   # ISO 639-1 code for response language

class SatelliteResponse(BaseModel):
    acquisition_date: str
    ndvi_mean: float
    ndwi_mean: float
    cloud_cover_pct: float
    stale: bool
    geotiff_path: str

class WeatherResponse(BaseModel):
    forecast_date: datetime
    temp_max: float
    temp_min: float
    rainfall_mm: float
    humidity: float

class FeatureVectorResponse(BaseModel):
    ndvi_trend: float
    vegetation_zone: str
    soil_moisture_7d_avg: float
    irrigation_need_score: float
    optimal_irrigation_days: List[int]
    pest_risk_score: float

class FullForecastResponse(BaseModel):
    farm_id: str
    timestamp: datetime
    satellite: SatelliteResponse
    weather: List[WeatherResponse]
    features: FeatureVectorResponse
    recommendation_context: str
    predicted_yield: Optional[float] = None
    irrigation_schedule: Optional[List[dict]] = None
    forecast_model_used: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    dependencies: dict[str, str]

class ProfitAnalysisResponse(BaseModel):
    crop: str
    total_cost: float
    gross_revenue: float
    net_profit: float
    roi_pct: float
    break_even_price: float

class CropProfitResponse(BaseModel):
    farm_id: str
    timestamp: datetime
    suitability_scores: dict[str, float]
    profit_analyses: List[ProfitAnalysisResponse]
    profit_boost_advice: str
    overall_capability_score: float
