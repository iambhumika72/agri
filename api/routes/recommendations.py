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
    Calls the Gemini generative module for natural language advice.
    """
    log.info(
        "Generating recommendation for farm=%s crop=%s lang=%s",
        request.farm_id, request.crop_type, request.language,
    )

    try:
        from generative.recommendation_engine import RecommendationEngine
        from generative.multilingual import translate_advisory, translate_sms

        engine = RecommendationEngine()

        # Build a simple context from provided fields if no pre-built context
        context = request.farm_context or (
            f"Farm: {request.farm_id} | Crop: {request.crop_type} | Season: {request.season}\n"
            f"Soil moisture: {request.soil_moisture or 'N/A'}% | "
            f"Irrigation need: {request.irrigation_score or 'N/A'}/10 | "
            f"Pest risk: {request.pest_risk or 'N/A'}/1.0 | "
            f"Yield forecast: {request.predicted_yield or 'N/A'} kg/ha"
        )

        # Build minimal mock objects for the engine when full pipeline data is absent
        class _MockIrr:
            farm_id = request.farm_id
            total_water_needed_liters = 0
            next_critical_date = None
            confidence = 0.75
            schedule = []

        class _MockYield:
            farm_id = request.farm_id
            crop_type = request.crop_type
            predicted_yield = request.predicted_yield or 0
            yield_lower = 0
            yield_upper = 0
            trend_component = 0
            key_drivers = []

        class _MockFV:
            farm_id = request.farm_id
            crop_growth_stage = "unknown"
            pest_risk_score = request.pest_risk or 0.0
            irrigation_need_score = request.irrigation_score or 0.0

        recommendation = engine.generate_full_advisory(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            season=request.season,
            farm_context=context,
            irrigation_schedule=_MockIrr(),
            yield_forecast=_MockYield(),
            feature_vector=_MockFV(),
            vision_analysis=None,
        )

        # Translate if needed
        full_advisory = recommendation.full_advisory
        irr_advice = recommendation.irrigation_advice
        yld_advice = recommendation.yield_advice
        pest_advice = recommendation.pest_advice
        sms = recommendation.sms_message if request.include_sms else None

        if request.language != "en":
            full_advisory = translate_advisory(full_advisory, request.language)
            if sms:
                sms = translate_sms(sms, request.language)

        return RecommendationResponse(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            language=request.language,
            generated_at=datetime.utcnow(),
            full_advisory=full_advisory,
            irrigation_advice=irr_advice,
            yield_advice=yld_advice,
            pest_advice=pest_advice,
            sms_message=sms,
            model_used=recommendation.model_used,
            confidence=recommendation.confidence,
        )

    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=f"Gemini API key not configured: {str(e)}")
    except Exception as e:
        log.error("Recommendation generation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Advisory generation failed: {str(e)}")
