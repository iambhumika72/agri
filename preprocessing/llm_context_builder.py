from __future__ import annotations

import logging
import numpy as np
from .schemas import FeatureVector, SatelliteAnalysis, ChangeResult

log = logging.getLogger(__name__)

def build_farm_context_string(
    feature_vector: FeatureVector,
    satellite_analysis: SatelliteAnalysis,
    farm_metadata: dict
) -> str:
    """Formats the feature vector into a structured natural language summary for LLM context."""
    
    # Extracting and rounding for readability
    id = feature_vector.farm_id
    crop = farm_metadata.get("crop", "Unknown")
    season = farm_metadata.get("season", "Unknown")
    n = feature_vector.days_since_planting
    stage = feature_vector.crop_growth_stage
    
    sat_date = satellite_analysis.acquisition_date.strftime("%Y-%m-%d")
    ndvi = round(satellite_analysis.ndvi_mean, 2)
    zone = feature_vector.vegetation_zone
    water_stress = "Yes" if feature_vector.ndwi_water_stress else "No"
    
    # Determine trend direction
    trend_val = feature_vector.ndvi_trend
    trend_dir = "increasing" if trend_val > 0.01 else "decreasing" if trend_val < -0.01 else "stable"
    
    moisture = round(feature_vector.soil_moisture_7d_avg, 2)
    deficit = round(feature_vector.soil_moisture_deficit * 100, 2) # as percentage
    temp = round(feature_vector.heat_accumulation_gdd / max(1, n), 2) # average gdd
    rain_7d = round(feature_vector.rainfall_7d_total, 2)
    
    gdd = round(feature_vector.heat_accumulation_gdd, 2)
    stress_days = feature_vector.temperature_stress_days
    pest = round(feature_vector.pest_risk_score, 2)
    
    y_trend = "increasing" if feature_vector.yield_trend > 0 else "decreasing" if feature_vector.yield_trend < 0 else "stable"
    
    rain_days = int(feature_vector.rain_probability_7d * 7)
    heat_days = feature_vector.heat_risk_7d
    irr_score = feature_vector.irrigation_need_score
    opt_days = ", ".join(map(str, feature_vector.optimal_irrigation_days))
    
    context = (
        f"Farm ID: {id} | Crop: {crop} | Season: {season} | "
        f"Days since planting: {n} | Growth stage: {stage}\n"
        f"Satellite (Sentinel-2, {sat_date}): NDVI={ndvi} ({zone}), "
        f"water stress={water_stress}, trend={trend_dir}\n"
        f"Soil: moisture={moisture}% (deficit={deficit}%), "
        f"rainfall last 7d={rain_7d}mm\n"
        f"GDD accumulated: {gdd} | Temp stress days: {stress_days}\n"
        f"Pest risk: {pest}/1.0 | Yield trend: {y_trend}\n"
        f"7-day forecast: rain on {rain_days} days, heat risk {heat_days} days, "
        f"irrigation need score: {irr_score}/10\n"
        f"Optimal irrigation days: [{opt_days}]"
    )
    
    # Token safety check (approx 1 token ~= 4 chars)
    if len(context) > 2000:
        log.warning(f"Farm context string is long ({len(context)} chars), might exceed 500 tokens.")
        
    return context

def build_alert_context(
    change_result: ChangeResult,
    feature_vector: FeatureVector
) -> str:
    """Generates an urgent alert string if severity warrants attention."""
    severity = change_result.severity.lower()
    if severity not in ["moderate", "high"]:
        return ""
        
    pct = round(change_result.alert_zone_pct, 1)
    delta = round(np.mean(change_result.delta_array) if hasattr(change_result.delta_array, "mean") else 0, 3)
    moisture = round(feature_vector.soil_moisture_7d_avg, 1)
    pest = round(feature_vector.pest_risk_score, 2)
    
    alert = (
        f"ALERT: {severity.upper()} vegetation decline detected over {pct}% "
        f"of field. NDVI dropped {delta} significantly. Soil moisture: {moisture}%, "
        f"pest risk: {pest}. Immediate attention recommended."
    )
    return alert

if __name__ == "__main__":
    # Test block
    import numpy as np
    from datetime import datetime
    
    fv = FeatureVector(
        farm_id="F123", feature_timestamp=datetime.now(), feature_version="1.0",
        ndvi_stress_flag=0, ndvi_trend=0.02, ndvi_anomaly_score=0.5, vegetation_zone="healthy",
        ndwi_water_stress=0, spatial_heterogeneity=0.1, soil_moisture_7d_avg=35.0,
        soil_moisture_trend=-0.5, soil_moisture_deficit=0.05, temperature_stress_days=2,
        heat_accumulation_gdd=450.0, rainfall_7d_total=12.0, drought_index=0.1,
        humidity_avg_7d=65.0, rain_probability_7d=0.2, heat_risk_7d=1,
        irrigation_need_score=2.5, optimal_irrigation_days=[3, 4, 5],
        evapotranspiration_est=4.2, frost_risk_7d=0, days_since_planting=45,
        crop_growth_stage="vegetative", yield_trend=1.2, avg_historical_yield=3.5,
        yield_volatility=0.4, pest_risk_score=0.15, days_since_last_irrigation=3,
        irrigation_frequency=1.5, season_encoded=0
    )
    sat = SatelliteAnalysis("F123", datetime.now(), 0.65, 0.05, -0.15, np.zeros((10,10)), False, [0.6, 0.62, 0.65])
    print(build_farm_context_string(fv, sat, {"crop": "Wheat", "season": "Kharif"}))
