"""
nodes/satellite_vision_node.py
================================
LangGraph node — Satellite Vision Analysis

Reads satellite imagery metadata from the shared AgriState, encodes the
false-color composite PNG to base64, calls Gemini 1.5 Pro Vision, and
writes structured agronomic analysis back into state.

State keys consumed
-------------------
  state["satellite"]["image_path"]    : str  — path to false-color composite PNG
  state["satellite"]["ndvi_mean"]     : float
  state["satellite"]["ndvi_std"]      : float
  state["satellite"]["stress_alert"]  : bool
  state["satellite"]["farm_id"]       : str

State keys produced
-------------------
  state["vision_analysis"]            : dict  — Gemini JSON response (parsed)
  state["errors"]                     : list  — appended on failure (non-fatal)

Environment variables
---------------------
  GEMINI_API_KEY  — Google AI Studio or Vertex AI key
"""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any, TypedDict

import google.generativeai as genai

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

# ---------------------------------------------------------------------------
# AgriState schema (TypedDict)
# The full state graph is defined in state.py; we declare only the slice
# relevant to this node to keep the import tree clean.
# ---------------------------------------------------------------------------

class SatelliteState(TypedDict, total=False):
    image_path: str
    ndvi_mean: float
    ndvi_std: float
    stress_alert: bool
    farm_id: str


class AgriState(TypedDict, total=False):
    satellite: SatelliteState
    vision_analysis: dict[str, Any]
    errors: list[str]


# ---------------------------------------------------------------------------
# Gemini client initialisation
# ---------------------------------------------------------------------------

def _get_gemini_client() -> genai.GenerativeModel:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Obtain a key from https://aistudio.google.com/app/apikey"
        )
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name="gemini-1.5-pro")
    log.info("Gemini 1.5 Pro client initialised.")
    return model


# ---------------------------------------------------------------------------
# System prompt (verbatim from spec)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are an expert agronomist analyzing Sentinel-2 satellite imagery. "
    "You are given a false-color composite (NIR-Red-Green bands) and NDVI "
    "statistics for a small farm. Analyze and return ONLY a JSON object "
    "with these exact keys:\n"
    "{\n"
    "  'health_score': int (0-100, where 100 = perfect crop health),\n"
    "  'stressed_zone_pct': float (% of visible field under stress),\n"
    "  'likely_cause': str (one of: water_stress | pest_damage | "
    "nutrient_deficiency | disease | healthy),\n"
    "  'growth_stage': str (seedling | vegetative | flowering | "
    "maturation | harvest_ready | unknown),\n"
    "  'confidence': float (0.0 to 1.0),\n"
    "  'agronomist_note': str (one sentence max, plain language for farmer)\n"
    "}\n"
    "Do not include markdown, code fences, or explanation. JSON only."
)

# Expected keys in the Gemini response
_REQUIRED_KEYS = {
    "health_score",
    "stressed_zone_pct",
    "likely_cause",
    "growth_stage",
    "confidence",
    "agronomist_note",
}

_VALID_CAUSES = {
    "water_stress", "pest_damage", "nutrient_deficiency", "disease", "healthy"
}
_VALID_STAGES = {
    "seedling", "vegetative", "flowering", "maturation", "harvest_ready", "unknown"
}


# ---------------------------------------------------------------------------
# Image encoding helpers
# ---------------------------------------------------------------------------

