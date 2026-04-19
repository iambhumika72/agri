from __future__ import annotations

"""
api/routes/recommendations.py
================================
LLM-powered recommendation endpoints for AgriSense.
Synthesizes irrigation, yield, and pest advisories via the generative module.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RecommendationRequest(BaseModel):
    farm_id: str = Field(..., description="Unique farm identifier")
    crop_type: str = Field(..., description="Crop being grown (e.g., Wheat, Rice)")
    season: str = Field(..., description="Current season: kharif | rabi | zaid")
    language: str = Field(default="en", description="Response language code: en, hi, ta, te, mr, bn, kn")
    include_sms: bool = Field(default=False, description="Whether to include an SMS-formatted advisory")

    # Optional pre-computed context (to avoid re-running pipeline)
    farm_context: Optional[str] = Field(default=None, description="Pre-built farm context string")
    soil_moisture: Optional[float] = Field(default=None, description="Current soil moisture %")
    irrigation_score: Optional[float] = Field(default=None, description="Irrigation need score 0-10")
    pest_risk: Optional[float] = Field(default=None, description="Pest risk score 0-1")
    predicted_yield: Optional[float] = Field(default=None, description="Yield forecast kg/ha")


class RecommendationResponse(BaseModel):
    farm_id: str
    crop_type: str
    language: str
    generated_at: datetime
    full_advisory: str
    irrigation_advice: str
    yield_advice: str
    pest_advice: str
    sms_message: Optional[str] = None
    model_used: str
    confidence: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=RecommendationResponse)
async def generate_recommendation(request: RecommendationRequest):
    """
    Generates an AI-powered farm advisory synthesized from all available data.
    """
    log.info("Generating recommendation for farm=%s crop=%s", request.farm_id, request.crop_type)

    try:
        from generative.recommendation_engine import RecommendationEngine
        from generative.multilingual import translate_advisory, translate_sms
        from models.schemas import IrrigationSchedule, YieldForecast
        from preprocessing.schemas import FeatureVector
        from ingestion.farmer_input_ingestion import FarmerInputIngester

        engine = RecommendationEngine()
        
        # If context is missing, we try to build a minimal one from history
        if not request.farm_context:
            ingester = FarmerInputIngester()
            history = await ingester.fetch_farmer_history(request.farm_id, limit=5)
            pest_summary = ", ".join([f"{h['observed_issue']} ({h['severity']})" for h in history if h.get("observed_issue")])
            request.farm_context = (
                f"Farm ID: {request.farm_id}\n"
                f"Crop: {request.crop_type} | Season: {request.season}\n"
                f"Recent Observations: {pest_summary or 'None'}\n"
                f"Current Moisture: {request.soil_moisture or '35.0'}%\n"
            )

        # Prepare structured data for the engine
        irr_schedule = IrrigationSchedule(
            farm_id=request.farm_id,
            total_water_needed_liters=0,
            confidence=0.8,
            schedule=[]
        )
        
        yield_forecast = YieldForecast(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            predicted_yield=request.predicted_yield or 0.0,
            yield_lower=0.0,
            yield_upper=0.0,
            key_drivers=["History", "Weather"]
        )
        
        fv = FeatureVector(
            farm_id=request.farm_id,
            feature_timestamp=datetime.utcnow(),
            crop_growth_stage="vegetative",
            pest_risk_score=request.pest_risk or 0.1,
            irrigation_need_score=request.irrigation_score or 5.0,
            ndvi_trend=0.01,
            vegetation_zone="healthy",
            soil_moisture_7d_avg=request.soil_moisture or 35.0
        )

        recommendation = engine.generate_full_advisory(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            season=request.season,
            farm_context=request.farm_context,
            irrigation_schedule=irr_schedule,
            yield_forecast=yield_forecast,
            feature_vector=fv,
            vision_analysis=None,
        )

        # Translation
        full_advisory = recommendation.full_advisory
        if request.language != "en":
            full_advisory = translate_advisory(full_advisory, request.language)

        return RecommendationResponse(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            language=request.language,
            generated_at=datetime.utcnow(),
            full_advisory=full_advisory,
            irrigation_advice=recommendation.irrigation_advice,
            yield_advice=recommendation.yield_advice,
            pest_advice=recommendation.pest_advice,
            sms_message=recommendation.sms_message if request.include_sms else None,
            model_used=recommendation.model_used,
            confidence=recommendation.confidence,
        )

    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=f"Gemini API key not configured: {str(e)}")
    except Exception as e:
        log.error("Recommendation generation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Advisory generation failed: {str(e)}")
