from __future__ import annotations

import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from preprocessing.schemas import (
    FeatureVector,
    FeatureValidationError,
    SensorReading,
    WeatherForecast,
    FarmHistory,
    SatelliteAnalysis,
    ChangeResult
)
from preprocessing.feature_builder import (
    build_satellite_features,
    build_sensor_features,
    build_weather_features,
    build_historical_features,
    assemble_feature_vector
)
from preprocessing.time_series_builder import (
    build_ndvi_timeseries,
    align_multimodal_timeseries
)
from preprocessing.llm_context_builder import (
    build_farm_context_string,
    build_alert_context
)

# 1. vegetation_zone classification
def test_vegetation_zone_classification():
    def get_zone(ndvi):
        dummy_sat = SatelliteAnalysis("F1", datetime.now(), ndvi, 0.05, -0.15, np.zeros((2,2)), False, [ndvi])
        return build_satellite_features(dummy_sat)["vegetation_zone"]
        
    assert get_zone(0.65) == "healthy"
    assert get_zone(0.45) == "moderate"
    assert get_zone(0.25) == "stressed"
    assert get_zone(0.10) == "barren"

# 2. drought_index clamping
def test_drought_index_clamping():
    # field_capacity = 0.40
    # moisture=50% (0.50) -> drought_index=0.0
    r1 = SensorReading("F1", datetime.now(), 50.0, 20.0, 25.0, 60.0, 0.0)
    res1 = build_sensor_features([r1], field_capacity=0.40)
    assert res1["drought_index"] == 0.0
    
    # moisture=0% (0.0) -> drought_index=1.0
    r2 = SensorReading("F1", datetime.now(), 0.0, 20.0, 25.0, 60.0, 0.0)
    res2 = build_sensor_features([r2], field_capacity=0.40)
    assert res2["drought_index"] == 1.0

# 3. irrigation_need_score clamping
def test_irrigation_need_score_clamping():
    # Extremes
    sat = {"ndvi_trend": 0, "ndvi_anomaly_score": 0, "ndvi_stress_flag": 0, "vegetation_zone": "healthy", "ndwi_water_stress": 0, "spatial_heterogeneity": 0}
    hist = {"days_since_planting": 10, "crop_growth_stage": "seedling", "yield_trend": 0, "avg_historical_yield": 0, "yield_volatility": 0, "pest_risk_score": 0, "days_since_last_irrigation": 0, "irrigation_frequency": 0, "season_encoded": 0}
    
    # Case: Max need
    sen_max = {"soil_moisture_deficit": 1.0, "soil_moisture_7d_avg": 0, "soil_moisture_trend": 0, "temperature_stress_days": 14, "heat_accumulation_gdd": 500, "rainfall_7d_total": 0, "drought_index": 1.0, "humidity_avg_7d": 20}
    wea_max = {"rain_probability_7d": 0.0, "heat_risk_7d": 7, "optimal_irrigation_days": [], "evapotranspiration_est": 10, "frost_risk_7d": 0}
    
    fv_max = assemble_feature_vector(sat, sen_max, wea_max, hist, "F1")
    assert 0.0 <= fv_max.irrigation_need_score <= 10.0
    
    # Case: Min need
    sen_min = {"soil_moisture_deficit": 0.0, "soil_moisture_7d_avg": 40, "soil_moisture_trend": 0, "temperature_stress_days": 0, "heat_accumulation_gdd": 100, "rainfall_7d_total": 50, "drought_index": 0.0, "humidity_avg_7d": 80}
    wea_min = {"rain_probability_7d": 1.0, "heat_risk_7d": 0, "optimal_irrigation_days": [0,1,2,3,4,5,6], "evapotranspiration_est": 1, "frost_risk_7d": 0}
    
    fv_min = assemble_feature_vector(sat, sen_min, wea_min, hist, "F1")
    assert 0.0 <= fv_min.irrigation_need_score <= 10.0

# 4. GDD computation
def test_gdd_computation():
    # T_max=30, T_min=10, T_base=10 -> GDD_day = (30+10)/2 - 10 = 10
    # In my simplified implementation I used air_temp as avg. 
    # Let's adjust mock to match: air_temp = 20 -> GDD = 20 - 10 = 10.
    readings = []
    start = datetime.now()
    for i in range(7):
        readings.append(SensorReading("F1", start + timedelta(days=i), 25.0, 15.0, 20.0, 60.0, 0.0))
    
    res = build_sensor_features(readings)
    assert res["heat_accumulation_gdd"] == 70.0

