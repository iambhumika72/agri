from __future__ import annotations

"""
generative/multilingual.py
============================
Regional language translation for AgriSense advisories.
Supports Hindi, Tamil, Telugu, Marathi, Bengali, and Kannada
using the Gemini API for high-quality agricultural context translation.
"""

import logging
from typing import Optional

from .llm_client import GeminiClient, get_gemini_client

log = logging.getLogger(__name__)

# Supported language codes and their display names
SUPPORTED_LANGUAGES: dict[str, str] = {
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "bn": "Bengali",
    "kn": "Kannada",
    "en": "English",  # passthrough
}

# Language-specific instructions for agricultural context
_TRANSLATION_INSTRUCTIONS: dict[str, str] = {
    "hi": (
        "Translate to simple, clear Hindi (Hindustani) as spoken by farmers in rural India. "
        "Use common agricultural terms in Hindi. Avoid overly formal or literary Hindi. "
        "Keep numbers and measurements in English (e.g., kg, mm, liters)."
    ),
    "ta": (
        "Translate to Tamil as spoken by farmers in Tamil Nadu and Sri Lanka. "
        "Use common agricultural words a village farmer would understand. "
        "Keep numbers and units in English."
    ),
    "te": (
        "Translate to Telugu as spoken by farmers in Andhra Pradesh and Telangana. "
        "Use everyday farming vocabulary. Keep numbers and units in English."
    ),
    "mr": (
        "Translate to Marathi as spoken by farmers in Maharashtra. "
        "Use simple, conversational Marathi suitable for village-level communication. "
        "Keep numbers and units in English."
    ),
    "bn": (
        "Translate to Bengali (Bangla) as spoken by farmers in West Bengal and Bangladesh. "
        "Use simple, clear language a rural farmer would understand. "
        "Keep numbers and units in English."
    ),
    "kn": (
        "Translate to Kannada as spoken by farmers in Karnataka. "
        "Use simple, rural farming vocabulary. Keep numbers and units in English."
    ),
}


def translate_advisory(
    text: str,
    target_language: str,
    client: Optional[GeminiClient] = None,
) -> str:
    """
    Translates an advisory text to the target regional language.

    Parameters
    ----------
    text : str — the English advisory text to translate
    target_language : str — ISO 639-1 language code (e.g., 'hi', 'ta', 'te')
    client : GeminiClient | None — reuses existing client if provided

    Returns
    -------
    str — translated text, or original text with a warning if translation fails
    """
    if target_language == "en":
        return text

    if target_language not in SUPPORTED_LANGUAGES:
        log.warning(
            "Unsupported language code '%s'. Supported: %s. Returning English.",
            target_language,
            list(SUPPORTED_LANGUAGES.keys()),
        )
        return text

    lang_name = SUPPORTED_LANGUAGES[target_language]
    instruction = _TRANSLATION_INSTRUCTIONS.get(target_language, f"Translate to {lang_name}.")

    system_prompt = (
        f"You are a professional agricultural translator specializing in {lang_name}. "
        f"{instruction} "
        "Preserve the structure (bullet points, numbers, section headers) of the original. "
        "Return ONLY the translated text, nothing else."
    )

    llm = client or get_gemini_client()

    try:
        translated = llm.generate(
            prompt=f"Translate the following farm advisory to {lang_name}:\n\n{text}",
            system_instruction=system_prompt,
            temperature=0.1,
            max_tokens=1024,
        )
        log.info(
            "Translated advisory to %s (%s) | input_len=%d | output_len=%d",
            lang_name, target_language, len(text), len(translated),
        )
        return translated
    except Exception as exc:
        log.error("Translation to %s failed: %s — returning original English.", lang_name, exc)
        return text  # Graceful fallback to English


def translate_sms(
    sms_text: str,
    target_language: str,
    client: Optional[GeminiClient] = None,
) -> str:
    """
    Translates a short SMS alert (≤160 chars) to a regional language.
    Special handling to preserve the compact format.
    """
    if target_language == "en":
        return sms_text

    lang_name = SUPPORTED_LANGUAGES.get(target_language, target_language)
    llm = client or get_gemini_client()

    system_prompt = (
        f"Translate this SMS alert to {lang_name}. "
        "Keep it under 160 characters. Keep numbers and units in English. "
        "Return ONLY the translated SMS text."
    )

    try:
        translated = llm.generate(
            prompt=sms_text,
            system_instruction=system_prompt,
            temperature=0.1,
            max_tokens=64,
        )
        # Safety: truncate if somehow model returns more than 160 chars
        return translated[:160]
    except Exception as exc:
        log.error("SMS translation to %s failed: %s", lang_name, exc)
        return sms_text


def detect_farmer_language(farm_metadata: dict) -> str:
    """
    Returns the language code from farm metadata, defaulting to English.
    Reads from: farm_metadata["language"] or farm_metadata["region"]
    """
    lang = farm_metadata.get("language", "").lower()
    if lang in SUPPORTED_LANGUAGES:
        return lang

    # Region-to-language fallback map
    region_map = {
        "punjab": "hi", "haryana": "hi", "rajasthan": "hi", "up": "hi",
        "maharashtra": "mr",
        "tamil_nadu": "ta", "tn": "ta",
        "andhra_pradesh": "te", "ap": "te", "telangana": "te",
        "west_bengal": "bn", "wb": "bn",
        "karnataka": "kn",
    }
    region = farm_metadata.get("region", "").lower().replace(" ", "_")
    return region_map.get(region, "en")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sample = (
        "Farm F1 Alert:\n"
        "• Irrigation needed tomorrow (June 15). Apply 12,000 liters.\n"
        "• Yield forecast: 3,200 kg/hectare (good season).\n"
        "• Pest risk: Low. Continue monitoring.\n"
    )

    try:
        result_hi = translate_advisory(sample, "hi")
        print("=== Hindi ===")
        print(result_hi)
    except EnvironmentError as e:
        print(f"No API key set — skipping live test: {e}")

    # Test language detection
    farm = {"region": "Punjab"}
    print(f"\nDetected language for {farm}: {detect_farmer_language(farm)}")
