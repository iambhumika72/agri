from __future__ import annotations
"""generative/__init__.py — Public exports for the generative package."""
from .llm_client import GeminiClient, get_gemini_client
from .recommendation_engine import RecommendationEngine, FarmRecommendation, create_recommendation_engine
from .multilingual import translate_advisory, translate_sms, detect_farmer_language, SUPPORTED_LANGUAGES

__all__ = [
    "GeminiClient", "get_gemini_client",
    "RecommendationEngine", "FarmRecommendation", "create_recommendation_engine",
    "translate_advisory", "translate_sms", "detect_farmer_language", "SUPPORTED_LANGUAGES",
]
