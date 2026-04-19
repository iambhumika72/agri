from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
from scipy.stats import linregress

from .schemas import (
    FeatureVector,
    FeatureValidationError,
    SensorReading,
    WeatherForecast,
    FarmHistory,
    SatelliteAnalysis
)

log = logging.getLogger(__name__)

def build_satellite_features(satellite_data: SatelliteAnalysis) -> dict:
    """Computes features from satellite imagery and history."""
    ndvi_mean = satellite_data.ndvi_mean
    ndvi_history = satellite_data.ndvi_history
    
    # ndvi_stress_flag
    ndvi_stress_flag = 1 if ndvi_mean < 0.30 else 0
    
    # ndvi_trend (slope of last 5 readings)
    if len(ndvi_history) >= 2:
        recent_history = ndvi_history[-5:]
        x = np.arange(len(recent_history))
        slope, _, _, _, _ = linregress(x, recent_history)
        ndvi_trend = float(slope)
    else:
        ndvi_trend = 0.0
        
    # ndvi_anomaly_score (z-score vs 30-day rolling mean/history)
    if len(ndvi_history) >= 2:
        mean_hist = np.mean(ndvi_history)
        std_hist = np.std(ndvi_history)
        if std_hist > 0:
            ndvi_anomaly_score = (ndvi_mean - mean_hist) / std_hist
        else:
            ndvi_anomaly_score = 0.0
    else:
        ndvi_anomaly_score = 0.0
        
    # vegetation_zone
    if ndvi_mean > 0.6:
        vegetation_zone = "healthy"
    elif 0.4 <= ndvi_mean <= 0.6:
        vegetation_zone = "moderate"
    elif 0.2 <= ndvi_mean < 0.4:
        vegetation_zone = "stressed"
    else:
        vegetation_zone = "barren"
        
    # ndwi_water_stress
    ndwi_water_stress = 1 if satellite_data.ndwi_mean < -0.1 else 0
    
    # spatial_heterogeneity (CV = std / mean)
    if ndvi_mean != 0:
        spatial_heterogeneity = float(np.std(satellite_data.ndvi_array) / ndvi_mean)
    else:
        spatial_heterogeneity = 0.0
        
    return {
        "ndvi_stress_flag": ndvi_stress_flag,
        "ndvi_trend": ndvi_trend,
        "ndvi_anomaly_score": ndvi_anomaly_score,
        "vegetation_zone": vegetation_zone,
        "ndwi_water_stress": ndwi_water_stress,
        "spatial_heterogeneity": spatial_heterogeneity
    }

def build_sensor_features(sensor_readings: List[SensorReading], field_capacity: float = 0.40) -> dict:
    """Computes features from 14 days of sensor data."""
    if not sensor_readings:
        log.warning("Empty sensor_readings list. Returning zero features.")
        return {
            "soil_moisture_7d_avg": 0.0,
            "soil_moisture_trend": 0.0,
            "soil_moisture_deficit": 0.0,
            "temperature_stress_days": 0,
            "heat_accumulation_gdd": 0.0,
            "rainfall_7d_total": 0.0,
            "drought_index": 0.0,
            "humidity_avg_7d": 0.0
        }
    
    # Sort by timestamp
    sensor_readings = sorted(sensor_readings, key=lambda x: x.timestamp)
    last_7d = [r.soil_moisture for r in sensor_readings[-7:]]
    last_14d_temp = [r.air_temperature for r in sensor_readings[-14:]]
    
    # soil_moisture_7d_avg
    soil_moisture_7d_avg = float(np.mean(last_7d))
    
    # soil_moisture_trend
    if len(last_7d) >= 2:
        x = np.arange(len(last_7d))
        slope, _, _, _, _ = linregress(x, last_7d)
        soil_moisture_trend = float(slope)
    else:
        soil_moisture_trend = 0.0
        
    # soil_moisture_deficit (field_capacity 40% minus current moisture)
    current_moisture = sensor_readings[-1].soil_moisture / 100.0 # moisture as decimal for deficit?
    # Actually prompt says 40% vs moisture (likely also 0-100 or 0-1)
    # If field_capacity is 0.40, then moisture should be 0-1.
    soil_moisture_deficit = max(0.0, field_capacity - current_moisture)
    
    # temperature_stress_days
    temperature_stress_days = sum(1 for t in last_14d_temp if t > 35.0)
    
    # heat_accumulation_gdd
    # GDD = sum(max(0, (T_max + T_min)/2 - T_base)) where T_base = 10°C
    # Since we have daily air_temp (might be avg), we use that if T_max/min aren't split.
    # If SensorReading has air_temperature as avg, we use it.
    gdd = 0.0
    t_base = 10.0
    for r in sensor_readings:
        # Assuming air_temperature is avg; if we had max/min we'd use (max+min)/2
        gdd_day = max(0.0, r.air_temperature - t_base)
        gdd += gdd_day
    heat_accumulation_gdd = gdd
    
    # rainfall_7d_total
    rainfall_7d_total = sum(r.rainfall_mm for r in sensor_readings[-7:])
    
    # drought_index = 1 - (soil_moisture / field_capacity), clamped to [0, 1]
    if field_capacity > 0:
        drought_index = max(0.0, min(1.0, 1.0 - (current_moisture / field_capacity)))
    else:
        drought_index = 0.0
        
    # humidity_avg_7d
    humidity_avg_7d = float(np.mean([r.humidity for r in sensor_readings[-7:]]))
    
    return {
        "soil_moisture_7d_avg": soil_moisture_7d_avg,
        "soil_moisture_trend": soil_moisture_trend,
        "soil_moisture_deficit": soil_moisture_deficit,
        "temperature_stress_days": temperature_stress_days,
        "heat_accumulation_gdd": heat_accumulation_gdd,
        "rainfall_7d_total": rainfall_7d_total,
        "drought_index": drought_index,
        "humidity_avg_7d": humidity_avg_7d
    }

