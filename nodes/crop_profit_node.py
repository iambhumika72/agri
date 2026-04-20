"""
nodes/crop_profit_node.py
=========================
LangGraph node for orchestrating crop suitability and profit forecasting.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from state import AgriState, ProfitContext
from preprocessing.field_capability_profiler import FieldCapabilityProfiler
from models.crop_suitability_scorer import CropSuitabilityScorer
from models.price_forecaster import PriceForecaster
from models.profit_calculator import ProfitCalculator
from models.profit_boost_advisor import ProfitBoostAdvisor
from historical_db.db_connector import HistoricalDBConnector

log = logging.getLogger(__name__)


def crop_profit_node(state: AgriState) -> Dict[str, Any]:
    """
    Orchestrates the profit forecasting pipeline.
    
    Processing Steps:
    1. Agregates satellite, weather, and historical data into a FieldCapabilityProfile.
    2. Scores all supported crops based on the profile.
    3. Forecasts market prices using the PriceForecaster (Prophet).
    4. Calculates ROI and profitability metrics.
    5. Generates high-level strategic advice using ProfitBoostAdvisor (Gemini).
    
    Args:
        state: The current AgriState in the LangGraph workflow.
        
    Returns:
        Update dictionary for the LangGraph state containing the 'profit' context.
    """
    farm_id = state.farm_id
    log.info("Executing crop_profit_node — farm_id=%s", farm_id)

    # 1. Validation: Ensure prerequisites are present
    if not state.satellite or not state.weather:
        log.warning("Prerequisite data (satellite/weather) missing for node. Skipping.")
        state.add_error("crop_profit_node", "Missing satellite or weather data.")
        return {"profit": None}

    try:
        # 2. Data Gathering
        # In a real run, these objects are already in state. 
        # We assume they match the dataclass shapes defined in models.schemas
        satellite_data = state.satellite
        weather_data = state.weather
        
        # We need historical context for pests and soil
        soil_data = {}
        pest_records = []
        
        with HistoricalDBConnector() as db:
            # Try to get soil health
            soil_data = db.get_latest_soil_health(farm_id) or {}
            
            # Get historical pests (last 2 years)
            end_date = datetime.utcnow().date()
            start_date = end_date.replace(year=end_date.year - 2)
            pest_df = db.get_pest_history(farm_id, start_date, end_date)
            if not pest_df.empty:
                pest_records = pest_df.reset_index().to_dict('records')

        # 3. Component Initialisation
        profiler = FieldCapabilityProfiler()
        suitability_scorer = CropSuitabilityScorer()
        price_forecaster = PriceForecaster()
        profit_calculator = ProfitCalculator()
        advisor = ProfitBoostAdvisor()

        # 4. Pipeline Execution
        # A. Profile Field
        profile = profiler.generate_profile(
            farm_id=farm_id,
            satellite=satellite_data,
            weather=weather_data,
            soil=soil_data,
            pest_history=pest_records
        )

        # B. Score Crops
        suitability_scores = suitability_scorer.score_crops(profile)

        # C. Financial Projections
        state_name = soil_data.get("state", "Maharashtra") # Fallback
        district_name = soil_data.get("district", "Nashik")
        
        analyses = []
        best_crop_analysis = None
        highest_roi = -100.0

        for crop, score in suitability_scores.items():
            # Only analyze crops with >40% suitability
            if score < 0.4:
                continue
                
            # Forecast price
            price_forecast = price_forecaster.forecast(state_name, district_name, crop)
            
            # Estimate yield based on suitability score if no direct forecast exists
            # Baseline: 3500 kg/ha for a score of 1.0
            estimated_yield = score * 3500.0
            
            analysis = profit_calculator.calculate_profit(
                crop=crop,
                predicted_yield_kg_ha=estimated_yield,
                predicted_price_inr_quintal=price_forecast.predicted_modal_price
            )
            
            analyses.append(analysis.to_dict())
            
            if analysis.roi_pct > highest_roi:
                highest_roi = analysis.roi_pct
                best_crop_analysis = analysis

        # D. Strategic Advice
        profit_boost_advice = ""
        if best_crop_analysis:
            # We fetch the forecasted price again for advisor context
            fc = price_forecaster.forecast(state_name, district_name, best_crop_analysis.crop)
            profit_boost_advice = advisor.generate_advice(
                profile=profile,
                analysis=best_crop_analysis,
                predicted_price=fc.predicted_modal_price
            )
        else:
            profit_boost_advice = "Field capability score is currently too low for a reliable profit forecast. Focus on soil restoration."

        # 5. Result Package
        profit_context = ProfitContext(
            field_profile=profile.__dict__,
            suitability_scores=suitability_scores,
            profit_analyses=analyses,
            profit_boost_advice=profit_boost_advice,
            last_updated=datetime.utcnow()
        )

        log.info("crop_profit_node execution successful for %s", farm_id)
        return {"profit": profit_context}

    except Exception as exc:
        log.exception("Fatal error in crop_profit_node: %s", exc)
        state.add_error("crop_profit_node", str(exc))
        return {"profit": None}
