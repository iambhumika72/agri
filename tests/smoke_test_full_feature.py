"""
tests/smoke_test_full_feature.py
================================
Comprehensive smoke test for the Crop Profit Forecaster.
Mocks all heavy geospatial dependencies and verifies the entire logic flow.
"""

import sys
import asyncio
import logging
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import numpy as np
import pandas as pd

# 1. MOCK HEAVY DEPENDENCIES (Before any imports)
def mock_heavy(name):
    m = MagicMock()
    sys.modules[name] = m

# Mock failing dependencies to allow test collection
MOCK_MODULES = [
    "rasterio", "rasterio.crs", "rasterio.mask", "rasterio.merge", 
    "rasterio.transform", "rasterio.warp", "rasterio.features",
    "fiona", "geopandas", "faiss", "sentinelsat", "ee", "cv2", 
    "sentence_transformers", "shapely", "shapely.geometry", "shapely.ops"
]

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = MagicMock()

# torch is installed, so no mock needed

# 2. INTERNAL IMPORTS
from state import AgriState, ProfitContext
from nodes.crop_profit_node import crop_profit_node
from ingestion.mandi_price_ingestion import MandiPriceIngester
from preprocessing.schemas import SatelliteAnalysis, WeatherForecast
from api.routes.crop_profit import get_profit_forecast
from api.schemas import FarmRequest

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("smoke_test")

async def run_smoke_test():
    log.info("Starting Comprehensive Smoke Test for Crop Profit Forecaster...")

    # --- TEST 1: Mandi Price Ingestion ---
    log.info("Testing MandiPriceIngester...")
    with patch("httpx.AsyncClient.get") as mock_get, \
         patch("ingestion.mandi_price_ingestion.HistoricalDBConnector") as MockDB:
        
        # Setup mock DB
        db_instance = MockDB.return_value.__enter__.return_value
        
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = {
            "records": [
                {
                    "state": "Punjab", "district": "Ludhiana", "market": "Ludhiana",
                    "commodity": "Wheat", "variety": "Other", "arrival_date": "20/04/2026",
                    "min_price": "2100", "max_price": "2300", "modal_price": "2200"
                }
            ]
        }
        
        ingester = MandiPriceIngester(api_key="fake-key")
        count = await ingester.ingest_recent_prices("Punjab", "Ludhiana", "Wheat")
        log.info(f"Ingested count: {count}")
        assert count == 1
        assert db_instance.insert_record.called
        log.info("✅ MandiPriceIngester verified.")

    # --- TEST 2: Full Node Orchestration ---
    log.info("Testing crop_profit_node...")
    
    # Mocking state inputs
    sat = SatelliteAnalysis(
        farm_id="F1", acquisition_date=datetime.utcnow(),
        ndvi_mean=0.7, ndvi_std=0.04, ndwi_mean=-0.1,
        ndvi_array=np.zeros((1,1)), stale=False, ndvi_history=[0.6, 0.7]
    )
    weather = WeatherForecast(
        farm_id="F1", forecast_date=datetime.utcnow(),
        forecast_temp_max=[30.0]*7, forecast_temp_min=[20.0]*7,
        forecast_rainfall=[5.0]*7, forecast_humidity=[60.0]*7, forecast_wind_speed=[10.0]*7
    )
    state = AgriState(farm_id="F1", satellite=sat, weather=weather)

    with patch("nodes.crop_profit_node.HistoricalDBConnector") as MockDB, \
         patch("nodes.crop_profit_node.PriceForecaster") as MockFC, \
         patch("nodes.crop_profit_node.ProfitBoostAdvisor") as MockAdv:
        
        # Setup DB mock
        db = MockDB.return_value.__enter__.return_value
        db.get_latest_soil_health.return_value = {"state": "Punjab", "district": "Ludhiana", "ph_level": 6.8}
        db.get_pest_history.return_value = pd.DataFrame()
        
        # Setup Forecaster mock
        fc = MockFC.return_value
        price_obj = MagicMock()
        price_obj.predicted_modal_price = 2250.0
        fc.forecast.return_value = price_obj
        
        # Setup Advisor mock
        adv = MockAdv.return_value
        adv.generate_advice.return_value = "Profit looks good. Try intercropping."

        # Run Node
        result = crop_profit_node(state)
        
        assert "profit" in result
        profit_ctx = result["profit"]
        assert isinstance(profit_ctx, ProfitContext)
        assert profit_ctx.profit_boost_advice == "Profit looks good. Try intercropping."
        assert len(profit_ctx.profit_analyses) > 0
        assert "wheat" in profit_ctx.suitability_scores
        log.info("✅ crop_profit_node verified.")

    # --- TEST 3: API Route ---
    log.info("Testing API route /profit/forecast...")
    
    # We call the handler directly
    request = FarmRequest(
        farm_id="F1", latitude=30.9, longitude=75.8,
        crop_type="Wheat", planting_date=datetime.utcnow(), season="Kharif"
    )
    user = {"sub": "test-user"}
    
    with patch("api.routes.crop_profit.crop_profit_node") as mock_node:
        # Re-mock the node output for the API test
        mock_node.return_value = {"profit": profit_ctx}
        
        resp = await get_profit_forecast(request, user)
        assert resp.farm_id == "F1"
        assert resp.profit_boost_advice == "Profit looks good. Try intercropping."
        assert resp.overall_capability_score > 0
        log.info("✅ API Route verified.")

    log.info("\n--- ALL TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    try:
        asyncio.run(run_smoke_test())
    except Exception as e:
        log.exception("Smoke test failed!")
        sys.exit(1)
