from __future__ import annotations

"""
api/dependencies.py
====================
Shared FastAPI dependency providers for AgriSense API.
"""

import logging
import os
from functools import lru_cache

from fastapi import Header, HTTPException

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_settings() -> dict:
    """Returns application settings loaded from environment variables."""
    return {
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "twilio_sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "twilio_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "gee_service_account": os.environ.get("GEE_SERVICE_ACCOUNT", ""),
        "redis_url": os.environ.get("REDIS_URL", "redis://localhost:6379"),
        "environment": os.environ.get("AGRISENSE_ENV", "development"),
    }


async def get_farm_id_header(x_farm_id: str = Header(default="")) -> str:
    """
    Optional dependency: reads farm_id from X-Farm-ID request header.
    Falls back gracefully — returns empty string if not set.
    """
    return x_farm_id


async def require_gemini_key() -> str:
    """
    Dependency that raises 503 if GEMINI_API_KEY is not configured.
    Use on routes that strictly require LLM access.
    """
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise HTTPException(
            status_code=503,
            detail=(
                "GEMINI_API_KEY is not configured. "
                "Set it as an environment variable to enable AI-powered recommendations."
            )
        )
    return key
