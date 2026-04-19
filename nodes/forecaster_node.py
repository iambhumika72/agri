from __future__ import annotations

import logging
import time
from typing import Any, Dict

from models.prophet_forecaster import ProphetForecaster
from models.lstm_forecaster import LSTMForecaster
from models.ensemble_forecaster import EnsembleForecaster
from models.schemas import IrrigationSchedule, YieldForecast

log = logging.getLogger(__name__)


class _SafeFeatureVector:
    """
    Lightweight stand-in used when no FeatureVector is provided in state.
    Provides safe defaults for all fields accessed by ensemble blending.
    """
    drought_index: float = 0.1
    rain_probability_7d: float = 0.3
    pest_risk_score: float = 0.1
    irrigation_need_score: float = 5.0
    soil_moisture_7d_avg: float = 30.0

    def __getattr__(self, name: str) -> Any:
        # Fallback for any unexpected field access
        return 0.0

def forecaster_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node for executing the forecasting pipeline.
    Reads preprocessed data and writes irrigation and yield forecasts to state.
    """
    start_time = time.time()
    
    # 1. Extraction from state
    if isinstance(state, dict):
        aligned_df = state.get("aligned_df")
        feature_vector = state.get("feature_vector") or _SafeFeatureVector()
        farm_metadata = state.get("farm_metadata", {})
        farm_id = farm_metadata.get("farm_id", "unknown_farm")
        crop_type = farm_metadata.get("crop_type", "Wheat")
    else:
        aligned_df = getattr(state, "aligned_df", None)
        feature_vector = getattr(state, "feature_vector", None) or _SafeFeatureVector()
        farm_id = getattr(state, "farm_id", "unknown_farm")
        crop_type = "Wheat" # Default if not in dataclass
    
    if aligned_df is None or aligned_df.empty:
        log.error(f"Aligned DataFrame missing in state for farm {farm_id}. Skipping forecast.")
        return state

    # 2. Initialization
    prophet = ProphetForecaster()
    lstm = LSTMForecaster()
    ensemble = EnsembleForecaster(prophet, lstm)
    
    # 3. Model Selection
    model_mode = ensemble.select_model(aligned_df)
    
    irrigation_schedule = None
    yield_forecast = None
    
    try:
        # 4. Execution
        if model_mode == "prophet":
            irrigation_schedule = prophet.forecast_irrigation_schedule(
                farm_id=farm_id,
                feature_vector=feature_vector,
                future_weather=aligned_df[["ds", "rainfall", "temperature"]] # Sample extraction
            )
            # Yield forecast (assuming model is fitted)
            try:
                yield_forecast = prophet.forecast_yield(farm_id, crop_type)
            except Exception as e:
                log.warning(f"Could not generate yield forecast: {str(e)}")
                
        elif model_mode == "ensemble":
            # Run Prophet
            p_schedule = prophet.forecast_irrigation_schedule(
                farm_id=farm_id, feature_vector=feature_vector, 
                future_weather=aligned_df[["ds", "rainfall", "temperature"]]
            )
            # Run LSTM
            l_pred = lstm.predict(aligned_df.tail(30))
            
            # Blend
            irrigation_schedule = ensemble.blend_irrigation_forecast(
                p_schedule, l_pred, feature_vector
            )
            
            # Yield Blend
            try:
                p_yield = prophet.forecast_yield(farm_id, crop_type)
                yield_forecast = ensemble.blend_yield_forecast(p_yield, l_pred, feature_vector)
            except Exception as e:
                log.warning(f"Could not generate ensemble yield forecast: {str(e)}")

        # 5. Writing to state
        if isinstance(state, dict):
            state["irrigation_schedule"] = irrigation_schedule
            state["yield_forecast"] = yield_forecast
            state["forecast_model_used"] = model_mode
        else:
            state.irrigation_schedule = irrigation_schedule
            state.yield_forecast = yield_forecast
            state.forecast_model_used = model_mode
        
    except Exception as e:
        log.error(f"Forecasting pipeline failed for {farm_id}: {str(e)}", exc_info=True)
        
    execution_time = time.time() - start_time
    log.info(f"Forecaster Node executed in {execution_time:.2f}s for farm {farm_id} using {model_mode} mode.")
    
    return state

if __name__ == "__main__":
    # Test block
    import pandas as pd
    import numpy as np
    from datetime import datetime
    
    synthetic_df = pd.DataFrame({
        "ds": pd.date_range("2024-01-01", periods=40, freq="D"),
        "soil_moisture": np.random.uniform(25, 45, 40),
        "rainfall": np.random.uniform(0, 5, 40),
        "temperature": np.random.uniform(20, 30, 40),
        "evapotranspiration_est": np.random.uniform(2, 4, 40)
    })
    # Add dummy feature cols for LSTM
    for col in ["ndvi_mean", "humidity", "gdd", "drought_index", "lag_1d", "lag_7d"]:
        synthetic_df[col] = np.random.rand(40)
        
    test_state = {
        "aligned_df": synthetic_df,
        "farm_metadata": {"farm_id": "TEST_001", "crop_type": "Rice"}
    }
    
    updated_state = forecaster_node(test_state)
    print(f"Model Used: {updated_state.get('forecast_model_used')}")
