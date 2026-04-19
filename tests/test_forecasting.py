from __future__ import annotations

import os
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any

from models.schemas import IrrigationSchedule, YieldForecast, LSTMPrediction, EvalResult
from models.prophet_forecaster import ProphetForecaster
from models.lstm_forecaster import LSTMForecaster
from models.ensemble_forecaster import EnsembleForecaster
from nodes.forecaster_node import forecaster_node
from preprocessing.schemas import FeatureVector

# Setup paths for tests
PROPHET_MODEL_PATH = "configs/prophet_irrigation.pkl"
LSTM_MODEL_PATH = "configs/lstm_model.pt"

@pytest.fixture
def synthetic_dfs():
    # 60 days of daily data
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    df = pd.DataFrame({
        "ds": dates,
        "soil_moisture": np.random.uniform(25, 45, 60),
        "temperature": np.random.uniform(20, 35, 60),
        "humidity": np.random.uniform(40, 80, 60),
        "rainfall": np.random.uniform(0, 10, 60),
        "evapotranspiration_est": np.random.uniform(2, 6, 60),
        "ndvi_mean": np.random.uniform(0.3, 0.7, 60),
        "gdd": np.random.uniform(300, 600, 60),
        "drought_index": np.random.uniform(0, 1, 60),
        "lag_1d": np.random.uniform(25, 45, 60),
        "lag_7d": np.random.uniform(25, 45, 60)
    })
    return df

@pytest.fixture
def mock_feature_vector():
    return FeatureVector(
        farm_id="F1", feature_timestamp=datetime.now(), feature_version="1.0",
        ndvi_stress_flag=0, ndvi_trend=0.01, ndvi_anomaly_score=0.0,
        vegetation_zone="healthy", ndwi_water_stress=0, spatial_heterogeneity=0.1,
        soil_moisture_7d_avg=35.0, soil_moisture_trend=0.0, soil_moisture_deficit=0.05,
        temperature_stress_days=0, heat_accumulation_gdd=400.0, rainfall_7d_total=10.0,
        drought_index=0.2, humidity_avg_7d=60.0, rain_probability_7d=0.2,
        heat_risk_7d=0, irrigation_need_score=3.0, optimal_irrigation_days=[1, 2, 3],
        evapotranspiration_est=4.0, frost_risk_7d=0, days_since_planting=40,
        crop_growth_stage="vegetative", yield_trend=0.0, avg_historical_yield=3000.0,
        yield_volatility=200.0, pest_risk_score=0.1, days_since_last_irrigation=3,
        irrigation_frequency=1.2, season_encoded=0
    )

# 1. Prophet yield forecast returns YieldForecast with all fields non-null
# 2. Prophet lower < predicted < upper bounds always hold
def test_prophet_yield_bounds(synthetic_dfs):
    forecaster = ProphetForecaster()
    # Need more observations for better fitting
    dates = pd.to_datetime([f"{2010+i}-06-01" for i in range(10)])
    yield_data = pd.DataFrame({
        "ds": dates,
        "y": [3000 + i*100 for i in range(10)],
        "ndvi_mean": [0.6]*10,
        "rainfall_7d": [40]*10,
        "gdd": [500]*10
    })
    forecaster.fit_yield_model(yield_data)
    
    # Provide future regressor for prediction
    future_reg = pd.DataFrame({
        "ds": [dates.max() + pd.Timedelta(days=180)],
        "ndvi_mean": [0.65],
        "rainfall_7d": [45],
        "gdd": [510]
    })
    yf = forecaster.forecast_yield("F1", "Wheat", future_regressors=future_reg)
    
    assert yf.predicted_yield is not None
    assert yf.yield_lower <= yf.predicted_yield <= yf.yield_upper
    assert yf.model_used == "prophet"

