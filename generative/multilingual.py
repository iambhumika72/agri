"""
generative/multilingual.py
============================
Regional language translation for AgriSense advisories, alerts, and SMS.

Supports Hindi, Punjabi, Gujarati, Tamil, Telugu, Marathi, Bengali, and Kannada
using the Gemini API for high-quality agricultural context translation.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from .llm_client import GeminiClient, get_gemini_client

log = logging.getLogger(__name__)

# ── Supported languages ──────────────────────────────────────────────────────
SUPPORTED_LANGUAGES: dict[str, str] = {
    "hi": "Hindi",
    "pa": "Punjabi",
    "gu": "Gujarati",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "bn": "Bengali",
    "kn": "Kannada",
    "en": "English",  # passthrough
}

# Language-specific translation instructions for agricultural context
_TRANSLATION_INSTRUCTIONS: dict[str, str] = {
    "hi": (
        "Translate to simple, clear Hindi (Hindustani) as spoken by farmers in rural India. "
        "Use common agricultural terms in Hindi. Avoid overly formal or literary Hindi. "
        "Keep numbers, units (kg, mm, liters, ppm), and brand names in English."
    ),
    "pa": (
        "Translate to Punjabi (Gurmukhi script) as spoken by farmers in Punjab and Haryana. "
        "Use everyday farming vocabulary a village farmer would understand. "
        "Keep numbers, units, and brand names in English."
    ),
    "gu": (
        "Translate to Gujarati as spoken by farmers in Gujarat. "
        "Use simple, conversational Gujarati suitable for rural farmers. "
        "Keep numbers, units, and brand names in English."
    ),
    "ta": (
        "Translate to Tamil as spoken by farmers in Tamil Nadu. "
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
        "Translate to Bengali (Bangla) as spoken by farmers in West Bengal. "
        "Use simple, clear language a rural farmer would understand. "
        "Keep numbers and units in English."
    ),
    "kn": (
        "Translate to Kannada as spoken by farmers in Karnataka. "
        "Use simple, rural farming vocabulary. Keep numbers and units in English."
    ),
}


def get_language_name(lang_code: str) -> str:
    """Returns the display name for a language code. Defaults to the code itself."""
    return SUPPORTED_LANGUAGES.get(lang_code, lang_code)


def is_supported(lang_code: str) -> bool:
    """Returns True if the language code is supported for translation."""
    return lang_code in SUPPORTED_LANGUAGES


def translate_advisory(
    text: str,
    target_language: str,
    client: Optional[GeminiClient] = None,
) -> str:
    """
    Translates a multi-paragraph farm advisory to the target regional language.
    Preserves bullet points, numbered lists, and section headers.
    """
    if target_language == "en" or not text.strip():
        return text
    if target_language not in SUPPORTED_LANGUAGES:
        log.warning("Unsupported language '%s'. Returning English.", target_language)
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
        log.info("Translated advisory to %s | chars: %d→%d", lang_name, len(text), len(translated))
        return translated
    except Exception as exc:
        log.error("Translation to %s failed: %s — returning English.", lang_name, exc)
        return text


def translate_sms(
    sms_text: str,
    target_language: str,
    client: Optional[GeminiClient] = None,
) -> str:
    """
    Translates a short SMS alert (≤160 chars) to a regional language.
    Preserves compact format and truncates to 160 chars if needed.
    """
    if target_language == "en" or not sms_text.strip():
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
        return translated[:160]
    except Exception as exc:
        log.error("SMS translation to %s failed: %s", lang_name, exc)
        return sms_text


def translate_alert_message(
    alert_message: str,
    recommendation: str,
    target_language: str,
    client: Optional[GeminiClient] = None,
) -> tuple[str, str]:
    """
    Translates an alert message and its recommendation text.
    Returns (translated_message, translated_recommendation).
    Uses a single LLM call with a JSON response for efficiency.
    """
    if target_language == "en":
        return alert_message, recommendation

    lang_name = SUPPORTED_LANGUAGES.get(target_language, target_language)
    instruction = _TRANSLATION_INSTRUCTIONS.get(target_language, f"Translate to {lang_name}.")

    payload = json.dumps({"message": alert_message, "recommendation": recommendation})
    system_prompt = (
        f"You are an agricultural translator. {instruction} "
        "You will receive a JSON object with 'message' and 'recommendation' fields. "
        f"Translate BOTH values to {lang_name}. "
        "Return ONLY a valid JSON object with the same two keys and translated values. "
        "No markdown, no explanation."
    )
    llm = client or get_gemini_client()
    try:
        raw = llm.generate(
            prompt=f"Translate this JSON to {lang_name}:\n{payload}",
            system_instruction=system_prompt,
            temperature=0.1,
            max_tokens=512,
        )
        # Strip markdown fences if model wraps it
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(clean)
        return data.get("message", alert_message), data.get("recommendation", recommendation)
    except Exception as exc:
        log.error("Alert translation to %s failed: %s — returning English.", lang_name, exc)
        return alert_message, recommendation


def translate_batch(
    fields: dict[str, str],
    target_language: str,
    client: Optional[GeminiClient] = None,
) -> dict[str, str]:
    """
    Translates multiple text fields in a single LLM call.
    Efficient for translating structured outputs (e.g. pest detection results).

    Args:
        fields: dict mapping field_name → English text to translate
        target_language: ISO 639-1 code

    Returns:
        dict with same keys, translated values (falls back to English on error)
    """
    if target_language == "en":
        return fields

    # Filter out empty fields
    to_translate = {k: v for k, v in fields.items() if v and v.strip()}
    if not to_translate:
        return fields

    lang_name = SUPPORTED_LANGUAGES.get(target_language, target_language)
    instruction = _TRANSLATION_INSTRUCTIONS.get(target_language, f"Translate to {lang_name}.")

    payload = json.dumps(to_translate, ensure_ascii=False)
    system_prompt = (
        f"You are an agricultural translator. {instruction} "
        "You will receive a JSON object. Translate ALL string values to "
        f"{lang_name}. Keep all JSON keys in English. "
        "Return ONLY a valid JSON object. No markdown, no explanation."
    )
    llm = client or get_gemini_client()
    try:
        raw = llm.generate(
            prompt=f"Translate to {lang_name}:\n{payload}",
            system_instruction=system_prompt,
            temperature=0.1,
            max_tokens=1024,
        )
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        translated = json.loads(clean)
        # Merge back: translated fields + any fields we skipped (empty)
        result = {**fields}
        result.update(translated)
        return result
    except Exception as exc:
        log.error("Batch translation to %s failed: %s — returning English.", lang_name, exc)
        return fields


def detect_farmer_language(farm_metadata: dict) -> str:
    """
    Returns the language code from farm metadata, defaulting to English.
    Reads from: farm_metadata["language"] or farm_metadata["region"].
    """
    lang = farm_metadata.get("language", "").lower()
    if lang in SUPPORTED_LANGUAGES:
        return lang

    region_map = {
        "punjab": "pa", "haryana": "pa",
        "uttar_pradesh": "hi", "up": "hi", "madhya_pradesh": "hi", "mp": "hi",
        "bihar": "hi", "rajasthan": "hi", "uttarakhand": "hi", "himachal_pradesh": "hi",
        "maharashtra": "mr",
        "gujarat": "gu",
        "tamil_nadu": "ta", "tn": "ta",
        "andhra_pradesh": "te", "ap": "te", "telangana": "te",
        "west_bengal": "bn", "wb": "bn",
        "karnataka": "kn",
        "kerala": "ml",  # Malayalam — not yet supported, fallback to en
    }
    region = farm_metadata.get("region", "").lower().replace(" ", "_")
    return region_map.get(region, "en")