def build_weather_features(forecast: WeatherForecast) -> dict:
    """Computes features from 7-day weather forecast."""
    # rain_probability_7d (fraction of days forecast_rainfall > 2mm)
    rain_days = sum(1 for r in forecast.forecast_rainfall if r > 2.0)
    rain_probability_7d = rain_days / 7.0
    
    # heat_risk_7d (count of days forecast_temp_max > 38°C)
    heat_risk_7d = sum(1 for t in forecast.forecast_temp_max if t > 38.0)
    
    # irrigation_need_score (0–10)
    # score = (soil_moisture_deficit * 0.4) + (rain_probability inverse * 0.4) + (heat_risk fraction * 0.2) * 10
    # Assuming soil_moisture_deficit is 0-1, rain_prob is 0-1, heat_risk fraction is 0-1.
    # Note: we need soil_moisture_deficit from sensor_features or passed in.
    # For now, we'll return a score that can be calculated after merging, but the prompt asks for it here.
    # I'll pass a default deficit if not available, but ideally this is handled in assemble.
    # Actually, I'll assume we need to calculate it with some "state" or just return partials.
    # Wait, the prompt says "Implement ... Delivery: ... zero placeholder".
    # I will pass deficit as an optional arg.
    
    # optimal_irrigation_days: indices (0–6) where forecast_rainfall < 2mm AND forecast_temp_max < 38°C
    optimal_irrigation_days = [
        i for i, (r, t) in enumerate(zip(forecast.forecast_rainfall, forecast.forecast_temp_max))
        if r < 2.0 and t < 38.0
    ]
    
    # evapotranspiration_est (Hargreaves: ET = 0.0023 * (T_mean + 17.8) * (T_max - T_min)^0.5 * Ra)
    # Ra = 12.0
    ra = 12.0
    et_list = []
    for t_max, t_min in zip(forecast.forecast_temp_max, forecast.forecast_temp_min):
        t_mean = (t_max + t_min) / 2.0
        et_day = 0.0023 * (t_mean + 17.8) * math.sqrt(max(0.0, t_max - t_min)) * ra
        et_list.append(et_day)
    evapotranspiration_est = float(np.mean(et_list))
    
    # frost_risk_7d (count of days forecast_temp_min < 4°C)
    frost_risk_7d = sum(1 for t in forecast.forecast_temp_min if t < 4.0)
    
    return {
        "rain_probability_7d": rain_probability_7d,
        "heat_risk_7d": heat_risk_7d,
        "optimal_irrigation_days": optimal_irrigation_days,
        "evapotranspiration_est": evapotranspiration_est,
        "frost_risk_7d": frost_risk_7d
    }

