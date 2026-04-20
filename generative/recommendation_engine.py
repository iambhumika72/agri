from __future__ import annotations

"""
generative/recommendation_engine.py
=====================================
Core LLM recommendation synthesis for AgriSense.
Orchestrates context → prompt → Gemini → structured recommendation.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .llm_client import GeminiClient, get_gemini_client
from .prompt_templates import (
    build_full_advisory_prompt,
    build_irrigation_prompt,
    build_pest_prompt,
    build_yield_prompt,
    SMS_TEMPLATE,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------

@dataclass
class FarmRecommendation:
    """Structured output from the recommendation engine."""
    farm_id: str
    crop_type: str
    generated_at: datetime = field(default_factory=datetime.utcnow)

    # Primary advisory text (for dashboard)
    full_advisory: str = ""

    # Per-domain advisories
    irrigation_advice: str = ""
    yield_advice: str = ""
    pest_advice: str = ""

    # SMS-formatted (Twilio delivery)
    sms_message: str = ""

    # Metadata
    model_used: str = "gemini-2.0-flash"
    confidence: float = 0.0
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """
    Orchestrates the full AgriSense recommendation synthesis pipeline.
    Takes preprocessed state data, builds prompts, calls Gemini, and returns
    structured `FarmRecommendation` objects.
    """

    def __init__(self, client: Optional[GeminiClient] = None) -> None:
        self.client = client or get_gemini_client()

    def _safe_generate(self, system: str, prompt: str, fallback: str = "") -> str:
        """Wraps LLM generation with error handling; returns fallback on failure."""
        try:
            return self.client.generate(
                prompt=prompt,
                system_instruction=system,
                temperature=0.3,
                max_tokens=512,
            )
        except Exception as exc:
            log.warning("LLM generation failed: %s — using fallback text.", exc)
            return fallback

    @staticmethod
    def _coerce_vision_analysis(vision_analysis: Any) -> Optional[Dict]:
        """
        Normalise vision_analysis to a plain dict regardless of whether it is a
        VisionAnalysis dataclass, a satellite_vision_node dict, or None.
        """
        if vision_analysis is None:
            return None
        if isinstance(vision_analysis, dict):
            return vision_analysis
        # Assume VisionAnalysis (or any) dataclass — convert via __dict__
        try:
            import dataclasses
            return dataclasses.asdict(vision_analysis)
        except Exception:
            # Last resort: attribute-based extraction
            return {
                "likely_cause": getattr(vision_analysis, "pest_type", "unknown"),
                "stressed_zone_pct": getattr(vision_analysis, "affected_area_pct", 0.0),
                "health_score": getattr(vision_analysis, "health_score", 50),
                "pest_detected": getattr(vision_analysis, "pest_detected", False),
                "confidence": getattr(vision_analysis, "pest_confidence", 0.0),
                "agronomist_note": getattr(vision_analysis, "recommended_action", ""),
            }

    def generate_full_advisory(
        self,
        farm_id: str,
        crop_type: str,
        season: str,
        farm_context: str,
        irrigation_schedule: Any,      # IrrigationSchedule dataclass
        yield_forecast: Any,           # YieldForecast dataclass
        feature_vector: Any,           # FeatureVector dataclass
        vision_analysis: Any = None,   # VisionAnalysis dataclass OR dict OR None
        language: str = "en",          # ISO 639-1 language code
    ) -> FarmRecommendation:
        """
        Main entry point: generates the complete farm advisory.

        Parameters
        ----------
        farm_id : str
        crop_type : str
        season : str
        farm_context : str — structured context string from llm_context_builder
        irrigation_schedule : IrrigationSchedule
        yield_forecast : YieldForecast
        feature_vector : FeatureVector
        vision_analysis : dict | None — from satellite_vision_node
        """
        log.info("Generating full advisory for farm=%s crop=%s", farm_id, crop_type)

        # Normalise vision_analysis to a plain dict for prompt builders
        vision_dict = self._coerce_vision_analysis(vision_analysis)

        # --- Build data dicts for prompts ---
        growth_stage = feature_vector.crop_growth_stage if feature_vector else "unknown"

        irr_data = {}
        if irrigation_schedule:
            irr_data = {
                "next_critical_date": str(irrigation_schedule.next_critical_date or "N/A"),
                "total_water_needed_liters": irrigation_schedule.total_water_needed_liters,
                "confidence": irrigation_schedule.confidence,
                "irrigation_need_score": feature_vector.irrigation_need_score if feature_vector else 0,
                "moisture_forecast": ", ".join(
                    f"{d.predicted_soil_moisture:.1f}%"
                    for d in (irrigation_schedule.schedule or [])
                ),
            }

        yld_data = {}
        if yield_forecast:
            yld_data = {
                "predicted_yield": yield_forecast.predicted_yield,
                "yield_lower": yield_forecast.yield_lower,
                "yield_upper": yield_forecast.yield_upper,
                "key_drivers": yield_forecast.key_drivers,
                "trend_component": yield_forecast.trend_component,
            }

        pest_data = {}
        if feature_vector:
            pest_data = {
                "pest_risk_score": feature_vector.pest_risk_score,
                "likely_cause": (vision_dict or {}).get("likely_cause", "unknown"),
                "stressed_zone_pct": (vision_dict or {}).get("stressed_zone_pct", 0.0),
                "growth_stage": growth_stage,
            }

        # --- Generate per-domain advisories (parallel in production would use asyncio) ---
        irr_system, irr_user = build_irrigation_prompt(farm_context, irr_data)
        yld_system, yld_user = build_yield_prompt(farm_context, yld_data)
        pest_system, pest_user = build_pest_prompt(farm_context, pest_data)
        full_system, full_user = build_full_advisory_prompt(
            farm_context=farm_context,
            farm_id=farm_id,
            crop_type=crop_type,
            season=season,
            growth_stage=growth_stage,
            irrigation_data=irr_data,
            yield_data=yld_data,
            pest_data=pest_data,
            vision_analysis=vision_dict,  # always a dict for prompt builder
        )

        # If language is supported and not English, append language instruction to system prompt
        if language != "en":
            from .multilingual import SUPPORTED_LANGUAGES, _TRANSLATION_INSTRUCTIONS
            if language in SUPPORTED_LANGUAGES:
                lang_name = SUPPORTED_LANGUAGES[language]
                lang_instruction = _TRANSLATION_INSTRUCTIONS.get(language, "")
                full_system += (
                    f"\n\nIMPORTANT: Generate your entire response in {lang_name}. "
                    f"{lang_instruction} "
                    "Keep numbers, units (kg, mm, liters), crop names, and technical terms in English."
                )

        irrigation_advice = self._safe_generate(irr_system, irr_user, "Irrigation data unavailable.")
        yield_advice = self._safe_generate(yld_system, yld_user, "Yield forecast unavailable.")
        pest_advice = self._safe_generate(pest_system, pest_user, "Pest data unavailable.")
        full_advisory = self._safe_generate(full_system, full_user, "Advisory generation failed.")

        # --- SMS summary ---
        pest_level = "Low"
        if feature_vector and feature_vector.pest_risk_score > 0.6:
            pest_level = "HIGH ⚠️"
        elif feature_vector and feature_vector.pest_risk_score > 0.3:
            pest_level = "Medium"

        irr_action = f"Irrigate on {irr_data.get('next_critical_date', 'N/A')}" if irr_data else "Check soil"
        yld_summary = f"{round(yld_data.get('predicted_yield', 0))} kg/ha" if yld_data else "N/A"

        sms = SMS_TEMPLATE.substitute(
            farm_id=farm_id,
            irrigation_action=irr_action,
            yield_summary=yld_summary,
            pest_level=pest_level,
        )

        # Confidence from irrigation model
        confidence = irrigation_schedule.confidence if irrigation_schedule else 0.0

        return FarmRecommendation(
            farm_id=farm_id,
            crop_type=crop_type,
            full_advisory=full_advisory,
            irrigation_advice=irrigation_advice,
            yield_advice=yield_advice,
            pest_advice=pest_advice,
            sms_message=sms,
            model_used=self.client.model_name,
            confidence=confidence,
        )

    def generate_quick_alert(
        self,
        farm_id: str,
        alert_context: str,
        alert_type: str = "general",
    ) -> str:
        """
        Generates a short, urgent alert message for immediate delivery.
        Used when change detection detects sudden vegetation decline.
        """
        system = (
            "You are AgriSense. Write an urgent but calm alert for a farmer. "
            "Max 2 sentences. Be specific about what to check."
        )
        prompt = f"Farm {farm_id} | Alert type: {alert_type}\n\n{alert_context}"
        return self._safe_generate(system, prompt, f"ALERT: Check your {alert_type} immediately — {farm_id}")


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_recommendation_engine() -> RecommendationEngine:
    """Returns a default RecommendationEngine instance."""
    return RecommendationEngine(client=get_gemini_client())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    engine = create_recommendation_engine()
    try:
        rec = engine.generate_quick_alert(
            farm_id="TEST_001",
            alert_context="NDVI dropped 0.15 over the past 5 days. Soil moisture at 18%. Rainfall forecast: 0mm.",
            alert_type="drought",
        )
        print("Quick Alert:", rec)
    except EnvironmentError as e:
        print(f"Skipping live test (no API key): {e}")
