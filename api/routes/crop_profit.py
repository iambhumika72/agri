"""
api/routes/crop_profit.py
=========================
FastAPI routes for crop suitability and profit forecasting.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
import numpy as np

from fastapi import APIRouter, Depends, HTTPException, status
from api.auth import verify_token
from api.schemas import CropProfitResponse, FarmRequest
from nodes.crop_profit_node import crop_profit_node
from state import AgriState
from preprocessing.schemas import SatelliteAnalysis, WeatherForecast

router = APIRouter(prefix="/profit", tags=["profit"])
log = logging.getLogger(__name__)


@router.post("/forecast", response_model=CropProfitResponse)
async def get_profit_forecast(request: FarmRequest, user: dict = Depends(verify_token)):
    """
    Triggers the profit forecasting pipeline for a given farm.
    
    This endpoint orchestrates the following:
    1. Initialises a transient pipeline state.
    2. Mocks/Fetches prerequisite environment data (satellite/weather).
    3. Executes the 'crop_profit_node' logic.
    4. Returns suitablity scores, financial projections, and strategic advice.
    """
    log.info("API: Profit forecast requested for farm_id=%s by user=%s", request.farm_id, user.get("sub"))
    
    # 1. Prepare transient state
    # In this standalone endpoint, we simulate the satellite and weather context.
    # In the main graph, these would be populated by upstream ingestion nodes.
    
    # Mocking satellite indices for the profit node
    sat_indices = SatelliteAnalysis(
        farm_id=request.farm_id,
        acquisition_date=datetime.utcnow(),
        ndvi_mean=0.65,
        ndvi_std=0.04,
        ndwi_mean=-0.1,
        ndvi_array=np.zeros((1, 1)), # Not used in profit node, only mean/std
        stale=False,
        ndvi_history=[0.60, 0.62, 0.65]
    )
    
    # Mocking weather forecast
    weather_info = WeatherForecast(
        farm_id=request.farm_id,
        forecast_date=datetime.utcnow(),
        forecast_temp_max=[32.0, 31.0, 30.0, 33.0, 34.0, 32.0, 31.0],
        forecast_temp_min=[22.0, 21.0, 20.0, 23.0, 24.0, 22.0, 21.0],
        forecast_rainfall=[0.0, 0.0, 10.0, 5.0, 0.0, 0.0, 2.0],
        forecast_humidity=[50.0] * 7,
        forecast_wind_speed=[12.0] * 7
    )
    
    state = AgriState(
        farm_id=request.farm_id,
        pipeline_run_id=f"profit_api_{int(datetime.utcnow().timestamp())}",
        satellite=sat_indices,
        weather=weather_info
    )
    
    # 2. Execute Node logic
    try:
        # We call the node directly as this is a specific feature-targetted endpoint
        result = crop_profit_node(state)
        profit_ctx = result.get("profit")
        
        if not profit_ctx:
            detail = "; ".join(state.errors) if state.errors else "Unknown internal error in profit node."
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Profit analysis failed: {detail}"
            )
            
        # 3. Format and return response
        return CropProfitResponse(
            farm_id=request.farm_id,
            timestamp=profit_ctx.last_updated,
            suitability_scores=profit_ctx.suitability_scores,
            profit_analyses=profit_ctx.profit_analyses,
            profit_boost_advice=profit_ctx.profit_boost_advice,
            overall_capability_score=profit_ctx.field_profile.get("overall_capability_score", 0.0)
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Fatal error in profit endpoint for farm %s", request.farm_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal Server Error: {str(exc)}"
        )