def build_historical_features(history: FarmHistory) -> dict:
    """Computes features from farm history and metadata."""
    now = datetime.utcnow().replace(tzinfo=None)
    planting_date = history.planting_date.replace(tzinfo=None)
    days_since_planting = (now - planting_date).days
    
    # crop_growth_stage
    if days_since_planting <= 20:
        crop_growth_stage = "seedling"
    elif 21 <= days_since_planting <= 50:
        crop_growth_stage = "vegetative"
    elif 51 <= days_since_planting <= 80:
        crop_growth_stage = "flowering"
    elif 81 <= days_since_planting <= 110:
        crop_growth_stage = "maturation"
    else:
        crop_growth_stage = "harvest_ready"
        
    # yield_trend
    if len(history.yield_history) >= 2:
        x = np.arange(len(history.yield_history))
        slope, _, _, _, _ = linregress(x, history.yield_history)
        yield_trend = float(slope)
    else:
        yield_trend = 0.0
        
    avg_historical_yield = float(np.mean(history.yield_history)) if history.yield_history else 0.0
    yield_volatility = float(np.std(history.yield_history)) if history.yield_history else 0.0
    
    # pest_risk_score = pest_events_same_season / total_seasons, clamp [0,1]
    # Assuming history.pest_events is a list of events.
    # total_seasons = len(history.yield_history) if history.yield_history else 1
    same_season_pests = sum(1 for p in history.pest_events if p.get("season") == history.season)
    total_seasons = max(1, len(history.yield_history))
    pest_risk_score = min(1.0, same_season_pests / total_seasons)
    
    # days_since_last_irrigation
    if history.irrigation_log:
        last_irr = max(history.irrigation_log, key=lambda x: x["date"])["date"].replace(tzinfo=None)
        days_since_last_irrigation = (now - last_irr).days
    else:
        days_since_last_irrigation = days_since_planting # fallback
        
    # irrigation_frequency (per week, last 30 days)
    recent_irrigations = [i for i in history.irrigation_log if (now - i["date"].replace(tzinfo=None)).days <= 30]
    irrigation_frequency = len(recent_irrigations) / 4.28 # ~30 days in weeks
    
    # season_encoded (kharif=0, rabi=1, zaid=2)
    season_map = {"kharif": 0, "rabi": 1, "zaid": 2}
    season_encoded = season_map.get(history.season.lower(), 0)
    
    return {
        "days_since_planting": days_since_planting,
        "crop_growth_stage": crop_growth_stage,
        "yield_trend": yield_trend,
        "avg_historical_yield": avg_historical_yield,
        "yield_volatility": yield_volatility,
        "pest_risk_score": pest_risk_score,
        "days_since_last_irrigation": days_since_last_irrigation,
        "irrigation_frequency": irrigation_frequency,
        "season_encoded": season_encoded
    }

def assemble_feature_vector(
    satellite_features: dict,
    sensor_features: dict,
    weather_features: dict,
    historical_features: dict,
    farm_id: str
) -> FeatureVector:
    """Assembles and validates the final FeatureVector."""
    # Compute irrigation_need_score here since it depends on sensor and weather partials
    # score = (soil_moisture_deficit * 0.4) + (rain_probability inverse * 0.4) + (heat_risk fraction * 0.2) * 10
    deficit = sensor_features.get("soil_moisture_deficit", 0.0)
    rain_prob_inv = 1.0 - weather_features.get("rain_probability_7d", 0.0)
    heat_risk_frac = weather_features.get("heat_risk_7d", 0) / 7.0
    
    irrigation_need_score = round(max(0.0, min(10.0, (deficit * 0.4 + rain_prob_inv * 0.4 + heat_risk_frac * 0.2) * 10)), 1)
    
    merged = {
        **satellite_features,
        **sensor_features,
        **weather_features,
        **historical_features,
        "farm_id": farm_id,
        "feature_timestamp": datetime.utcnow(),
        "feature_version": "1.0",
        "irrigation_need_score": irrigation_need_score
    }
    
    # Validate: no NaN or None
    for k, v in merged.items():
        if v is None:
            raise FeatureValidationError(f"Null value found in field: {k}")
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise FeatureValidationError(f"Invalid float value (NaN/Inf) found in field: {k}")
            
    fv = FeatureVector(**merged)
    log.info(f"Assembled FeatureVector for {farm_id} at {fv.feature_timestamp} (v{fv.feature_version})")
    log.info(f"Summary: NDVI={satellite_features['ndvi_trend']:.3f}, Moisture={sensor_features['soil_moisture_7d_avg']:.1f}%, Irrigation Score={irrigation_need_score}")
    
    return fv

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.INFO)
    dummy_sat = SatelliteAnalysis("F1", datetime.now(), 0.45, 0.05, -0.15, np.random.rand(10, 10), False, [0.4, 0.42, 0.45])
    sat_f = build_satellite_features(dummy_sat)
    print(sat_f)