# 5. crop_growth_stage
def test_crop_growth_stage():
    def get_stage(days):
        planting = datetime.utcnow() - timedelta(days=days)
        history = FarmHistory("F1", "Wheat", planting, "Kharif", [], [], [])
        return build_historical_features(history)["crop_growth_stage"]
        
    assert get_stage(10) == "seedling"
    assert get_stage(35) == "vegetative"
    assert get_stage(65) == "flowering"
    assert get_stage(95) == "maturation"
    assert get_stage(120) == "harvest_ready"

# 6. NDVI timeseries
def test_ndvi_timeseries():
    now = datetime.now()
    ndvi_history = [(now - timedelta(days=i*5), 0.5 - i*0.01, 0.05) for i in range(10)]
    df = build_ndvi_timeseries(ndvi_history)
    assert "ds" in df.columns
    assert "y" in df.columns
    assert not df["y"].isnull().any()

# 7. align_multimodal_timeseries
def test_align_multimodal_timeseries():
    now = pd.Timestamp.utcnow()
    sensor_df = pd.DataFrame({
        "ds": [now - pd.Timedelta(days=i) for i in range(5)],
        "soil_moisture": [30, 31, 32, 33, 34]
    })
    ndvi_df = pd.DataFrame({
        "ds": [now - pd.Timedelta(days=5)],
        "y": [0.6]
    })
    weather_df = pd.DataFrame({
        "ds": [now + pd.Timedelta(days=i) for i in range(2)],
        "temp": [35, 36]
    })
    
    aligned = align_multimodal_timeseries(ndvi_df, sensor_df, weather_df)
    assert not aligned.index.duplicated().any()
    # Check if NDVI forward filled
    assert aligned.loc[aligned.index.min(), "y"] == 0.6

# 8. FeatureValidationError
def test_feature_validation_error():
    sat = {"ndvi_trend": 0, "ndvi_anomaly_score": 0, "ndvi_stress_flag": 0, "vegetation_zone": "healthy", "ndwi_water_stress": 0, "spatial_heterogeneity": 0}
    sen = {"soil_moisture_deficit": 0.1, "soil_moisture_7d_avg": 30, "soil_moisture_trend": 0, "temperature_stress_days": 0, "heat_accumulation_gdd": 0, "rainfall_7d_total": 0, "drought_index": 0.2, "humidity_avg_7d": 60}
    wea = {"rain_probability_7d": 0.2, "heat_risk_7d": 0, "optimal_irrigation_days": [], "evapotranspiration_est": 4.0, "frost_risk_7d": 0}
    hist = {"days_since_planting": 40, "crop_growth_stage": "vegetative", "yield_trend": 0, "avg_historical_yield": 0, "yield_volatility": 0, "pest_risk_score": 0, "days_since_last_irrigation": 0, "irrigation_frequency": 0, "season_encoded": 0}
    
    # Introduce None
    sat["ndvi_trend"] = None
    with pytest.raises(FeatureValidationError):
        assemble_feature_vector(sat, sen, wea, hist, "F1")

# 9. build_farm_context_string
def test_build_farm_context_string():
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
    sat = SatelliteAnalysis("F123", datetime.now(), 0.65, 0.05, -0.15, np.zeros((2,2)), False, [0.6, 0.62, 0.65])
    context = build_farm_context_string(fv, sat, {"crop": "Wheat", "season": "Kharif"})
    
    assert len(context) < 2000
    assert "F123" in context
    assert "Wheat" in context
    assert "2.5/10" in context

# 10. build_alert_context
def test_build_alert_context():
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
    
    # severity="high" -> non-empty
    cr_high = ChangeResult("high", 15.0, np.array([-0.2]), "path")
    assert "ALERT" in build_alert_context(cr_high, fv)
    
    # severity="low" -> empty
    cr_low = ChangeResult("low", 2.0, np.array([-0.02]), "path")
    assert build_alert_context(cr_low, fv) == ""