def _encode_png_to_base64(image_path: str | Path) -> str:
    """Read a PNG file and return its base64-encoded bytes as a UTF-8 string."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"False-color composite not found: {path}")
    with open(path, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("utf-8")
    log.info("Encoded composite PNG (%d bytes base64): %s", len(encoded), path)
    return encoded


# ---------------------------------------------------------------------------
# Response parsing & validation
# ---------------------------------------------------------------------------

def _parse_vision_response(raw_text: str, farm_id: str) -> dict[str, Any]:
    """
    Parse and validate the JSON string returned by Gemini.

    Strips any accidental markdown fences before parsing.  If validation
    fails, returns a fallback dict with error metadata rather than raising.
    """
    # Strip common LLM artefacts
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            ln for ln in lines if not ln.strip().startswith("```")
        ).strip()

    try:
        parsed: dict = json.loads(text)
    except json.JSONDecodeError as exc:
        log.error("Gemini response is not valid JSON: %s | raw=%r", exc, raw_text[:300])
        return _fallback_response(farm_id, error=f"JSON parse error: {exc}")

    # Key presence check
    missing = _REQUIRED_KEYS - set(parsed.keys())
    if missing:
        log.warning("Gemini response missing keys: %s — using fallback.", missing)
        return _fallback_response(farm_id, error=f"Missing keys: {missing}")

    # Type coercions + range clamps
    try:
        parsed["health_score"] = max(0, min(100, int(parsed["health_score"])))
        parsed["stressed_zone_pct"] = max(0.0, min(100.0, float(parsed["stressed_zone_pct"])))
        parsed["confidence"] = max(0.0, min(1.0, float(parsed["confidence"])))

        if parsed["likely_cause"] not in _VALID_CAUSES:
            log.warning(
                "Unknown likely_cause '%s'; defaulting to 'healthy'.",
                parsed["likely_cause"],
            )
            parsed["likely_cause"] = "healthy"

        if parsed["growth_stage"] not in _VALID_STAGES:
            log.warning(
                "Unknown growth_stage '%s'; defaulting to 'unknown'.",
                parsed["growth_stage"],
            )
            parsed["growth_stage"] = "unknown"

        parsed["agronomist_note"] = str(parsed["agronomist_note"])[:500]

    except (TypeError, ValueError) as exc:
        log.error("Type coercion failed: %s", exc)
        return _fallback_response(farm_id, error=f"Type coercion: {exc}")

    parsed["farm_id"] = farm_id
    parsed["source"] = "gemini-1.5-pro"
    log.info(
        "Vision analysis | farm=%s | health=%d | cause=%s | stage=%s | conf=%.2f",
        farm_id,
        parsed["health_score"],
        parsed["likely_cause"],
        parsed["growth_stage"],
        parsed["confidence"],
    )
    return parsed


def _fallback_response(farm_id: str, error: str = "") -> dict[str, Any]:
    """Return a safe default when Gemini output cannot be parsed."""
    return {
        "health_score": 50,
        "stressed_zone_pct": 0.0,
        "likely_cause": "healthy",
        "growth_stage": "unknown",
        "confidence": 0.0,
        "agronomist_note": "Analysis unavailable; please review imagery manually.",
        "farm_id": farm_id,
        "source": "fallback",
        "error": error,
    }


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

def satellite_vision_node(state: AgriState) -> AgriState:
    """
    LangGraph node: analyse satellite imagery with Gemini 1.5 Pro Vision.

    This function is intentionally non-raising — any error is appended to
    state["errors"] and a safe fallback vision_analysis is stored, allowing
    the graph to continue to downstream nodes.

    Parameters
    ----------
    state : AgriState  — shared graph state

    Returns
    -------
    Updated AgriState with "vision_analysis" populated.
    """
    errors: list[str] = list(state.get("errors", []))

    satellite: SatelliteState = state.get("satellite", {})
    farm_id: str = satellite.get("farm_id", "unknown_farm")
    image_path: str = satellite.get("image_path", "")
    ndvi_mean: float = float(satellite.get("ndvi_mean", 0.0))
    ndvi_std: float  = float(satellite.get("ndvi_std", 0.0))
    stress_alert: bool = bool(satellite.get("stress_alert", False))

    log.info(
        "[satellite_vision_node] farm=%s | ndvi_mean=%.3f | stress=%s | image=%s",
        farm_id, ndvi_mean, stress_alert, image_path,
    )

    # ---- guard: image path required ----
    if not image_path:
        err = "satellite_vision_node: 'image_path' missing from state.satellite"
        log.error(err)
        errors.append(err)
        return {
            **state,
            "vision_analysis": _fallback_response(farm_id, error=err),
            "errors": errors,
        }

    try:
        # ---- encode composite PNG ----
        b64_image = _encode_png_to_base64(image_path)

        # ---- build Gemini request ----
        model = _get_gemini_client()

        # Construct a rich contextual user prompt so Gemini has numeric context
        user_prompt = (
            f"Farm ID: {farm_id}\n"
            f"NDVI mean: {ndvi_mean:.4f}\n"
            f"NDVI std deviation: {ndvi_std:.4f}\n"
            f"Stress alert triggered: {'YES — NDVI below 0.30' if stress_alert else 'No'}\n\n"
            "The attached image is a false-color Sentinel-2 composite "
            "(NIR → Red channel, Red → Green channel, Green → Blue channel). "
            "Bright red regions indicate healthy dense vegetation; "
            "pale or dark areas indicate stressed or sparse cover.\n\n"
            "Return the JSON analysis as instructed."
        )

        response = model.generate_content(
            [
                {"role": "user", "parts": [SYSTEM_PROMPT]},
                {
                    "role": "user",
                    "parts": [
                        user_prompt,
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image,
                            }
                        },
                    ],
                },
            ],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,        # near-deterministic for structured output
                max_output_tokens=512,
            ),
        )

        raw_text: str = response.text
        log.debug("Gemini raw response: %r", raw_text[:500])

        # ---- parse & validate ----
        vision_analysis = _parse_vision_response(raw_text, farm_id)

    except FileNotFoundError as exc:
        err = f"satellite_vision_node: composite PNG not found — {exc}"
        log.error(err)
        errors.append(err)
        vision_analysis = _fallback_response(farm_id, error=err)

    except Exception as exc:  # noqa: BLE001
        err = f"satellite_vision_node: Gemini call failed — {type(exc).__name__}: {exc}"
        log.error(err)
        errors.append(err)
        vision_analysis = _fallback_response(farm_id, error=err)

    return {
        **state,
        "vision_analysis": vision_analysis,
        "errors": errors,
    }
