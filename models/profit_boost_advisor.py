"""
models/profit_boost_advisor.py
==============================
Generative advisor for maximizing ROI and net profit using Gemini.
"""

from __future__ import annotations

import logging
from typing import Optional

from generative.recommendation_engine import RecommendationEngine, create_recommendation_engine
from generative.prompt_templates import build_profit_boost_prompt
from preprocessing.schemas import FieldCapabilityProfile
from .profit_calculator import ProfitAnalysis

log = logging.getLogger(__name__)


class ProfitBoostAdvisor:
    """Generates actionable profit-boosting strategies using Generative AI."""

    def __init__(self, engine: Optional[RecommendationEngine] = None) -> None:
        self.engine = engine or create_recommendation_engine()

    def generate_advice(
        self,
        profile: FieldCapabilityProfile,
        analysis: ProfitAnalysis,
        predicted_price: float
    ) -> str:
        """
        Synthesizes a profit boost strategy using the Gemini LLM.
        
        Args:
            profile: The field capability profile (soil, climate, etc.)
            analysis: The financial profit analysis (roi, net profit)
            predicted_price: The forecasted market price for the crop.
            
        Returns:
            A string containing the advisor's strategic suggestions.
        """
        log.info("Generating profit boost advice for crop=%s", analysis.crop)

        # 1. Prepare data for the prompt
        profile_dict = {
            "overall_capability_score": profile.overall_capability_score,
            "ph_level": profile.ph_level,
            "organic_matter": profile.organic_matter,
            "temp_suitability": profile.temp_suitability,
            "historical_pest_pressure": profile.historical_pest_pressure,
        }

        analysis_dict = {
            "crop": analysis.crop,
            "predicted_price": predicted_price,
            "predicted_yield": (analysis.gross_revenue * 100.0) / predicted_price if predicted_price > 0 else 0,
            "total_cost": analysis.total_cost,
            "net_profit": analysis.net_profit,
            "roi_pct": analysis.roi_pct,
        }

        # 2. Build prompts
        system, user = build_profit_boost_prompt(profile_dict, analysis_dict)

        # 3. Generate content via Gemini
        advice = self.engine._safe_generate(
            system=system,
            prompt=user,
            fallback="Focus on optimizing irrigation and nutrient application to safeguard your projected profit."
        )

        log.debug("Profit boost advice generated (length=%d)", len(advice))
        return advice
