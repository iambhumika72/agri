"""
api/routes/language.py
========================
Language utility endpoints for the AgriSense frontend.
"""

from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/language", tags=["language"])

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English",   "native": "English",    "region": "All India"},
    {"code": "hi", "name": "Hindi",     "native": "हिन्दी",      "region": "UP · MP · Bihar"},
    {"code": "pa", "name": "Punjabi",   "native": "ਪੰਜਾਬੀ",      "region": "Punjab · Haryana"},
    {"code": "mr", "name": "Marathi",   "native": "मराठी",        "region": "Maharashtra"},
    {"code": "gu", "name": "Gujarati",  "native": "ગુજરાતી",     "region": "Gujarat"},
    {"code": "kn", "name": "Kannada",   "native": "ಕನ್ನಡ",       "region": "Karnataka"},
    {"code": "te", "name": "Telugu",    "native": "తెలుగు",      "region": "Andhra · Telangana"},
    {"code": "ta", "name": "Tamil",     "native": "தமிழ்",       "region": "Tamil Nadu"},
    {"code": "bn", "name": "Bengali",   "native": "বাংলা",       "region": "West Bengal"},
]


class LanguageInfo(BaseModel):
    code: str
    name: str
    native: str
    region: str


@router.get("/", response_model=list[LanguageInfo])
async def list_supported_languages():
    """Returns the list of all languages supported by the AgriSense platform."""
    return SUPPORTED_LANGUAGES


@router.post("/translate-text")
async def translate_text(
    text: str,
    target_language: str,
):
    """
    Translates arbitrary text to the target language using Gemini.
    Useful for translating farmer-submitted notes or UI content on demand.
    """
    if target_language == "en":
        return {"translated": text, "language": "en"}
    try:
        from generative.multilingual import translate_advisory, is_supported
        if not is_supported(target_language):
            return {"translated": text, "language": "en", "warning": f"Language '{target_language}' not supported"}
        translated = translate_advisory(text, target_language)
        return {"translated": translated, "language": target_language}
    except Exception as e:
        return {"translated": text, "language": "en", "error": str(e)}
