from __future__ import annotations

import logging
import numpy as np
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Any

log = logging.getLogger(__name__)

@dataclass
class SatelliteAnalysis:
    """Represents the output from the ingestion/ satellite pipeline."""
    farm_id: str
    acquisition_date: datetime
    ndvi_mean: float
    ndvi_std: float
    ndwi_mean: float
    ndvi_array: np.ndarray
    stale: bool
    # History for trend/anomaly (last 5-30 readings)
    ndvi_history: List[float] 
    
@dataclass
class ChangeResult:
    """Represents the output from the change detection module."""
    severity: str
    alert_zone_pct: float
    delta_array: np.ndarray
    alert_mask: np.ndarray
    geojson_path: str

@dataclass
class SensorReading:
    """Represents a single day's aggregated IoT sensor readings."""
    farm_id: str
    timestamp: datetime
    soil_moisture: float
    soil_temperature: float
    air_temperature: float
    humidity: float
    rainfall_mm: float

@dataclass  
class WeatherForecast:
    """Represents a 7-day weather forecast for a specific farm."""
    farm_id: str
    forecast_date: datetime
    forecast_temp_max: List[float]    # 7 values
    forecast_temp_min: List[float]    # 7 values
    forecast_rainfall: List[float]    # 7 values
    forecast_humidity: List[float]    # 7 values
    forecast_wind_speed: List[float]  # 7 values

@dataclass
class FarmHistory:
    """Represents historical data and metadata for a specific farm."""
    farm_id: str
    crop_type: str
    planting_date: datetime
    season: str
    yield_history: List[float]
    pest_events: List[dict]
    irrigation_log: List[dict]

@dataclass
class FeatureVector:
    """The final assembled feature vector for model input and LLM context."""
    farm_id: str
    feature_timestamp: datetime
    feature_version: str
    
    # satellite
    ndvi_stress_flag: int
    ndvi_trend: float
    ndvi_anomaly_score: float
    vegetation_zone: str
    ndwi_water_stress: int
    spatial_heterogeneity: float
    
    # sensor
    soil_moisture_7d_avg: float
    soil_moisture_trend: float
    soil_moisture_deficit: float
    temperature_stress_days: int
    heat_accumulation_gdd: float
    rainfall_7d_total: float
    drought_index: float
    humidity_avg_7d: float
    
    # weather
    rain_probability_7d: float
    heat_risk_7d: int
    irrigation_need_score: float
    optimal_irrigation_days: List[int]
    evapotranspiration_est: float
    frost_risk_7d: int
    
    # historical
    days_since_planting: int
    crop_growth_stage: str
    yield_trend: float
    avg_historical_yield: float
    yield_volatility: float
    pest_risk_score: float
    days_since_last_irrigation: int
    irrigation_frequency: float
    season_encoded: int

class FeatureValidationError(Exception):
    """Raised when the assembled feature vector contains invalid values (e.g., NaN)."""
    pass

@dataclass
class FieldCapabilityProfile:
    """A crop-agnostic profile of the field's agricultural potential."""
    farm_id: str
    timestamp: datetime
    
    # Vegetation Health (Satellite)
    avg_ndvi: float
    ndvi_stability: float
    moisture_index: float  # NDWI
    
    # Climatic Suitability (Weather)
    temp_suitability: float # 0-1
    precip_suitability: float # 0-1
    soil_moisture_index: float # 0-1
    
    # Soil Health (Direct sensor/DB)
    ph_level: float
    organic_matter: float
    
    # Risk Profile
    historical_pest_pressure: float # 0-1
    dominant_pest_types: List[str]
    
    # Final Score
    overall_capability_score: float # 0-1

if __name__ == "__main__":
    # Smoke test for schemas
    now = datetime.utcnow()
    reading = SensorReading("F1", now, 25.0, 20.0, 30.0, 60.0, 0.0)
    print(f"Created SensorReading for {reading.farm_id} at {reading.timestamp}")
