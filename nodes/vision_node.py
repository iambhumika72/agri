"""
nodes/vision_node.py
====================
LangGraph node for AgriSense that executes the full vision analysis pipeline.
Orchestrates multimodal detection, patch analysis, and pest knowledge retrieval.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from models.pest_retriever import PestRetriever
from models.vision_model import VisionModel
from state import AgriState

log = logging.getLogger(__name__)

def vision_node(state: AgriState) -> AgriState:
    """
    LangGraph node: runs multimodal vision analysis and pest retrieval.
    
    Processes the false-color composite image, performs patch-level analysis 
    on high-alert zones, and retrieves grounded treatment plans if pests are detected.
    """
    start_time = time.time()
    log.info("[vision_node] Starting vision pipeline for farm: %s", state.farm_id)
    
    # 1. Extract inputs from state
    # We assume satellite data is populated in state.satellite (dict)
    satellite_data = state.satellite or {}
    image_path = satellite_data.get("false_color_png_path")
    ndvi_array = satellite_data.get("ndvi_array")
    ndvi_mean = satellite_data.get("ndvi_mean", 0.0)
    ndvi_std = satellite_data.get("ndvi_std", 0.0)
    
    # These come from previous nodes
    change_result = getattr(state, "change_result", None)
    feature_vector = getattr(state, "feature_vector", None)
    
    # 2. Guard: check if required inputs exist
    if not image_path or not Path(image_path).exists():
        log.error("vision_node: Missing or invalid false_color_png_path: %s", image_path)
        state.add_error("vision_node", "False-color composite PNG not found.")
        return state
        
    if feature_vector is None:
        log.error("vision_node: feature_vector missing from state.")
        state.add_error("vision_node", "FeatureVector missing — cannot provide context to vision model.")
        return state

    # 3. Initialise models
    try:
        model = VisionModel()
        retriever = PestRetriever()
    except Exception as e:
        log.error("vision_node: Failed to initialise models: %s", e)
        state.add_error("vision_node", f"Model initialisation failure: {e}")
        return state

    # 4. Run full-field analysis
    try:
        ndvi_stats = {"mean": ndvi_mean, "std": ndvi_std}
        # If change_result is missing, create a dummy one to allow analysis
        if change_result is None:
            from preprocessing.schemas import ChangeResult
            import numpy as np
            change_result = ChangeResult(
                severity="low", 
                alert_zone_pct=0.0, 
                delta_array=np.zeros((1,1)), 
                alert_mask=np.zeros((1,1), dtype=bool),
                geojson_path=""
            )
            
        vision_analysis = model.analyze(image_path, feature_vector, ndvi_stats, change_result)
        state.vision_analysis = vision_analysis
        
        # 5. Run patch-level analysis if alert mask exists
        if hasattr(change_result, 'alert_mask') and ndvi_array is not None:
             state.patch_analyses = model.detect_with_patch_analysis(
                 ndvi_array, 
                 change_result.alert_mask, 
                 image_path, 
                 feature_vector
             )
        elif ndvi_array is not None and change_result.delta_array is not None:
            # Fallback: create mask from delta_array if alert_mask attribute is missing
            alert_mask = change_result.delta_array > 0.2
            state.patch_analyses = model.detect_with_patch_analysis(
                 ndvi_array, 
                 alert_mask, 
                 image_path, 
                 feature_vector
             )

        # 6. Generate health map
        if ndvi_array is not None:
            model.compute_field_health_map(ndvi_array, vision_analysis)
            # Path logic follows models/vision_model.py convention
            date_str = datetime.utcnow().strftime("%Y%m%d")
            state.health_map_path = f"preprocessing/composites/{state.farm_id}_healthmap_{date_str}.png"

        # 7. Pest Retrieval & Treatment Planning
        if vision_analysis.pest_detected:
            log.info("Pest detected: %s (Confidence: %.2f). Retrieving knowledge...", 
                     vision_analysis.pest_type, vision_analysis.pest_confidence)
            
            # Use crop_type from feature_vector if available
            crop_type = getattr(feature_vector, 'crop_type', 'unknown')
            
            pest_cases = retriever.retrieve_similar_cases(
                pest_type=vision_analysis.pest_type,
                crop_type=crop_type,
                growth_stage=vision_analysis.growth_stage_visual
            )
            state.pest_cases = pest_cases
            
            if pest_cases:
                # Use the top retrieved case for the treatment plan
                state.treatment_plan = retriever.get_treatment_urgency(
                    pest_cases[0],
                    vision_analysis.affected_area_pct,
                    vision_analysis.urgency_level
                )
                log.info("Treatment plan generated with priority score: %.2f", 
                         state.treatment_plan.priority_score)

    except Exception as e:
        log.exception("vision_node: Pipeline execution failed: %s", e)
        state.add_error("vision_node", f"Execution error: {e}")

    duration = time.time() - start_time
    log.info("[vision_node] Completed in %.2fs", duration)
    return state

if __name__ == "__main__":
    # Integration smoke test
    logging.basicConfig(level=logging.INFO)
    from preprocessing.schemas import FeatureVector, ChangeResult
    import numpy as np
    
    mock_state = AgriState(farm_id="SMOKE_TEST_FARM")
    mock_state.satellite = {
        "false_color_png_path": "preprocessing/composites/test_sample.png",
        "ndvi_array": np.random.rand(100, 100),
        "ndvi_mean": 0.45
    }
    mock_state.feature_vector = FeatureVector(
        farm_id="SMOKE_TEST_FARM",
        feature_timestamp=datetime.utcnow(),
        feature_version="1.0",
        ndvi_stress_flag=0,
        ndvi_trend=0.0,
        ndvi_anomaly_score=0.0,
        vegetation_zone="high",
        ndwi_water_stress=0,
        spatial_heterogeneity=0.1,
        soil_moisture_7d_avg=25.0,
        soil_moisture_trend=0.0,
        soil_moisture_deficit=0.0,
        temperature_stress_days=0,
        heat_accumulation_gdd=1200.0,
        rainfall_7d_total=10.0,
        drought_index=0.0,
        humidity_avg_7d=60.0,
        rain_probability_7d=0.2,
        heat_risk_7d=0,
        irrigation_need_score=0.1,
        optimal_irrigation_days=[2, 5],
        evapotranspiration_est=4.5,
        frost_risk_7d=0,
        days_since_planting=45,
        crop_growth_stage="vegetative",
        yield_trend=0.0,
        avg_historical_yield=3500.0,
        yield_volatility=0.0,
        pest_risk_score=0.1,
        days_since_last_irrigation=3,
        irrigation_frequency=0.5,
        season_encoded=1
    )
    
    # Node should handle missing file gracefully via add_error
    result = vision_node(mock_state)
    print(f"Errors: {result.errors}")