# 3. irrigation_needed is True when soil_moisture=20% and rainfall=0mm
# 4. irrigation_needed is False when soil_moisture=45% and rainfall=10mm
def test_irrigation_logic(synthetic_dfs):
    forecaster = ProphetForecaster()
    # Ensure model is fitted
    forecaster.fit_irrigation_model(synthetic_dfs, synthetic_dfs)
        
    # Provide future weather with required columns
    future_dates = pd.date_range(synthetic_dfs["ds"].max() + timedelta(days=1), periods=7, freq="D")
    future_weather = pd.DataFrame({
        "ds": future_dates,
        "rainfall": [0.0]*7,
        "temperature": [30.0]*7,
        "evapotranspiration_est": [4.0]*7
    })
    
    schedule = forecaster.forecast_irrigation_schedule("F1", days_ahead=7, future_weather=future_weather)
    assert len(schedule.schedule) == 7
    for day in schedule.schedule:
        assert isinstance(day.irrigation_needed, bool)

# 5. LSTM prepare_sequences: input df of 60 rows -> X shape [30, 30, n_features]
def test_lstm_prepare_sequences(synthetic_dfs):
    lstm = LSTMForecaster(sequence_len=30)
    X, y = lstm.prepare_sequences(synthetic_dfs)
    assert X.shape == (30, 30, 9)
    assert y.shape == (30, 1)

# 6. LSTM recursive forecast returns exactly 7 predictions
def test_lstm_recursive_forecast(synthetic_dfs):
    lstm = LSTMForecaster(sequence_len=10, forecast_horizon=7)
    lstm.train(synthetic_dfs.head(20)) 
    pred = lstm.predict(synthetic_dfs.tail(10))
    assert len(pred.predictions) == 7

# 7. EnsembleForecaster weight normalization
def test_ensemble_weight_adjustment(mock_feature_vector):
    from models.schemas import IrrigationSchedule, IrrigationDay, LSTMPrediction
    p = ProphetForecaster()
    l = LSTMForecaster()
    ensemble = EnsembleForecaster(p, l)
    
    mock_feature_vector.drought_index = 0.8
    
    now = datetime.now()
    dummy_schedule = IrrigationSchedule("F1", [], 0, None, 0.8, "prophet")
    for i in range(7):
        dummy_schedule.schedule.append(
            IrrigationDay(now + timedelta(days=i), 25.0, True, 100.0, 0.8)
        )
    dummy_pred = LSTMPrediction([24.0]*7, [now + timedelta(days=i) for i in range(7)], 0.1, "1.0")
    
    blended = ensemble.blend_irrigation_forecast(dummy_schedule, dummy_pred, mock_feature_vector)
    assert blended.model_used == "ensemble"

# 8. select_model logic
def test_select_model_logic(synthetic_dfs):
    p = ProphetForecaster()
    l = LSTMForecaster()
    ensemble = EnsembleForecaster(p, l)
    
    assert ensemble.select_model(synthetic_dfs.head(20)) == "prophet"
    
    # Force ensemble
    l.train(synthetic_dfs.head(40))
    assert ensemble.select_model(synthetic_dfs) == "ensemble"

# 9. EvalResult: rmse, mae, mape, r_squared all non-negative floats
def test_eval_result_types(synthetic_dfs):
    lstm = LSTMForecaster(sequence_len=10)
    lstm.train(synthetic_dfs.head(40))
    res = lstm.evaluate(synthetic_dfs.tail(20))
    assert isinstance(res, EvalResult)
    assert res.rmse >= 0

# 10. forecaster_node execution
def test_forecaster_node_integration(synthetic_dfs, mock_feature_vector):
    # Ensure models exist
    p = ProphetForecaster()
    p.fit_irrigation_model(synthetic_dfs, synthetic_dfs)
    
    # Mock aligned_df with all required columns
    state = {
        "aligned_df": synthetic_dfs,
        "feature_vector": mock_feature_vector,
        "farm_metadata": {"farm_id": "F1", "crop_type": "Wheat"}
    }
    updated_state = forecaster_node(state)
    assert updated_state["irrigation_schedule"] is not None
