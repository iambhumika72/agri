"""
tests/test_crop_profit.py
==========================
Unit and integration tests for the Crop Profit Forecaster.
"""

import sys
from unittest.mock import MagicMock

# Mock failing dependencies to allow test collection without full environment
sys.modules["rasterio"] = MagicMock()
sys.modules["fiona"] = MagicMock()
sys.modules["geopandas"] = MagicMock()
sys.modules["faiss"] = MagicMock()
sys.modules["sentinelsat"] = MagicMock()
sys.modules["ee"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["rasterio.features"] = MagicMock()
sys.modules["rasterio.warp"] = MagicMock()
sys.modules["cv2"] = MagicMock()

import pytest
from datetime import datetime
import numpy as np
import pandas as pd
from unittest.mock import patch

from state import AgriState
from nodes.crop_profit_node import crop_profit_node
from preprocessing.schemas import SatelliteAnalysis, WeatherForecast
from models.profit_calculator import ProfitCalculator
from models.crop_suitability_scorer import CropSuitabilityScorer

@pytest.fixture
def mock_state():
    sat = SatelliteAnalysis(
        farm_id="test_farm",
        acquisition_date=datetime.utcnow(),
        ndvi_mean=0.7,
        ndvi_std=0.03,
        ndwi_mean=-0.15,
        ndvi_array=np.zeros((10, 10)),
        stale=False,
        ndvi_history=[0.65, 0.68, 0.7]
    )
    weather = WeatherForecast(
        farm_id="test_farm",
        forecast_date=datetime.utcnow(),
        forecast_temp_max=[28.0] * 7,
        forecast_temp_min=[18.0] * 7,
        forecast_rainfall=[0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0],
        forecast_humidity=[65.0] * 7,
        forecast_wind_speed=[8.0] * 7
    )
    return AgriState(
        farm_id="test_farm",
        satellite=sat,
        weather=weather
    )

def test_profit_calculator():
    calc = ProfitCalculator()
    # Wheat: yield 3000kg/ha, price 2200/quintal => Revenue = 30 * 2200 = 66000
    # Cost = 38000. Profit = 28000. ROI = 28000/38000 * 100 = 73.68%
    analysis = calc.calculate_profit("wheat", 3000, 2200)
    
    assert analysis.crop == "wheat"
    assert analysis.gross_revenue == 66000.0
    assert analysis.net_profit == 28000.0
    assert round(analysis.roi_pct, 2) == 73.68
    assert round(analysis.break_even_price, 2) == 1266.67

def test_suitability_scorer():
    scorer = CropSuitabilityScorer()
    # Mock profile
    profile = MagicMock()
    profile.overall_capability_score = 0.8
    profile.ph_level = 6.5
    profile.ndvi_stability = 0.9
    
    scores = scorer.score_crops(profile)
    assert "wheat" in scores
    assert 0.0 <= scores["wheat"] <= 1.0
    assert scores["wheat"] > 0.5 # High suitability for 6.5 pH

@patch("nodes.crop_profit_node.HistoricalDBConnector")
@patch("nodes.crop_profit_node.PriceForecaster")
@patch("nodes.crop_profit_node.ProfitBoostAdvisor")
def test_crop_profit_node_basic(MockAdvisor, MockForecaster, MockDB, mock_state):
    # Mock DB
    db_instance = MockDB.return_value.__enter__.return_value
    db_instance.get_latest_soil_health.return_value = {"state": "Punjab", "district": "Patiala", "ph_level": 6.8}
    db_instance.get_pest_history.return_value = pd.DataFrame()
    
    # Mock PriceForecaster
    forecaster_instance = MockForecaster.return_value
    mock_price = MagicMock()
    mock_price.predicted_modal_price = 2300.0
    forecaster_instance.forecast.return_value = mock_price
    
    # Mock Advisor
    advisor_instance = MockAdvisor.return_value
    advisor_instance.generate_advice.return_value = "Test advice"
    
    # Execute node
    result = crop_profit_node(mock_state)
    
    assert "profit" in result
    profit_ctx = result["profit"]
    assert profit_ctx is not None
    assert profit_ctx.profit_boost_advice == "Test advice"
    assert len(profit_ctx.profit_analyses) > 0
    assert profit_ctx.suitability_scores["wheat"] > 0
