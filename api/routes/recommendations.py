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
    language: str = Field(default="en", description="Response language code: en, hi, pa, gu, ta, te, mr, bn, kn")
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
# Helpers
# ---------------------------------------------------------------------------

def _extract_recommendation(final_state):
    """
    Safely extract the FarmRecommendation object from pipeline final_state.

    LangGraph may return the state as an AgriState dataclass or as a raw dict
    depending on the version. This helper handles both forms.

    Returns (FarmRecommendation | None, model_used: str)
    """
    if isinstance(final_state, dict):
        advisory_obj = final_state.get("full_advisory")
        model_used = final_state.get("forecast_model_used") or "Gemini 2.0 Flash"
    else:
        advisory_obj = getattr(final_state, "full_advisory", None)
        model_used = getattr(final_state, "forecast_model_used", None) or "Gemini 2.0 Flash"

    return advisory_obj, model_used


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=RecommendationResponse)
async def generate_recommendation(request: RecommendationRequest):
    """
    Generates an AI-powered farm advisory synthesized from all available data.

    Runs the full AgriSense LangGraph pipeline (historical → forecast →
    vision → recommendation) and returns structured domain advisories.
    """
    log.info("Generating recommendation for farm=%s crop=%s", request.farm_id, request.crop_type)

    try:
        from nodes.orchestrator import AgriSensePipeline
        from generative.multilingual import translate_advisory

        pipeline = AgriSensePipeline()
        final_state = await pipeline.run(farm_id=request.farm_id, language=request.language)

        # Unwrap the FarmRecommendation object from AgriState
        recommendation, model_used = _extract_recommendation(final_state)

        if recommendation is None:
            raise ValueError("Pipeline failed to generate an advisory — no full_advisory in state.")

        # `recommendation` here is a FarmRecommendation dataclass.
        # If somehow the state stored a raw string (fallback), handle gracefully.
        if isinstance(recommendation, str):
            # Degraded path: advisory is a plain string from an error fallback
            full_advisory_text = recommendation
            return RecommendationResponse(
                farm_id=request.farm_id,
                crop_type=request.crop_type,
                language=request.language,
                generated_at=datetime.utcnow(),
                full_advisory=full_advisory_text,
                irrigation_advice="See full advisory.",
                yield_advice="See full advisory.",
                pest_advice="See full advisory.",
                sms_message=None,
                model_used=model_used,
                confidence=0.0,
            )

        # Happy path: FarmRecommendation dataclass
        full_advisory_text = recommendation.full_advisory

        # Translation (non-English requests)
        if request.language != "en":
            try:
                from generative.multilingual import translate_batch, translate_sms, is_supported
                if is_supported(request.language):
                    # Batch translate all advisory fields in one LLM call
                    fields_to_translate = {
                        "full_advisory": full_advisory_text,
                        "irrigation_advice": recommendation.irrigation_advice,
                        "yield_advice": recommendation.yield_advice,
                        "pest_advice": recommendation.pest_advice,
                    }
                    translated_fields = translate_batch(
                        fields_to_translate, request.language
                    )
                    full_advisory_text = translated_fields.get("full_advisory", full_advisory_text)
                    irrigation_advice = translated_fields.get("irrigation_advice", recommendation.irrigation_advice)
                    yield_advice = translated_fields.get("yield_advice", recommendation.yield_advice)
                    pest_advice = translated_fields.get("pest_advice", recommendation.pest_advice)

                    # Translate SMS separately (length constraint)
                    sms_message = None
                    if request.include_sms and recommendation.sms_message:
                        sms_message = translate_sms(recommendation.sms_message, request.language)
            except Exception as te:
                log.warning("Translation to '%s' failed: %s — returning English.", request.language, te)
                irrigation_advice = recommendation.irrigation_advice
                yield_advice = recommendation.yield_advice
                pest_advice = recommendation.pest_advice
                sms_message = recommendation.sms_message if request.include_sms else None
        else:
            irrigation_advice = recommendation.irrigation_advice
            yield_advice = recommendation.yield_advice
            pest_advice = recommendation.pest_advice
            sms_message = recommendation.sms_message if request.include_sms else None

        return RecommendationResponse(
            farm_id=request.farm_id,
            crop_type=request.crop_type,
            language=request.language,
            generated_at=datetime.utcnow(),
            full_advisory=full_advisory_text,
            irrigation_advice=irrigation_advice,
            yield_advice=yield_advice,
            pest_advice=pest_advice,
            sms_message=sms_message,
            model_used=recommendation.model_used or model_used,
            confidence=recommendation.confidence,
        )

    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=f"Gemini API key not configured: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        log.error("Recommendation generation failed: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Advisory generation failed: {str(e)}")
