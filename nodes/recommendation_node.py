from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Optional

from state import AgriState
from generative.recommendation_engine import RecommendationEngine
from preprocessing.llm_context_builder import build_farm_context_string

log = logging.getLogger(__name__)

def recommendation_node(state: AgriState) -> AgriState:
    """
    LangGraph node: generates the final recommendation advisory using LLM.
    Synthesizes historical context, vision analysis, and forecasting results.
    """
    log.info("recommendation_node started for farm_id=%s", state.farm_id)
    
    try:
        engine = RecommendationEngine()
        
        # 1. Build farm context string if not already present
        # We need crop_type and season which might be in historical context or state
        crop_type = "Wheat" # Default
        season = "kharif"   # Default
        
        if state.historical and state.historical.farm_summary:
            crop_type = state.historical.farm_summary.get("crop_type", crop_type)
            season = state.historical.farm_summary.get("season", season)
            
        farm_context = ""
        if state.feature_vector and state.satellite:
            # Note: satellite in AgriState might be a dict or a SatelliteAnalysis object
            # Our vision_node uses state.satellite as a SatelliteAnalysis object
            from preprocessing.schemas import SatelliteAnalysis
            if isinstance(state.satellite, SatelliteAnalysis):
                farm_context = build_farm_context_string(
                    state.feature_vector, 
                    state.satellite, 
                    {"crop": crop_type, "season": season}
                )

        # 2. Invoke recommendation engine
        recommendation = engine.generate_full_advisory(
            farm_id=state.farm_id,
            crop_type=crop_type,
            season=season,
            farm_context=farm_context,
            irrigation_schedule=state.irrigation_schedule,
            yield_forecast=state.yield_forecast,
            feature_vector=state.feature_vector,
            vision_analysis=state.vision_analysis,
            language=state.language,
        )
        
        state.full_advisory = recommendation
        log.info("recommendation_node completed successfully.")
        
    except Exception as e:
        log.error("recommendation_node failed: %s", str(e), exc_info=True)
        state.add_error("recommendation_node", str(e))
        
    return state
