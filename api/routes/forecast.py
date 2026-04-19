from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException
import numpy as np

# Internal imports
from ingestion.satellite_ingestor import ingest_sentinel2
from weather_module.weather_client import WeatherClient
from preprocessing.feature_builder import (
    build_satellite_features,
    build_sensor_features,
    build_weather_features,
    build_historical_features,
    assemble_feature_vector
)
from preprocessing.llm_context_builder import build_farm_context_string
from preprocessing.schemas import SatelliteAnalysis, SensorReading, WeatherForecast, FarmHistory

from ..schemas import FarmRequest, FullForecastResponse, SatelliteResponse, WeatherResponse, FeatureVectorResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/forecast", tags=["agriculture"])

@router.post("/", response_model=FullForecastResponse)
async def create_forecast(request: FarmRequest):
    """
    Orchestrates the full AgriSense pipeline:
    1. Ingest Sentinel-2 data
    2. Fetch Weather forecast
    3. Build features
    4. Generate recommendation context
    """
    try:
        # 1. Satellite Ingestion (Punjab BBOX fallback if coords provided)
        # For simplicity, use a 0.1 degree bbox around the coordinates
        bbox = (
            request.longitude - 0.05, request.latitude - 0.05,
            request.longitude + 0.05, request.latitude + 0.05
        )
        
        sat_result = ingest_sentinel2(
            geometry_input=bbox,
            start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            end_date=datetime.now().strftime("%Y-%m-%d"),
            farm_id=request.farm_id
        )
        
        # 2. Weather Forecast
        async with WeatherClient() as client:
            weather_raw = await client.fetch_forecast(
                request.latitude, request.longitude, request.farm_id
            )
            
        # 3. Feature Engineering
        # Prepare inputs for preprocessing
        sat_analysis = SatelliteAnalysis(
            farm_id=request.farm_id,
            acquisition_date=datetime.strptime(sat_result["acquisition_date"], "%Y-%m-%d"),
            ndvi_mean=0.55, # Mocking value if not fully extracted from result
            ndvi_std=0.08,
            ndwi_mean=-0.12,
            ndvi_array=np.random.rand(10, 10),
            stale=sat_result["stale"],
            ndvi_history=[0.5, 0.52, 0.55]
        )
        
        # Mock sensor readings for now (since IoT layer is pending)
        sensor_readings = [
            SensorReading(
                farm_id=request.farm_id,
                timestamp=datetime.now() - timedelta(days=i),
                soil_moisture=35.0,
                soil_temperature=22.0,
                air_temperature=30.0,
                humidity=60.0,
                rainfall_mm=0.0
            ) for i in range(14)
        ]
        
        weather_forecast_obj = WeatherForecast(
            farm_id=request.farm_id,
            forecast_date=datetime.now(),
            forecast_temp_max=weather_raw["daily"]["temperature_2m_max"],
            forecast_temp_min=weather_raw["daily"]["temperature_2m_min"],
            forecast_rainfall=weather_raw["daily"]["precipitation_sum"],
            forecast_humidity=[60.0] * 7, # Mocked
            forecast_wind_speed=weather_raw["daily"]["windspeed_10m_max"]
        )
        
        farm_history = FarmHistory(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            planting_date=request.planting_date,
            season=request.season,
            yield_history=[3.2, 3.5, 3.4],
            pest_events=[],
            irrigation_log=[]
        )
        
        # Build features
        sat_f = build_satellite_features(sat_analysis)
        sen_f = build_sensor_features(sensor_readings)
        wea_f = build_weather_features(weather_forecast_obj)
        hist_f = build_historical_features(farm_history)
        
        fv = assemble_feature_vector(sat_f, sen_f, wea_f, hist_f, request.farm_id)
        
        # 4. LLM Context
        rec_context = build_farm_context_string(fv, sat_analysis, {"crop": request.crop_type, "season": request.season})
        
        # Prepare response
        return FullForecastResponse(
            farm_id=request.farm_id,
            timestamp=datetime.utcnow(),
            satellite=SatelliteResponse(
                acquisition_date=sat_result["acquisition_date"],
                ndvi_mean=sat_analysis.ndvi_mean,
                ndwi_mean=sat_analysis.ndwi_mean,
                cloud_cover_pct=sat_result["cloud_cover_pct"],
                stale=sat_result["stale"],
                geotiff_path=sat_result["geotiff_path"]
            ),
            weather=[
                WeatherResponse(
                    forecast_date=datetime.now() + timedelta(days=i),
                    temp_max=weather_forecast_obj.forecast_temp_max[i],
                    temp_min=weather_forecast_obj.forecast_temp_min[i],
                    rainfall_mm=weather_forecast_obj.forecast_rainfall[i],
                    humidity=weather_forecast_obj.forecast_humidity[i]
                ) for i in range(7)
            ],
            features=FeatureVectorResponse(
                ndvi_trend=fv.ndvi_trend,
                vegetation_zone=fv.vegetation_zone,
                soil_moisture_7d_avg=fv.soil_moisture_7d_avg,
                irrigation_need_score=fv.irrigation_need_score,
                optimal_irrigation_days=fv.optimal_irrigation_days,
                pest_risk_score=fv.pest_risk_score
            ),
            recommendation_context=rec_context
        )
        
    except Exception as e:
        log.error(f"Error creating forecast for {request.farm_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")
